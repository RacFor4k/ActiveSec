// worker.h
#pragma once

#include <fltKernel.h>
#include "comm.h"

#ifdef __cplusplus
extern "C" {
#endif

    // »нициализаци€ worker-модул€.
    // ѕередаЄм PFLT_FILTER (получен при FltRegisterFilter / DriverEntry).
    NTSTATUS WorkerInitialize(_In_ PFLT_FILTER Filter);

    // «авершение работы worker-модул€. ∆дЄт ли строго завершени€ Ч тут просто флаг/clean-up.
    VOID WorkerUninitialize();

    // QueueType Ч WORK_QUEUE_TYPE (CriticalWorkQueue / DelayedWorkQueue).
    // Context Ч указатель, который будет получен в WorkerRoutine. ћожно передавать структуру данных.
    // Ёта функци€ реализует "вызвал Ч забыл": выдел€ет work item, помещает в очередь и возвращает результат.
    NTSTATUS WorkerQueueWorkItemFromFilter(
        _In_ PFLT_FILTER Filter,
        _In_opt_ PVOID Context,
        _In_ WORK_QUEUE_TYPE QueueType = DelayedWorkQueue
    );

    // ”добна€ обЄртка, принимающа€ FltObjects из callback'а (Pre* callback'ы получают PCFLT_RELATED_OBJECTS).
    inline NTSTATUS WorkerQueueWorkItemFromFltObjects(
        _In_ PCFLT_RELATED_OBJECTS FltObjects,
        _In_opt_ PVOID Context,
        _In_ WORK_QUEUE_TYPE QueueType = DelayedWorkQueue
    )
    {
        if (FltObjects == nullptr) {
            return STATUS_INVALID_PARAMETER;
        }
        return WorkerQueueWorkItemFromFilter(FltObjects->Filter, Context, QueueType);
    }

#ifdef __cplusplus
}
#endif
