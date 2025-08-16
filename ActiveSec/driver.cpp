// driver.cpp
// Основной модуль — регистрация/отмена регистрации фильтра, экспорт DriverEntry и unload.
// Собран как C++ файл, но с extern "C" для точек входа, требуемых WDK.

#include <fltKernel.h>
#include <ntstrsafe.h>
#include "callbacks.h"
#include "worker.h"
#include "comm.h"
#include "blockedpid.h"
#include "common.h"

//
// Глобальный хендл фильтра
//
PFLT_FILTER gFilterHandle = nullptr;

//
// Регистрация pre-operation callback'ов.
// Мы используем массив FLT_OPERATION_REGISTRATION и затем FLT_REGISTRATION,
// как в примерах Microsoft (PassThrough / samples).
//
CONST FLT_OPERATION_REGISTRATION Callbacks[] = {
    { IRP_MJ_CREATE,
      0,
      PreCreateCallback,
      nullptr },

    { IRP_MJ_READ,
      0,
      nullptr,
      PostReadCallback },

    { IRP_MJ_WRITE,
      0,
      PreWriteCallback,
      nullptr },

      // Конец массива
      { IRP_MJ_OPERATION_END }
};


NTSTATUS
FilterUnload(
    _In_ FLT_FILTER_UNLOAD_FLAGS Flags
) {
    UNREFERENCED_PARAMETER(Flags);
    if (gFilterHandle != nullptr) {
        // Отключаем фильтр
        FltUnregisterFilter(gFilterHandle);
        gFilterHandle = nullptr;
    }
    WorkerUninitialize();
    BlockedPIDUninitialize();
    CommUninitialize();

    Print("FLT unloaded\n");
    return STATUS_SUCCESS;
}

NTSTATUS
NullQueryTeardown(
    _In_ PCFLT_RELATED_OBJECTS FltObjects,
    _In_ FLT_INSTANCE_QUERY_TEARDOWN_FLAGS Flags
) {
    UNREFERENCED_PARAMETER(FltObjects);
    UNREFERENCED_PARAMETER(Flags);
    return STATUS_SUCCESS;
}

//
// Основная регистрационная структура фильтра.
// Можно расширять флагами, контекстами, callback'ами для instance attach/detach и т.д.
//
CONST FLT_REGISTRATION FilterRegistration = {
    sizeof(FLT_REGISTRATION),     // Size
    FLT_REGISTRATION_VERSION,     // Version
    0,                            // Flags
    nullptr,                      // ContextRegistration
    Callbacks,                    // OperationRegistration
    FilterUnload,                      // FilterUnload
    nullptr,                      // InstanceSetup
    NullQueryTeardown,                      // InstanceQueryTeardown
    nullptr,                      // InstanceTeardownStart
    nullptr,                      // InstanceTeardownComplete
    nullptr,                      // GenerateFileName
    nullptr,                      // NormalizeNameComponent
    nullptr,                      // NormalizeContextCleanup
    nullptr,                      // TransactionNotify
    nullptr,                      // NormalizeNameComponentEx
    nullptr                       // SectionNotification
};

extern "C"
NTSTATUS
DriverEntry(
    _In_ PDRIVER_OBJECT DriverObject,
    _In_ PUNICODE_STRING RegistryPath
)
{
    UNREFERENCED_PARAMETER(RegistryPath);

    NTSTATUS status = STATUS_SUCCESS;

    __try {
        Print("KM_MESSAGE size: %zu\n", sizeof(KM_MESSAGE))
        // Регистрируем фильтр у Filter Manager
        status = FltRegisterFilter(DriverObject, &FilterRegistration, &gFilterHandle);
        if (!NT_SUCCESS(status)) {
            Print("FltRegisterFilter failed 0x%08X", status);
            __leave;
        }

        status = BlockedPIDInitialize();
        if (!NT_SUCCESS(status))
        {
            Print("BlockedPIDInitialize failed 0x%08X", status);
            __leave;
        }

        status = WorkerInitialize(gFilterHandle);
        if (!NT_SUCCESS(status))
        {
            Print("WorkerInitialize failed 0x%08X", status);
            __leave;
        }

        UNICODE_STRING PortName;
        RtlCreateUnicodeString(&PortName, PORT_NAME);
        status = CommInitialize(gFilterHandle, &PortName);
        RtlFreeUnicodeString(&PortName);
        if (!NT_SUCCESS(status))
        {
            Print("CommInitialize failed 0x%08X", status);
            __leave;
        }

        // Начинаем фильтрацию
        status = FltStartFiltering(gFilterHandle);
        if (!NT_SUCCESS(status)) {
            Print("FltStartFiltering failed 0x%08X", status);
            // Если старт не удался, отменим регистрацию
            FltUnregisterFilter(gFilterHandle);
            gFilterHandle = nullptr;
            __leave;
        }

        Print("loaded and filtering\n");
    }
    __finally {
        // ничего дополнительного
    }

    return status;
}


extern "C"
NTSTATUS
DriverUnload(
    _In_ PDRIVER_OBJECT DriverObject
)
{
    UNREFERENCED_PARAMETER(DriverObject);

    if (gFilterHandle != nullptr) {
        // Отключаем фильтр
        FltUnregisterFilter(gFilterHandle);
        gFilterHandle = nullptr;
    }

    WorkerUninitialize();

    Print("unloaded\n");
    return STATUS_SUCCESS;
}

// В некоторых сборках требуется экспорт Unload через DriverObject.
// Если вы используете DriverEntry, в INF/INF-проекте укажите DriverUnload корректно.
// Здесь также можно добавить команду для установки DriverObject->DriverUnload = DriverUnload,
// но FltRegisterFilter/DriverEntry модель часто подразумевает явное использование DriverUnload.
