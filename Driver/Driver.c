#include <FltKernel.h>
#include <ntstrsafe.h>
#include "Callbacks.h"
#include "CryptoUtils.h"

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

NTSTATUS TestCrypto()
{
	NTSTATUS status;

	//
	// 1. Выделяем память
	//

	UCHAR* key = ExAllocatePool2(POOL_FLAG_NON_PAGED, KEY_LENGTH, MY_CRYPTO_TAG);
	UCHAR* plain = ExAllocatePool2(POOL_FLAG_NON_PAGED, DATA_LEN, MY_CRYPTO_TAG);
	UCHAR* encrypted = ExAllocatePool2(POOL_FLAG_NON_PAGED, DATA_LEN, MY_CRYPTO_TAG);
	UCHAR* decrypted = ExAllocatePool2(POOL_FLAG_NON_PAGED, DATA_LEN, MY_CRYPTO_TAG);

	if (!key || !plain || !encrypted || !decrypted)
	{
		status = STATUS_INSUFFICIENT_RESOURCES;
		goto Cleanup;
	}

	RtlZeroMemory(key, KEY_LENGTH);
	RtlZeroMemory(plain, DATA_LEN);
	RtlZeroMemory(encrypted, DATA_LEN);
	RtlZeroMemory(decrypted, DATA_LEN);

	//
	// 2. Заполняем входные данные
	//

	// key (32 bytes)
	RtlCopyMemory(key, "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", 32);

	// plain text (до 31 байта + 0)
	RtlCopyMemory(plain, "Hello kernel AES test", 22);

	KdPrint(("=== START AES TEST ===\n"));

	//
	// 3. Encrypt
	//
	status = CUEncryptAES256(key, plain, encrypted);
	if (!NT_SUCCESS(status))
	{
		KdPrint(("Encrypt failed: 0x%X\n", status));
		goto Cleanup;
	}

	KdPrint(("Encrypted (HEX): "));
	for (int i = 0; i < DATA_LEN; i++)
		KdPrint(("%02X ", encrypted[i]));
	KdPrint(("\n"));


	//
	// 4. Decrypt
	//
	status = CUDecryptAES256(key, encrypted, decrypted);
	if (!NT_SUCCESS(status))
	{
		KdPrint(("Decrypt failed: 0x%X\n", status));
		goto Cleanup;
	}

	// добавляем нуль-терминатор только для печати
	decrypted[DATA_LEN - 1] = '\0';

	KdPrint(("Decrypted: %s\n", decrypted));

Cleanup:

	//
	// 5. Освобождаем память
	//
	if (key)       ExFreePoolWithTag(key, MY_CRYPTO_TAG);
	if (plain)     ExFreePoolWithTag(plain, MY_CRYPTO_TAG);
	if (encrypted) ExFreePoolWithTag(encrypted, MY_CRYPTO_TAG);
	if (decrypted) ExFreePoolWithTag(decrypted, MY_CRYPTO_TAG);

	KdPrint(("=== END AES TEST ===\n"));

	return status;
}


NTSTATUS DriverEntry(
	PDRIVER_OBJECT DriverObject,
	PUNICODE_STRING RegistryPath
)
{
    KdPrint(("Active Hello!\n"));
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
	
	TestCrypto();


	return STATUS_SUCCESS;
}
