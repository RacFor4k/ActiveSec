#include "Communication.h"
#include "CryptoUtils.h"
#include <ntstrsafe.h>

typedef struct _QUEUE_ITEM {
    LIST_ENTRY ListEntry;
    PVOID DataBuffer;
    ULONG DataLength;
} QUEUE_ITEM, * PQUEUE_ITEM;

typedef struct _COMM_CONTEXT {
    PFLT_FILTER Filter;
    PFLT_PORT ServerPort;
    PFLT_PORT ClientPort;

    // Shared Memory
    HANDLE SectionHandle;
    PVOID SharedMemoryBase;

    // Worker & Queue
    KSPIN_LOCK QueueLock;
    LIST_ENTRY QueueHead;
    KEVENT WorkerWakeEvent;     // Будит воркер, когда есть работа
    KEVENT UmAckEvent;          // Будит воркер, когда UM прочитал данные
    PKTHREAD WorkerThreadObj;
    BOOLEAN ShutdownFlag;

} COMM_CONTEXT, * PCOMM_CONTEXT;

static COMM_CONTEXT g_Ctx = { 0 };

NTSTATUS ConnectNotify(PFLT_PORT ClientPort, PVOID ServerPortCookie, PVOID Context, ULONG Size, PVOID* ConnectionCookie);
VOID DisconnectNotify(PVOID ConnectionCookie);
NTSTATUS MessageNotify(PVOID PortCookie, PVOID InputBuffer, ULONG InputBufferLength, PVOID OutputBuffer, ULONG OutputBufferLength, PULONG ReturnOutputBufferLength);
VOID WorkerThreadRoutine(PVOID Context);

NTSTATUS Communication_Init(PFLT_FILTER Filter) {
    NTSTATUS status;
    OBJECT_ATTRIBUTES oa;
    PSECURITY_DESCRIPTOR sd;
    UNICODE_STRING portName;
    UNICODE_STRING sectionName;
    LARGE_INTEGER sectionSize;

    g_Ctx.Filter = Filter;
    KeInitializeSpinLock(&g_Ctx.QueueLock);
	InitializeListHead(&g_Ctx.QueueHead);
	KeInitializeEvent(&g_Ctx.WorkerWakeEvent, NotificationEvent, FALSE);
	KeInitializeEvent(&g_Ctx.UmAckEvent, NotificationEvent, FALSE);
	g_Ctx.ShutdownFlag = FALSE;

	RtlInitUnicodeString(&portName, MSG_PORT_NAME);
	status = FltBuildDefaultSecurityDescriptor(&sd, FLT_PORT_ALL_ACCESS);
    if (!NT_SUCCESS(status)) return status;

    InitializeObjectAttributes(&oa, &portName, OBJ_KERNEL_HANDLE | OBJ_CASE_INSENSITIVE, NULL, sd);
	status = FltCreateCommunicationPort(
		Filter,
		&g_Ctx.ServerPort,
		&oa,
		NULL,
		ConnectNotify,
		DisconnectNotify,
		MessageNotify,
		1
	);
	
	if (!NT_SUCCESS(status)) {
		FltCloseCommunicationPort(g_Ctx.ServerPort);
		return status;
	}
    
    if (!NT_SUCCESS(status)) return status;
	RtlInitUnicodeString(&sectionName, SHARED_SECTION_NAME);
	sectionSize.QuadPart = SHARED_MEM_SIZE;
	InitializeObjectAttributes(&oa, &sectionName, OBJ_KERNEL_HANDLE | OBJ_CASE_INSENSITIVE, NULL, sd);
    FltFreeSecurityDescriptor(sd);
	status = ZwCreateSection(
		&g_Ctx.SectionHandle,
		SECTION_ALL_ACCESS,
		&oa,
		&sectionSize,
		PAGE_READWRITE,
		SEC_COMMIT,
		NULL
	);
	if (!NT_SUCCESS(status)) {
		ZwClose(g_Ctx.SectionHandle);
		FltCloseCommunicationPort(g_Ctx.ServerPort);
		return status;
	}

	HANDLE threadHandle;
	status = PsCreateSystemThread(
		&threadHandle,
		THREAD_ALL_ACCESS,
		NULL,
		NULL,
		NULL,
		WorkerThreadRoutine,
		&g_Ctx
	);
	if (NT_SUCCESS(status)) {
		ObReferenceObjectByHandle(threadHandle, THREAD_ALL_ACCESS, *PsThreadType, KernelMode, &g_Ctx.WorkerThreadObj, NULL);
		ZwClose(threadHandle);
	}
	else {
		// Очистка при ошибке...
		ZwUnmapViewOfSection(ZwCurrentProcess(), g_Ctx.SharedMemoryBase);
		ZwClose(g_Ctx.SectionHandle);
		FltCloseCommunicationPort(g_Ctx.ServerPort);
	}
	return status;
}

VOID Communication_Shutdown() {
	g_Ctx.ShutdownFlag = TRUE;

	KeSetEvent(&g_Ctx.WorkerWakeEvent, 0, FALSE);
	KeSetEvent(&g_Ctx.UmAckEvent, 0, FALSE);

	if (g_Ctx.WorkerThreadObj) {
		KeWaitForSingleObject(g_Ctx.WorkerThreadObj, Executive, KernelMode, FALSE, NULL);
		ObDereferenceObject(g_Ctx.WorkerThreadObj);
	}

	if (g_Ctx.ClientPort)
		FltCloseClientPort(g_Ctx.Filter, &g_Ctx.ClientPort);
	FltCloseCommunicationPort(g_Ctx.ServerPort);

	if (g_Ctx.SharedMemoryBase)
		ZwUnmapViewOfSection(ZwCurrentProcess(), g_Ctx.SharedMemoryBase);
	if (g_Ctx.SectionHandle)
		ZwClose(g_Ctx.SectionHandle);

	// Очистка очереди
	KIRQL irql;
	KeAcquireSpinLock(&g_Ctx.QueueLock, &irql);
	while (!IsListEmpty(&g_Ctx.QueueHead)) {
		PLIST_ENTRY entry = RemoveHeadList(&g_Ctx.QueueHead);
		PQUEUE_ITEM item = CONTAINING_RECORD(entry, QUEUE_ITEM, ListEntry);
		if (item->DataBuffer)
			ExFreePool(item->DataBuffer);
		ExFreePool(item);
	}
	KeReleaseSpinLock(&g_Ctx.QueueLock, irql);
}

NTSTATUS Communication_QueueBigData(PVOID Buffer, ULONG Length) {
	if (!g_Ctx.ClientPort)
		return STATUS_PORT_DISCONNECTED;
	if (Length == 0 || Buffer == NULL)
		return STATUS_INVALID_PARAMETER;

	PQUEUE_ITEM item = ExAllocatePool2(POOL_FLAG_NON_PAGED, sizeof(QUEUE_ITEM), 'qItm');
	if (!item)
		return STATUS_INSUFFICIENT_RESOURCES;
	item->DataBuffer = ExAllocatePool2(POOL_FLAG_NON_PAGED, Length, 'qDat');
	if (!item->DataBuffer) {
		ExFreePool(item);
		return STATUS_INSUFFICIENT_RESOURCES;
	}
	RtlCopyMemory(item->DataBuffer, Buffer, Length);
	item->DataLength = Length;

	KIRQL irql;
	KeAcquireSpinLock(&g_Ctx.QueueLock, &irql);
	InsertTailList(&g_Ctx.QueueHead, &item->ListEntry);
	KeReleaseSpinLock(&g_Ctx.QueueLock, irql);

	KeSetEvent(&g_Ctx.WorkerWakeEvent, 0, FALSE);
	return STATUS_SUCCESS;
}

NTSTATUS Communication_SendMessage(PUNICODE_STRING Message) {
	if (!g_Ctx.ClientPort)
		return STATUS_PORT_DISCONNECTED;
	if (Message == NULL || Message->Length == 0)
		return STATUS_INVALID_PARAMETER;
	ULONG msgSize = sizeof(DRIVER_MSG_HEADER) + Message->Length; // + null-terminator
	PVOID msgBuffer = ExAllocatePool2(POOL_FLAG_NON_PAGED, msgSize, 'mBuf');
	if (!msgBuffer)
		return STATUS_INSUFFICIENT_RESOURCES;

	PDRIVER_MSG_HEADER header = (PDRIVER_MSG_HEADER)msgBuffer;
	header->Type = MsgType_LogInfo;
	header->DataSize = Message->Length;
	header->TotalSize = header->DataSize;
	header->CurrentOffset = 0;

	PWCHAR msgData = (PWCHAR)((PUCHAR)msgBuffer + sizeof(DRIVER_MSG_HEADER));
	RtlCopyMemory(msgData, Message->Buffer, Message->Length);

	LARGE_INTEGER timeout;
	timeout.QuadPart = -10 * 1000 * 1; // 1 ms
	NTSTATUS status = FltSendMessage(
		g_Ctx.Filter,
		&g_Ctx.ClientPort,
		msgBuffer,
		msgSize,
		NULL,
		NULL,
		&timeout
	);
	ExFreePool(msgBuffer);
	return status;
}

// --- Worker Thread Logic ---

VOID WorkerThreadRoutine(PVOID Context) {
	PCOMM_CONTEXT ctx = (PCOMM_CONTEXT)Context;

	while (TRUE) {
		KeWaitForSingleObject(&ctx->WorkerWakeEvent, Executive, KernelMode, FALSE, NULL);
		if (ctx->ShutdownFlag)
			break;
		// Обработка очереди
		while (TRUE) {
			PQUEUE_ITEM item = NULL;
			KIRQL irql;

			KeAcquireSpinLock(&ctx->QueueLock, &irql);
			if (!IsListEmpty(&ctx->QueueHead)) {
				PLIST_ENTRY entry = RemoveHeadList(&ctx->QueueHead);
				item = CONTAINING_RECORD(entry, QUEUE_ITEM, ListEntry);
			}
			KeReleaseSpinLock(&ctx->QueueLock, irql);

			if (item == NULL)
				break; // Очередь пуста
			
			ULONG offset = 0;
			PUCHAR srcBuffer = (PUCHAR)item->DataBuffer;

			while (offset < item->DataLength && !ctx->ShutdownFlag) {
				if (!ctx->ClientPort)
					break;

				ULONG remaining = item->DataLength - offset;
				ULONG chunkSize = (remaining > SHARED_MEM_SIZE) ? (SHARED_MEM_SIZE) : remaining;

				// Копируем в Shared Memory
				RtlCopyMemory(ctx->SharedMemoryBase, srcBuffer + offset, chunkSize);

				// Формируем сообщение
				DRIVER_MSG_HEADER msg;
				msg.Type = MsgType_DataReady;
				msg.DataSize = chunkSize;
				msg.TotalSize = item->DataLength;
				msg.CurrentOffset = offset;

				// Отправляем сообщение
				LARGE_INTEGER timeout;
				timeout.QuadPart = -10 * 1000 * 10; // 10 ms
				NTSTATUS status = FltSendMessage(
					ctx->Filter,
					&ctx->ClientPort,
					&msg,
					sizeof(msg),
					NULL,
					NULL,
					&timeout
				);

				if (!NT_SUCCESS(status)) {
					KdPrint(("WorkerThread: FltSendMessage failed: 0x%X\n", status));
					break;
				}

				// Ждем подтверждения от UM
				KeWaitForSingleObject(&ctx->UmAckEvent, Executive, KernelMode, FALSE, NULL);

				if (ctx->ShutdownFlag)
					break;

				offset += chunkSize;
			}


			if(item->DataBuffer) ExFreePool(item->DataBuffer);
			ExFreePool(item);
		}
	}
	PsTerminateSystemThread(STATUS_SUCCESS);
}

// --- Callbacks порта ---

NTSTATUS ConnectNotify(PFLT_PORT ClientPort, PVOID ServerPortCookie, PVOID Context, ULONG Size, PVOID* ConnectionCookie) {
	UNREFERENCED_PARAMETER(ServerPortCookie);
	UNREFERENCED_PARAMETER(Context);
	UNREFERENCED_PARAMETER(Size);
	NTSTATUS status;
	UCHAR key[32];
	PFLT_PORT clientPortTemp = NULL;

	if (g_Ctx.ClientPort) {
		// Уже есть клиент, не разрешаем второе подключение
		return STATUS_TOO_MANY_SESSIONS;
	}
	CUGenerateRandomBytes(key);

	clientPortTemp = ClientPort;

	ULONG replyLength = KEY_LENGTH;
	UCHAR responseToken[KEY_LENGTH];

	LARGE_INTEGER timeout;
	timeout.QuadPart = -10 * 1000 * 1000; // 1000 ms

	status = FltSendMessage(
		g_Ctx.Filter,
		&clientPortTemp,
		key, // Буфер для отправки (Challenge)
		KEY_LENGTH,
		responseToken, // Буфер для приема ответа (Response Token)
		&replyLength,
		&timeout
	);

	if (!NT_SUCCESS(status) || replyLength != KEY_LENGTH) {
		ExFreePool(key);
		return STATUS_ACCESS_DENIED;
	}

	UCHAR token[KEY_LENGTH];
	CUDecryptAES256(key, responseToken, token);

	if (!CUCompareWithSaltMask(key, token, 0xC0000003)) {
		ExFreePool(key);
		return STATUS_ACCESS_DENIED;
	}

	g_Ctx.ClientPort = clientPortTemp;
	ExFreePool(key);
	*ConnectionCookie = NULL;
	return STATUS_SUCCESS;
}

VOID DisconnectNotify(PVOID ConnectionCookie) {
	UNREFERENCED_PARAMETER(ConnectionCookie);
	if (g_Ctx.ClientPort) {
		FltCloseClientPort(g_Ctx.Filter, &g_Ctx.ClientPort);
		g_Ctx.ClientPort = NULL;
	}
	KeSetEvent(&g_Ctx.WorkerWakeEvent, 0, FALSE);
}

NTSTATUS MessageNotify(PVOID PortCookie, PVOID InputBuffer, ULONG InputBufferLength, PVOID OutputBuffer, ULONG OutputBufferLength, PULONG ReturnOutputBufferLength) {
	UNREFERENCED_PARAMETER(PortCookie);
	UNREFERENCED_PARAMETER(OutputBuffer);
	UNREFERENCED_PARAMETER(OutputBufferLength);
	UNREFERENCED_PARAMETER(ReturnOutputBufferLength);
	if (InputBuffer == NULL || InputBufferLength < sizeof(USER_MSG_HEADER))
		return STATUS_INVALID_PARAMETER;

	PUSER_MSG_HEADER userHeader = (PUSER_MSG_HEADER)InputBuffer;
	switch (userHeader->Command) {
	case CmdType_SignalAck:
		KeSetEvent(&g_Ctx.UmAckEvent, 0, FALSE);
		break;
	default:
		return STATUS_INVALID_PARAMETER;
	}
	return STATUS_SUCCESS;
}