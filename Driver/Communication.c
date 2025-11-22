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

typedef struct _CONNECTION_CONTEXT {
	UCHAR Key[KEY_LENGTH];
	PFLT_PORT ClientPort;
} CONNECTION_CONTEXT, * PCONNECTION_CONTEXT;

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
	SIZE_T viewSize = 0;

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
	status = ZwCreateSection(
		&g_Ctx.SectionHandle,
		SECTION_ALL_ACCESS,
		&oa,
		&sectionSize,
		PAGE_READWRITE,
		SEC_COMMIT,
		NULL
	);
    FltFreeSecurityDescriptor(sd);
	if (!NT_SUCCESS(status)) {
		ZwClose(g_Ctx.SectionHandle);
		FltCloseCommunicationPort(g_Ctx.ServerPort);
		return status;
	}

	viewSize = SHARED_MEM_SIZE;
	g_Ctx.SharedMemoryBase = NULL;
	status = ZwMapViewOfSection(
		g_Ctx.SectionHandle,
		ZwCurrentProcess(),
		&g_Ctx.SharedMemoryBase,
		0,
		SHARED_MEM_SIZE,
		NULL,
		&viewSize,
		ViewUnmap,
		0,
		PAGE_READWRITE
	);

	if (!NT_SUCCESS(status)) {
		ZwClose(g_Ctx.SectionHandle);
		g_Ctx.SectionHandle = NULL;
		FltCloseCommunicationPort(g_Ctx.ServerPort);
		g_Ctx.ServerPort = NULL;
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
		g_Ctx.SharedMemoryBase = NULL;
		ZwClose(g_Ctx.SectionHandle);
		g_Ctx.SectionHandle = NULL;
		FltCloseCommunicationPort(g_Ctx.ServerPort);
		g_Ctx.ServerPort = NULL;
		return status;
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
	KdPrint(("Communication_QueueBigData: Queued %u bytes for sending\n", Length));
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

	if (g_Ctx.ClientPort) {
		return STATUS_TOO_MANY_SESSIONS;
	}

	PCONNECTION_CONTEXT connCtx = ExAllocatePool2(POOL_FLAG_NON_PAGED, sizeof(CONNECTION_CONTEXT), 'cCtx');
	if (!connCtx) {
		KdPrint(("ConnectNotify: Failed to allocate connection context\n"));
		return STATUS_INSUFFICIENT_RESOURCES;
	}
	RtlZeroMemory(connCtx->Key, KEY_LENGTH);
	connCtx->ClientPort = ClientPort;

	*ConnectionCookie = connCtx;
	KdPrint(("ConnectNotify: Client connected\n"));
	return STATUS_SUCCESS;
}

VOID DisconnectNotify(PVOID ConnectionCookie) {
	PCONNECTION_CONTEXT connCtx = (PCONNECTION_CONTEXT)ConnectionCookie;
	if (connCtx)
	{
		ExFreePool(connCtx);
	}
	if (g_Ctx.ClientPort) {
		FltCloseClientPort(g_Ctx.Filter, &g_Ctx.ClientPort);
		g_Ctx.ClientPort = NULL;
	}
	KeSetEvent(&g_Ctx.WorkerWakeEvent, 0, FALSE);
	KdPrint(("DisconnectNotify: Client disconnected\n"));
}

NTSTATUS MessageNotify(PVOID PortCookie, PVOID InputBuffer, ULONG InputBufferLength, PVOID OutputBuffer, ULONG OutputBufferLength, PULONG ReturnOutputBufferLength) {
	UNREFERENCED_PARAMETER(OutputBuffer);
	UNREFERENCED_PARAMETER(OutputBufferLength);
	UNREFERENCED_PARAMETER(ReturnOutputBufferLength);
	PCONNECTION_CONTEXT connCtx = (PCONNECTION_CONTEXT)PortCookie;

	if (InputBuffer == NULL || InputBufferLength < sizeof(USER_MSG_HEADER)) {
		KdPrint(("MessageNotify: Invalid input buffer\n"));
		return STATUS_INVALID_PARAMETER;
	}
	NTSTATUS status;
	PUSER_MSG_HEADER userHeader = (PUSER_MSG_HEADER)InputBuffer;
	switch (userHeader->Command) {
	case CmdType_GetKey:
		if (g_Ctx.ClientPort) {
			KdPrint(("MessageNotify: Already authorized client tried to get key\n"));
			return STATUS_ACCESS_DENIED; // Уже аутентифицирован
		}
		if (OutputBufferLength < KEY_LENGTH || OutputBuffer == NULL) {
			KdPrint(("MessageNotify: Output buffer too small for key\n"));
			return STATUS_BUFFER_TOO_SMALL;
		}
		UCHAR key[KEY_LENGTH];
		status = CUGenerateRandomBytes(key);
		if (!NT_SUCCESS(status)) return status;
		RtlCopyMemory(connCtx->Key, key, KEY_LENGTH);
		RtlCopyMemory(OutputBuffer, key, KEY_LENGTH);
		*ReturnOutputBufferLength = KEY_LENGTH;
		KdPrint(("MessageNotify: Provided encryption key to client\n"));
		return STATUS_SUCCESS;
	case CmdType_Authorize:
		if (!connCtx) {
			KdPrint(("MessageNotify: No connection context in authorize\n"));
			return STATUS_INVALID_PARAMETER;
		}
		if (g_Ctx.ClientPort) {
			KdPrint(("MessageNotify: Client already authorized\n"));
			return STATUS_ACCESS_DENIED; // Уже аутентифицирован
		}
		if (InputBufferLength < sizeof(USER_MESSAGE)) {
			KdPrint(("MessageNotify: Input buffer too small for authorize message\n"));
			return STATUS_INVALID_PARAMETER;
		}
		PUSER_MESSAGE userMsg = (PUSER_MESSAGE)InputBuffer;
		UCHAR recievedToken[KEY_LENGTH];
		UCHAR Token[KEY_LENGTH];
		RtlCopyMemory(recievedToken, userMsg->Data.KeyMsg.Key, KEY_LENGTH);
		CUDecryptAES256(connCtx->Key, recievedToken, Token);
		if (!CUCompareWithSaltMask(connCtx->Key, Token, 0xC0000003)) {
			KdPrint(("MessageNotify: Authorization failed, invalid token\n"));
			return STATUS_ACCESS_DENIED;
		}
		g_Ctx.ClientPort = connCtx->ClientPort;
		KdPrint(("MessageNotify: Client authorized successfully\n"));
		return STATUS_SUCCESS;

	case CmdType_SignalAck:
		KeSetEvent(&g_Ctx.UmAckEvent, 0, FALSE);
		KdPrint(("MessageNotify: Received Ack from client\n"));
		break;
	default:
		return STATUS_INVALID_PARAMETER;
	}
	return STATUS_SUCCESS;
}