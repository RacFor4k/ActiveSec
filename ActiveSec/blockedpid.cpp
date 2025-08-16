#include "blockedpid.h"
#include "common.h"

typedef struct _PID_ENTRY {
    LIST_ENTRY List;
    UINT64 Pid;
} PID_ENTRY, * PPID_ENTRY;

static LIST_ENTRY gBlockedPIDList;
static ERESOURCE gBlockedPIDLock;
static BOOLEAN gBlockedPIDInitialized = FALSE;

NTSTATUS BlockedPIDInitialize()
{
    if (gBlockedPIDInitialized) {
        return STATUS_SUCCESS;
    }

    InitializeListHead(&gBlockedPIDList);
    NTSTATUS status = ExInitializeResourceLite(&gBlockedPIDLock);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    gBlockedPIDInitialized = TRUE;
    return STATUS_SUCCESS;
}

VOID BlockedPIDUninitialize()
{
    if (!gBlockedPIDInitialized) {
        return;
    }

    // Очистка списка
    ExAcquireResourceExclusiveLite(&gBlockedPIDLock, TRUE);
    while (!IsListEmpty(&gBlockedPIDList)) {
        PLIST_ENTRY entry = RemoveHeadList(&gBlockedPIDList);
        PPID_ENTRY pidEntry = CONTAINING_RECORD(entry, PID_ENTRY, List);
        ExFreePool(pidEntry);
    }
    ExReleaseResourceLite(&gBlockedPIDLock);

    ExDeleteResourceLite(&gBlockedPIDLock);
    gBlockedPIDInitialized = FALSE;
}

NTSTATUS BlockedPIDAdd(_In_ UINT64 pid)
{
    if (!gBlockedPIDInitialized) {
        return STATUS_INVALID_DEVICE_STATE;
    }

    // Проверим, есть ли уже
    ExAcquireResourceSharedLite(&gBlockedPIDLock, TRUE);
    for (PLIST_ENTRY e = gBlockedPIDList.Flink; e != &gBlockedPIDList; e = e->Flink) {
        PPID_ENTRY item = CONTAINING_RECORD(e, PID_ENTRY, List);
        if (item->Pid == pid) {
            ExReleaseResourceLite(&gBlockedPIDLock);
            return STATUS_SUCCESS; // уже есть — выходим
        }
    }
    ExReleaseResourceLite(&gBlockedPIDLock);

    // Добавим (эксклюзивно)
    PPID_ENTRY newEntry = (PPID_ENTRY)ExAllocatePool2(POOL_FLAG_NON_PAGED, sizeof(PID_ENTRY), AS_TAG);
    if (!newEntry) {
        return STATUS_INSUFFICIENT_RESOURCES;
    }
    newEntry->Pid = pid;
    InitializeListHead(&newEntry->List);

    ExAcquireResourceExclusiveLite(&gBlockedPIDLock, TRUE);
    InsertTailList(&gBlockedPIDList, &newEntry->List);
    ExReleaseResourceLite(&gBlockedPIDLock);

    return STATUS_SUCCESS;
}

NTSTATUS BlockedPIDRemove(_In_ UINT64 pid)
{
    if (!gBlockedPIDInitialized) {
        return STATUS_INVALID_DEVICE_STATE;
    }

    ExAcquireResourceExclusiveLite(&gBlockedPIDLock, TRUE);
    for (PLIST_ENTRY e = gBlockedPIDList.Flink; e != &gBlockedPIDList; e = e->Flink) {
        PPID_ENTRY item = CONTAINING_RECORD(e, PID_ENTRY, List);
        if (item->Pid == pid) {
            RemoveEntryList(e);
            ExFreePool(item);
            ExReleaseResourceLite(&gBlockedPIDLock);
            return STATUS_SUCCESS;
        }
    }
    ExReleaseResourceLite(&gBlockedPIDLock);
    return STATUS_SUCCESS; // не нашли — просто выходим
}

BOOLEAN BlockedPIDFind(_In_ UINT64 pid)
{
    if (!gBlockedPIDInitialized) {
        return FALSE;
    }

    BOOLEAN found = FALSE;
    ExAcquireResourceSharedLite(&gBlockedPIDLock, TRUE);
    for (PLIST_ENTRY e = gBlockedPIDList.Flink; e != &gBlockedPIDList; e = e->Flink) {
        PPID_ENTRY item = CONTAINING_RECORD(e, PID_ENTRY, List);
        if (item->Pid == pid) {
            found = TRUE;
            break;
        }
    }
    ExReleaseResourceLite(&gBlockedPIDLock);
    return found;
}
