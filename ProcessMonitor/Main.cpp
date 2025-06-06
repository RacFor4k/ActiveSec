#include <fltKernel.h>
#include "Callbacks.h"

static const GUID KernelProcessGUID =
{ 0x3d6fa8d1, 0xfe05, 0x11d0, {0x9d, 0xda, 0x00, 0xc0, 0x4f, 0xd7, 0xba, 0x7c} };

TRACEHANDLE g_hTrace = 0;

PFLT_FILTER gFilterHandle = NULL;

FLT_OPERATION_REGISTRATION Callbacks[] = {
    { IRP_MJ_READ, 0, MiniFilter::PreReadCallback, nullptr },
    { IRP_MJ_WRITE, 0, MiniFilter::PreWriteCallback, nullptr },
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
    UNREFERENCED_PARAMETER(RegistryPath);

    NTSTATUS status;

    status = PsSetCreateProcessNotifyRoutineEx(CreateProcessNotifyRoutineEx, FALSE);

    status = FltRegisterFilter(DriverObject, &FilterRegistration, &gFilterHandle);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    status = FltStartFiltering(gFilterHandle);
    if (!NT_SUCCESS(status)) {
        FltUnregisterFilter(gFilterHandle);
    }

    return status;
}

NTSTATUS MiniFilterUnload(_In_ FLT_FILTER_UNLOAD_FLAGS Flags)
{
    UNREFERENCED_PARAMETER(Flags);
    
    PsSetCreateProcessNotifyRoutineEx(CreateProcessNotifyRoutineEx, TRUE);
    FltUnregisterFilter(gFilterHandle);
    return STATUS_SUCCESS;
}

