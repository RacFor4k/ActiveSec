#include <minifilter.h>
#include <fltKernel.h>
#include <iostream>
#include <string>

PFLT_FILTER gFilterHandle;

PUNICODE_STRING TargetFile;

NTSTATUS MiniFilterInstanceSetup(
	_In_ PCFLT_RELATED_OBJECTS FltObjects,
	_In_ FLT_INSTANCE_SETUP_FLAGS Flags,
	_In_ DEVICE_TYPE VolumeDeviceType,
	_In_ FLT_FILESYSTEM_TYPE VolumeFilesystemType
)
{
	RtlInitUnicodeString(TargetFile, L"example.txt");

	UNREFERENCED_PARAMETER(FltObjects);
	UNREFERENCED_PARAMETER(Flags);
	UNREFERENCED_PARAMETER(VolumeDeviceType);
	UNREFERENCED_PARAMETER(VolumeFilesystemType);

	return STATUS_SUCCESS;
}

FLT_PREOP_CALLBACK_STATUS PreWriteCallback(
	_Inout_ PFLT_CALLBACK_DATA Data,
	_In_ PCFLT_RELATED_OBJECTS FltObjects,
	_Outptr_opt_result_maybenull_ PVOID* CompletionContext
)
{
	UNREFERENCED_PARAMETER(CompletionContext);
	if (Data->Iopb->TargetFileObject && FltObjects->FileObject) {
		PFLT_FILE_NAME_INFORMATION nameInfo;
		NTSTATUS status = FltGetFileNameInformation(Data, FLT_FILE_NAME_NORMALIZED | FLT_FILE_NAME_QUERY_DEFAULT, &nameInfo);
		
		if (NT_SUCCESS(status)) {
			FltParseFileNameInformation(nameInfo);

			if (RtlCompareUnicodeString(&nameInfo->FinalComponent, TargetFile, TRUE) == 0) {
				DbgPrint("File write event");
			}
			FltReleaseFileNameInformation(nameInfo);

		}
	}

	return FLT_PREOP_SUCCESS_NO_CALLBACK;
}

const FLT_OPERATION_REGISTRATION Callbacks[] = {
	{ IRP_MJ_WRITE, 0, PreWriteCallback, nullptr},
	{IRP_MJ_OPERATION_END}
};

const FLT_REGISTRATION FilterRegistration = {
	sizeof(FLT_REGISTRATION),
	FLT_REGISTRATION_VERSION,
	0,                         // Flags
	nullptr,                   // Context
	Callbacks,                 // Operation callbacks
	DriverUnload,              // MiniFilterUnload
	MiniFilterInstanceSetup,   // InstanceSetup
	nullptr,                   // InstanceQueryTeardown
	nullptr,                   // InstanceTeardownStart
	nullptr,                   // InstanceTeardownComplete
	nullptr,                   // GenerateFileName
	nullptr,                   // GenerateDestinationFileName
	nullptr                    // NormalizeNameComponent
};

extern "C"
NTSTATUS DriveEntry(
	_In_ PDRIVER_OBJECT DriverObject,
	_In_ PUNICODE_STRING RegistryPath
) {
	UNREFERENCED_PARAMETER(RegistryPath);
	return FltRegisterFilter(DriverObject, &FilterRegistration, &gFilterHandle) == STATUS_SUCCESS ? 
	FltStartFiltering(gFilterHandle) : STATUS_UNSUCCESSFUL;
}

extern "C"
NTSTATUS 