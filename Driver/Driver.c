#include <FltKernel.h>
#include <ntstrsafe.h>
#include "Callbacks.h"
#include "CryptoUtils.h"
#include "Communication.h"

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
	Communication_Shutdown();
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
		KdPrint(("FltRegisterFilter failed: 0x%X\n", status));
		return status;
	}
	status = FltStartFiltering(gFilterData.FilterHandle);
	if (!NT_SUCCESS(status)) {
		KdPrint(("FltStartFiltering failed: 0x%X\n", status));
		FltUnregisterFilter(gFilterData.FilterHandle);
		return status;
	}
	status = Communication_Init(gFilterData.FilterHandle);
	if (!NT_SUCCESS(status)) {
		KdPrint(("Communication_Init failed: 0x%X\n", status));
		FltUnregisterFilter(gFilterData.FilterHandle);
		return status;
	}
	KdPrint(("Driver loaded successfully\n"));
	return STATUS_SUCCESS;
}
