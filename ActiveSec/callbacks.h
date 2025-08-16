// callbacks.h
// ƒекларации pre-operation callback'ов.
// —делано так, чтобы callbacks.cpp был изолирован и расшир€ем.

#pragma once

#include <fltKernel.h>

#ifdef __cplusplus
extern "C" {
#endif

    // PreOperation callback'ы Ч экспортируютс€ с "C"-сигнатурой дл€ FltMgr
    FLT_PREOP_CALLBACK_STATUS
        PreCreateCallback(
            _Inout_ PFLT_CALLBACK_DATA Data,
            _In_ PCFLT_RELATED_OBJECTS FltObjects,
            _Outptr_result_maybenull_ PVOID* CompletionContext
        );

    FLT_POSTOP_CALLBACK_STATUS
        PostReadCallback(
            _Inout_ PFLT_CALLBACK_DATA Data,
            _In_ PCFLT_RELATED_OBJECTS FltObjects,
            _In_opt_ PVOID CompletionContext,
            _In_ FLT_POST_OPERATION_FLAGS Flags
        );

    FLT_PREOP_CALLBACK_STATUS
        PreWriteCallback(
            _Inout_ PFLT_CALLBACK_DATA Data,
            _In_ PCFLT_RELATED_OBJECTS FltObjects,
            _Outptr_result_maybenull_ PVOID* CompletionContext
        );

#ifdef __cplusplus
}
#endif
