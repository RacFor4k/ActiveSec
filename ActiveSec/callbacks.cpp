// callbacks.cpp
// Реализация заглушек PreCreate/PreRead/PreWrite.
// На будущее: сюда удобно добавить фильтрацию на основе контекстов,
// очередей для асинхронной обработки, логирование, обмен с user-mode и т.д.

#include "callbacks.h"
#include "worker.h"
#include <ntifs.h>

FLT_PREOP_CALLBACK_STATUS
PreCreateCallback(
    _Inout_ PFLT_CALLBACK_DATA Data,
    _In_ PCFLT_RELATED_OBJECTS FltObjects,
    _Outptr_result_maybenull_ PVOID* CompletionContext
)
{
    UNREFERENCED_PARAMETER(Data);
    UNREFERENCED_PARAMETER(CompletionContext);
    if (CompletionContext)
        CompletionContext = nullptr;

    PKM_MESSAGE log = (PKM_MESSAGE)ExAllocatePool2(POOL_FLAG_NON_PAGED, sizeof(KM_MESSAGE), AS_TAG);
    if (!log) {
        Print("PreCreate: cannot allocate memory for log");
        return FLT_PREOP_SUCCESS_NO_CALLBACK;
    }
    RtlIsZeroMemory(log, sizeof(KM_MESSAGE));
    log->Pid = (UINT64)PsGetCurrentProcessId();
    log->Type = 0; // create
    log->BufferLength = 0;
    // Получение пути файла
    if (FltObjects->FileObject && FltObjects->FileObject->FileName.Length < sizeof(log->FilePath)) {
        RtlCopyMemory(log->FilePath, FltObjects->FileObject->FileName.Buffer, FltObjects->FileObject->FileName.Length);
        log->FilePath[FltObjects->FileObject->FileName.Length / sizeof(WCHAR)] = L'\0';
    }

    WorkerQueueWorkItemFromFltObjects(FltObjects, log);

    // TODO: здесь можно добавить асинхронную отправку в worker

    return FLT_PREOP_SUCCESS_NO_CALLBACK;
}


FLT_POSTOP_CALLBACK_STATUS
PostReadCallback(
    _Inout_ PFLT_CALLBACK_DATA Data,
    _In_ PCFLT_RELATED_OBJECTS FltObjects,
    _In_opt_ PVOID CompletionContext,
    _In_ FLT_POST_OPERATION_FLAGS Flags
)
{
    UNREFERENCED_PARAMETER(Flags);
    UNREFERENCED_PARAMETER(CompletionContext);

    PKM_MESSAGE log = (PKM_MESSAGE)ExAllocatePool2(POOL_FLAG_NON_PAGED, sizeof(KM_MESSAGE), AS_TAG);
    if (!log) {
        Print("PostRead: cannot allocate memory for log");
        return FLT_POSTOP_FINISHED_PROCESSING;
    }
    RtlIsZeroMemory(log, sizeof(KM_MESSAGE));
    log->Pid = (UINT64)PsGetCurrentProcessId();
    log->Type = 1; // read

    // Файл
    if (FltObjects->FileObject && FltObjects->FileObject->FileName.Length < sizeof(log->FilePath)) {
        RtlCopyMemory(log->FilePath, FltObjects->FileObject->FileName.Buffer, FltObjects->FileObject->FileName.Length);
        log->FilePath[FltObjects->FileObject->FileName.Length / sizeof(WCHAR)] = L'\0';
    }

    // Смещение и длина
    log->Offset = (ULONG)Data->Iopb->Parameters.Read.ByteOffset.QuadPart;
    log->BufferLength = min((ULONG)Data->IoStatus.Information, MAX_LOG_BUFFER_LEN);

    // Копируем прочитанные данные
    if (log->BufferLength > 0 && Data->Iopb->TargetFileObject) {
        // Безопасное копирование
        __try {
            PVOID sourceBuffer = nullptr;

            // Buffered I/O
            if (Data->Iopb->TargetFileObject && Data->Iopb->Parameters.Read.MdlAddress == nullptr) {
                sourceBuffer = Data->Iopb->Parameters.Read.ReadBuffer;
            }
            // Direct I/O
            else if (Data->Iopb->Parameters.Read.MdlAddress) {
                sourceBuffer = MmGetSystemAddressForMdlSafe(Data->Iopb->Parameters.Read.MdlAddress, NormalPagePriority);
            }

            if (sourceBuffer) {
                RtlCopyMemory(log->Buffer, sourceBuffer, log->BufferLength);
            }
        }
        __except (EXCEPTION_EXECUTE_HANDLER) {
            log->BufferLength = 0;
        }
    }

    WorkerQueueWorkItemFromFltObjects(FltObjects, log);
    // TODO: асинхронная отправка log

    return FLT_POSTOP_FINISHED_PROCESSING;
}


FLT_PREOP_CALLBACK_STATUS
PreWriteCallback(
    _Inout_ PFLT_CALLBACK_DATA Data,
    _In_ PCFLT_RELATED_OBJECTS FltObjects,
    _Outptr_result_maybenull_ PVOID* CompletionContext
)
{
    UNREFERENCED_PARAMETER(FltObjects);
    UNREFERENCED_PARAMETER(CompletionContext);
    if (CompletionContext)
        CompletionContext = nullptr;

    PKM_MESSAGE log = (PKM_MESSAGE)ExAllocatePool2(POOL_FLAG_NON_PAGED, sizeof(KM_MESSAGE), AS_TAG);
    if (!log) {
        Print("PreWrite: cannot allocate memory for log");
        return FLT_PREOP_SUCCESS_NO_CALLBACK;
    }
    RtlIsZeroMemory(log, sizeof(KM_MESSAGE));
    log->Pid = (UINT64)PsGetCurrentProcessId();
    log->Type = 1; // read

    // Файл
    if (FltObjects->FileObject && FltObjects->FileObject->FileName.Length < sizeof(log->FilePath)) {
        RtlCopyMemory(log->FilePath, FltObjects->FileObject->FileName.Buffer, FltObjects->FileObject->FileName.Length);
        log->FilePath[FltObjects->FileObject->FileName.Length / sizeof(WCHAR)] = L'\0';
    }

    // Смещение и длина
    log->Offset = (ULONG)Data->Iopb->Parameters.Read.ByteOffset.QuadPart;
    log->BufferLength = min((ULONG)Data->IoStatus.Information, MAX_LOG_BUFFER_LEN);

    // Копируем прочитанные данные
    if (log->BufferLength > 0 && Data->Iopb->TargetFileObject) {
        // Безопасное копирование
        __try {
            PVOID sourceBuffer = nullptr;

            // Buffered I/O
            if (Data->Iopb->TargetFileObject && Data->Iopb->Parameters.Write.MdlAddress == nullptr) {
                sourceBuffer = Data->Iopb->Parameters.Write.WriteBuffer;
            }
            // Direct I/O
            else if (Data->Iopb->Parameters.Write.MdlAddress) {
                sourceBuffer = MmGetSystemAddressForMdlSafe(Data->Iopb->Parameters.Write.MdlAddress, NormalPagePriority);
            }

            if (sourceBuffer) {
                RtlCopyMemory(log->Buffer, sourceBuffer, log->BufferLength);
            }
        }
        __except (EXCEPTION_EXECUTE_HANDLER) {
            log->BufferLength = 0;
        }
    }
    
    WorkerQueueWorkItemFromFltObjects(FltObjects, log);
    return FLT_PREOP_SUCCESS_NO_CALLBACK;
}
