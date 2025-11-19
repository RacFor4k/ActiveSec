// comm.cpp
#include "comm.h"
#include "blockedpid.h"
#include <ntstrsafe.h>

static PFLT_PORT gServerPort = nullptr;
static PFLT_PORT gClientPort = nullptr;
static PFLT_FILTER gCommFilter = nullptr;

//
// Прототипы
//
static NTSTATUS
CommConnect(
    _In_ PFLT_PORT ClientPort,
    _In_opt_ PVOID ServerPortCookie,
    _In_reads_bytes_opt_(SizeOfContext) PVOID ConnectionContext,
    _In_ ULONG SizeOfContext,
    _Outptr_result_maybenull_ PVOID* ConnectionPortCookie
);

static VOID
CommDisconnect(
    _In_opt_ PVOID ConnectionCookie
);

static NTSTATUS
CommMessage(
    _In_opt_ PVOID PortCookie,
    _In_reads_bytes_opt_(InputBufferSize) PVOID InputBuffer,
    _In_ ULONG InputBufferSize,
    _Out_writes_bytes_to_opt_(OutputBufferSize, *ReturnOutputBufferLength) PVOID OutputBuffer,
    _In_ ULONG OutputBufferSize,
    _Out_ PULONG ReturnOutputBufferLength
);

NTSTATUS CommInitialize(
    _In_ PFLT_FILTER Filter,
    _In_ PCUNICODE_STRING PortName
)
{
    gCommFilter = Filter;

    PSECURITY_DESCRIPTOR sd;
    RtlCreateSecurityDescriptor(&sd, SECURITY_DESCRIPTOR_REVISION);

    NTSTATUS status = FltBuildDefaultSecurityDescriptor(&sd, FLT_PORT_ALL_ACCESS);
    if (!NT_SUCCESS(status)) {
        Print("Comm: FltBuildDefaultSecurityDescriptor failed 0x%08X\n", status);
    }
    OBJECT_ATTRIBUTES oa;
    InitializeObjectAttributes(&oa,
        (PUNICODE_STRING)PortName,
        OBJ_CASE_INSENSITIVE | OBJ_KERNEL_HANDLE,
        nullptr,
        sd);

    status = FltCreateCommunicationPort(
        Filter,
        &gServerPort,
        &oa,
        nullptr,            // ServerPortCookie
        CommConnect,        // ConnectNotifyCallback
        CommDisconnect,     // DisconnectNotifyCallback
        CommMessage,        // MessageNotifyCallback
        1                   // MaxConnections
    );

    FltFreeSecurityDescriptor(sd);

    if (!NT_SUCCESS(status)) {
        Print("Comm: FltCreateCommunicationPort failed 0x%08X\n", status);
    }
    else {
        Print("Comm: Port created: %wZ\n", PortName);
    }

    return status;
}

VOID CommUninitialize()
{
    if (gClientPort) {
        FltCloseClientPort(gCommFilter, &gClientPort);
        gClientPort = nullptr;
    }

    if (gServerPort) {
        FltCloseCommunicationPort(gServerPort);
        gServerPort = nullptr;
    }
    gCommFilter = nullptr;

    Print("Comm: Uninitialized\n");
}

NTSTATUS CommSendMessageToUser(
    _In_reads_bytes_(MessageSize) PVOID Message,
    _In_ ULONG MessageSize
)
{
    Print("MessageSize: %u", MessageSize)
    if (!gClientPort) {
        return STATUS_PORT_DISCONNECTED;
    }
    
    LARGE_INTEGER timeout;
    timeout.QuadPart = -10 * 1000 * 1000; // 1 сек в 100-нс единицах (отриц. => относительное время)

    ULONG bytesReturned = 0;
    NTSTATUS status = FltSendMessage(
        gCommFilter,
        &gClientPort,
        Message,
        MessageSize,
        nullptr,
        &bytesReturned,
        &timeout
    );

    if (!NT_SUCCESS(status)) {
        Print("Comm: FltSendMessage failed 0x%08X\n", status);
    }

    return status;
}

//
// Callbacks
//
static NTSTATUS
CommConnect(
    _In_ PFLT_PORT ClientPort,
    _In_opt_ PVOID ServerPortCookie,
    _In_reads_bytes_opt_(SizeOfContext) PVOID ConnectionContext,
    _In_ ULONG SizeOfContext,
    _Outptr_result_maybenull_ PVOID* ConnectionPortCookie
)
{
    UNREFERENCED_PARAMETER(ServerPortCookie);
    UNREFERENCED_PARAMETER(ConnectionContext);
    UNREFERENCED_PARAMETER(SizeOfContext);
    UNREFERENCED_PARAMETER(ConnectionPortCookie);

    gClientPort = ClientPort;
    Print("Comm: Client connected\n");

    return STATUS_SUCCESS;
}

static VOID
CommDisconnect(
    _In_opt_ PVOID ConnectionCookie
)
{
    UNREFERENCED_PARAMETER(ConnectionCookie);

    FltCloseClientPort(gCommFilter, &gClientPort);
    gClientPort = nullptr;

    Print("Comm: Client disconnected\n");
}

static NTSTATUS
CommMessage(
    _In_opt_ PVOID PortCookie,
    _In_reads_bytes_opt_(InputBufferSize) PVOID InputBuffer,
    _In_ ULONG InputBufferSize,
    _Out_writes_bytes_to_opt_(OutputBufferSize, *ReturnOutputBufferLength) PVOID OutputBuffer,
    _In_ ULONG OutputBufferSize,
    _Out_ PULONG ReturnOutputBufferLength
)
{
    UNREFERENCED_PARAMETER(OutputBuffer);
    UNREFERENCED_PARAMETER(OutputBufferSize);
    UNREFERENCED_PARAMETER(PortCookie);

    //Print("Comm: Received message from user-mode (%lu bytes)\n", InputBufferSize);
    NTSTATUS status;
    if (InputBuffer && InputBufferSize >= sizeof(UM_MESSAGE)) {
        PUM_MESSAGE msg = (PUM_MESSAGE)InputBuffer;
        if (msg->Type == 0) {
            status = BlockedPIDAdd(msg->Pid);
            if (!NT_SUCCESS(status))
                return status;
        }
        else if (msg->Type == 1) {
            status = BlockedPIDRemove(msg->Pid);
            if (!NT_SUCCESS(status))
                return status;
        }
    }

    *ReturnOutputBufferLength = 0;
    return STATUS_SUCCESS;
}
