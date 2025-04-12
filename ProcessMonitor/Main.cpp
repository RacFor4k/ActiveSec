#include <fltKernel.h>
#include "..\ActiveSec\Callbacks.h"

PFLT_FILTER gFilterHandle = NULL;

FLT_OPERATION_REGISTRATION Callbacks[] = {
    {
        IRP_MJ_CREATE,
        0,
        nullptr,          // Pre-operation callback
        nullptr           // Post-operation callback
    },
    { IRP_MJ_READ, 0, MiniFilter::PreReadCallback, nullptr},
    {IRP_MJ_WRITE, 0, MiniFilter::PreWriteCallback, nullptr}
    { IRP_MJ_OPERATION_END }
};

const FLT_REGISTRATION FilterRegistration = {
    sizeof(FLT_REGISTRATION),         // Size
    FLT_REGISTRATION_VERSION,         // Version
    0,                                // Flags
    nullptr,                          // Contexts
    Callbacks,                        // Operation callbacks
    MiniFilterUnload,                 // MiniFilterUnload
    nullptr,                          // InstanceSetup
    nullptr,                          // InstanceQueryTeardown
    nullptr,                          // InstanceTeardownStart
    nullptr,                          // InstanceTeardownComplete
    nullptr,                          // GenerateFileName
    nullptr,                          // GenerateDestinationFileName
    nullptr                           // NormalizeNameComponent
};

NTSTATUS DriverEntry(PDRIVER_OBJECT DriverObject, PUNICODE_STRING RegistryPath) {
	NTSTATUS status;
	PFLT_PORT serverPort = NULL;

	status = FltRegisterFilter(DriverObject, &FilterRegistration, &gFilterHandle)
}