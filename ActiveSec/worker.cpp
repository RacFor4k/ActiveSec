// worker.cpp
// Простая, безопасная реализация generic work-item 'вызвал-забыл'.
// Использует FltAllocateGenericWorkItem, FltQueueGenericWorkItem, FltFreeGenericWorkItem.

#include "worker.h"

#include <ntstrsafe.h> // для безопасного форматирования, при необходимости

//
// Примитивный state: храним указатель на фильтр, чтобы можно было использовать из других мест.
// (Не обязателен, но удобно)
//
static PFLT_FILTER gWorkerFilter = nullptr;

//
// Прототип рабочей рутины для FltQueueGenericWorkItem.
// Она вызывается в контексте системного потока на IRQL == PASSIVE_LEVEL.
// Важно: освобождать FltWorkItem внутри этой функции (или в последующем пути), 
// иначе будет утечка.
//
_Use_decl_annotations_
VOID
WorkerRoutine(
    PFLT_GENERIC_WORKITEM FltWorkItem,
    PVOID FltObject,
    PVOID Context
)
{
    UNREFERENCED_PARAMETER(FltObject); // FltObject — либо PFLT_FILTER, либо PFLT_INSTANCE, по вызову

    if (!Context) {
        Print("Worker: Context is null");
    }
    else {
        NTSTATUS status = CommSendMessageToUser(Context, sizeof(KM_MESSAGE));
        if (!NT_SUCCESS(status)) {
            Print("Worker: error while sending message: 0x%08X", status);
        }
        ExFreePool(Context);
    }

    // Освобождаем work item, когда всё сделано.
    if (FltWorkItem) {
        FltFreeGenericWorkItem(FltWorkItem);
    }
}

NTSTATUS
WorkerInitialize(
    _In_ PFLT_FILTER Filter
)
{
    if (Filter == nullptr) {
        return STATUS_INVALID_PARAMETER;
    }

    // Просто сохраняем ссылку; не увеличиваем ссылку в Filter Manager'е (PFLT_FILTER — opaque).
    // При выгрузке фильтра нужно убедиться, что вызывается WorkerUninitialize до FltUnregisterFilter.
    gWorkerFilter = Filter;

    Print("Worker: initialized, Filter=%p\n", Filter);
    return STATUS_SUCCESS;
}

VOID
WorkerUninitialize()
{
    // Здесь можно добавить ожидание завершения фоновых задач/синхронизацию, если требуется.
    // Т.к. мы освобождаем work-item внутри рутины, и не храним пул, достаточно очистить ссылку.
    gWorkerFilter = nullptr;
    Print("Worker: uninitialized\n");
}

NTSTATUS
WorkerQueueWorkItemFromFilter(
    _In_ PFLT_FILTER Filter,
    _In_opt_ PVOID Context,
    _In_ WORK_QUEUE_TYPE QueueType
)
{
    UNREFERENCED_PARAMETER(Context);

    if (Filter == nullptr) {
        return STATUS_INVALID_PARAMETER;
    }

    // Выделяем generic work item.
    PFLT_GENERIC_WORKITEM workItem = FltAllocateGenericWorkItem();
    if (workItem == nullptr) {
        Print("Worker: FltAllocateGenericWorkItem failed (OOM)\n");
        return STATUS_INSUFFICIENT_RESOURCES;
    }

    // Ставим в очередь; FltObject передаём Filter (можно передать instance при необходимости).
    NTSTATUS status = FltQueueGenericWorkItem(
        workItem,
        Filter,           // FltObject — opaque, может быть Filter или Instance
        WorkerRoutine,    // worker routine
        QueueType,        // DelayedWorkQueue / CriticalWorkQueue
        Context           // optional context, попадёт в WorkerRoutine
    );

    if (!NT_SUCCESS(status)) {
        // Если не удалось поставить в очередь (например, фильтр выгружается), надо освободить workItem.
        Print("Worker: FltQueueGenericWorkItem failed 0x%08X\n", status);
        FltFreeGenericWorkItem(workItem);
        return status;
    }

    // Успех — работа поставлена в очередь, мы «вызвал-забыл».
    return STATUS_SUCCESS;
}
