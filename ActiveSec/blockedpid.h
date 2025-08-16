#pragma once
#include <fltKernel.h>

#ifdef __cplusplus
extern "C" {
#endif

	// Инициализация/деинициализация
	NTSTATUS BlockedPIDInitialize();
	VOID BlockedPIDUninitialize();

	// Добавление PID (если уже есть — пропускаем)
	NTSTATUS BlockedPIDAdd(_In_ UINT64 pid);

	// Удаление PID (если нет — пропускаем)
	NTSTATUS BlockedPIDRemove(_In_ UINT64 pid);

	// Поиск PID (возвращает TRUE если найден)
	BOOLEAN BlockedPIDFind(_In_ UINT64 pid);

#ifdef __cplusplus
}
#endif
