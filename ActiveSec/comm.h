// comm.h
#pragma once

#include <fltKernel.h>
#include "common.h"

#ifdef __cplusplus
extern "C" {
#endif

#pragma pack(push, 1)
    typedef struct _KM_MESSAGE {
        ULONG Type;
        WCHAR ProccessPath[260];
        WCHAR FilePath[260];
        ULONG Offset;
        ULONG BufferLength;
        CHAR Buffer[MAX_LOG_BUFFER_LEN];
    } KM_MESSAGE, * PKM_MESSAGE;

    typedef struct _UM_MESSAGE {
        WCHAR ProcessPath[260];
        ULONG Type;
    } UM_MESSAGE, * PUM_MESSAGE;
#pragma pack(pop)
    NTSTATUS CommInitialize(
        _In_ PFLT_FILTER Filter,
        _In_ PCUNICODE_STRING PortName
    );

    VOID CommUninitialize();

    NTSTATUS CommSendMessageToUser(
        _In_reads_bytes_(MessageSize) PVOID Message,
        _In_ ULONG MessageSize
    );

#ifdef __cplusplus
}
#endif
