#include <FltKernel.h>
#include <ntstrsafe.h>
#include "Callbacks.h"
#include "CryptoUtils.hpp"

#define MAX_HEX_STRING_LENGTH 64 

FORCEINLINE UCHAR HexCharToByte(CHAR ch)
{
    if (ch >= '0' && ch <= '9') {
        return ch - '0';
    }
    if (ch >= 'A' && ch <= 'F') {
        return ch - 'A' + 10;
    }
    if (ch >= 'a' && ch <= 'f') {
        return ch - 'a' + 10;
    }
    // Если символ не hex, вернем 0 и будем полагаться на проверку вызывающей функции
    return 0;
}

NTSTATUS HexStringToByteArray(
    _In_ PCCHAR HexString,
    _Out_ PUCHAR OutputBuffer,
    _In_ ULONG OutputLength
)
{
    // Строка должна быть не NULL
    if (HexString == NULL || OutputBuffer == NULL) {
        return STATUS_INVALID_PARAMETER;
    }

    // Получаем длину входной строки
    SIZE_T stringLength = 0;
    NTSTATUS status = RtlStringCbLengthA(HexString, MAX_HEX_STRING_LENGTH, &stringLength);

    // Проверяем, что длина была успешно получена и не превышает лимит.
    if (!NT_SUCCESS(status)) {
        return STATUS_INVALID_PARAMETER;
    }

    // Длина HEX строки должна быть четной (каждый байт = 2 символа)
    if (stringLength % 2 != 0) {
        return STATUS_INVALID_PARAMETER;
    }

    // Выходной буфер должен быть ровно половиной длины строки
    if (stringLength / 2 != OutputLength) {
        return STATUS_BUFFER_TOO_SMALL;
    }

    ULONG i = 0; // Индекс для выходного буфера
    ULONG j = 0; // Индекс для входной строки

    while (j < stringLength)
    {
        // 1. Старшая половина байта (High Nibble)
        CHAR highChar = HexString[j++];
        UCHAR highVal = HexCharToByte(highChar);

        // Проверка, является ли символ допустимым HEX (если HexCharToByte возвращает 0, 
        // это может быть либо '0', либо недопустимый символ. Нужна более строгая проверка)
        if (!((highChar >= '0' && highChar <= '9') ||
            (highChar >= 'A' && highChar <= 'F') ||
            (highChar >= 'a' && highChar <= 'f')))
        {
            return STATUS_DATATYPE_MISALIGNMENT; // Недопустимый символ HEX
        }

        // 2. Младшая половина байта (Low Nibble)
        CHAR lowChar = HexString[j++];
        UCHAR lowVal = HexCharToByte(lowChar);

        if (!((lowChar >= '0' && lowChar <= '9') ||
            (lowChar >= 'A' && lowChar <= 'F') ||
            (lowChar >= 'a' && lowChar <= 'f')))
        {
            return STATUS_DATATYPE_MISALIGNMENT; // Недопустимый символ HEX
        }


        // 3. Комбинирование: (high_val << 4) | low_val
        OutputBuffer[i++] = (highVal << 4) | lowVal;
    }

    return STATUS_SUCCESS;
}


typedef struct FilterData {
	PFLT_FILTER FilterHandle;
} FilterData, *PFilterData;

FilterData gFilterData = { 0 };

CONST FLT_OPERATION_REGISTRATION Callbacks[] = {
	{ IRP_MJ_CREATE, 0, PreCreateCallback, NULL },
	{ IRP_MJ_READ, 0, PreReadCallback, NULL },
	{ IRP_MJ_WRITE, 0, PreWriteCallback, NULL },
	{ IRP_MJ_OPERATION_END }
};

NTSTATUS DriverUnload(
	_In_ FLT_FILTER_UNLOAD_FLAGS  Flags
)
{
	UNREFERENCED_PARAMETER(Flags);
	FltUnregisterFilter(gFilterData.FilterHandle);
	KdPrint(("Driver unloaded successfully\n"));
	return STATUS_SUCCESS;
}

NTSTATUS FilterInstanceQueryTeardown(
	_In_ PCFLT_RELATED_OBJECTS FltObjects,
	_In_ FLT_INSTANCE_QUERY_TEARDOWN_FLAGS Flags
) {
	UNREFERENCED_PARAMETER(FltObjects);
	UNREFERENCED_PARAMETER(Flags);
	KdPrint(("FilterInstanceQueryTeardown called\n"));
	return STATUS_SUCCESS;
}

NTSTATUS FilterInstanceSetup(
	_In_ PCFLT_RELATED_OBJECTS FltObjects,
	_In_ FLT_INSTANCE_SETUP_FLAGS Flags,
	_In_ DEVICE_TYPE VolumeDeviceType,
	_In_ FLT_FILESYSTEM_TYPE VolumeFilesystemType
) {
	UNREFERENCED_PARAMETER(FltObjects);
	UNREFERENCED_PARAMETER(Flags);
	UNREFERENCED_PARAMETER(VolumeDeviceType);
	UNREFERENCED_PARAMETER(VolumeFilesystemType);
	KdPrint(("FilterInstanceSetup called\n"));
	return STATUS_SUCCESS;
}

CONST FLT_REGISTRATION FilterRegistration = {
	sizeof(FLT_REGISTRATION),			// Size
	FLT_REGISTRATION_VERSION,           // Version
	0,                                  // Flags
	NULL,                               // Context
	Callbacks,                               // Operation callbacks
	DriverUnload,                       // FilterUnload
	FilterInstanceSetup,                // InstanceSetup
	FilterInstanceQueryTeardown,		// InstanceQueryTeardown
	NULL,                               // InstanceTeardownStart
	NULL,                               // InstanceTeardownComplete
	NULL,                               // GenerateFileName
	NULL,                               // NormalizeNameComponent
	NULL,                               // NormalizeContextCleanup
	NULL,                               // TransactionNotification
	NULL                                // NormalizeNameComponentEx
};

extern "C" NTSTATUS DriverEntry(
	PDRIVER_OBJECT DriverObject,
	PUNICODE_STRING RegistryPath
)
{
	UNREFERENCED_PARAMETER(RegistryPath);
	NTSTATUS status;
	status = FltRegisterFilter(DriverObject, &FilterRegistration, &gFilterData.FilterHandle);
	if (!NT_SUCCESS(status)) {
		return status;
	}
	status = FltStartFiltering(gFilterData.FilterHandle);
	if (!NT_SUCCESS(status)) {
		FltUnregisterFilter(gFilterData.FilterHandle);
		return status;
	}
	KdPrint(("Driver loaded successfully\n"));
	
	char hexdata[] = "1FF1630DDA1C745990115E0E43D3179CBAD710EAF2BC256FCB78C1CCB6C35E4D";

    char outbuf[32];
    HexStringToByteArray(hexdata, (PUCHAR)outbuf, 32);
    CryptoUtils::DecryptAES256("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", outbuf);
    KdPrint((outbuf));

	return STATUS_SUCCESS;
}