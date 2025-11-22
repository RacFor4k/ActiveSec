#pragma once
#include <fltKernel.h>

#define MAX_MSG_SIZE 1024
#define MSG_PORT_NAME L"\\ActiveSec"

#define SHARED_SECTION_NAME L"\\BaseNamedObjects\\ActiveSecMem"
#define SHARED_MEM_SIZE     (16 * 1024 * 1024)

typedef enum _CTX_MSG_TYPE {
    MsgType_LogInfo = 1,    // Пример 1-го вида сообщения (просто лог)
    MsgType_DataReady = 2   // Уведомление: данные лежат в Shared Memory
} CTX_MSG_TYPE;

// Типы сообщений от UM -> Driver
typedef enum _CTX_CMD_TYPE {
	CmdType_Authorize = 1,     // Установка ключа шифрования
	CmdType_GetKey = 2,       // Запрос ключа шифрования
    CmdType_SignalAck = 3   // Сигнал: "Я прочитал Shared Memory, давай дальше"
} CTX_CMD_TYPE;

// Структура ключа (как в задании)
typedef struct _TOKEN_MSG {
    CTX_CMD_TYPE Command;
    unsigned char Key[32];
} TOKEN_MSG, * PTOKEN_MSG;

// Заголовок сообщения от Драйвера к UM
typedef struct _DRIVER_MSG_HEADER {
    CTX_MSG_TYPE Type;
    unsigned long DataSize; // Реальный размер данных в SharedMemory (для DataReady)
    unsigned long TotalSize; // Полный размер исходного буфера
    unsigned long CurrentOffset; // Текущее смещение
} DRIVER_MSG_HEADER, * PDRIVER_MSG_HEADER;

// Заголовок сообщения от UM к Драйверу
typedef struct _USER_MSG_HEADER {
	CTX_CMD_TYPE Command; // 1 - Authorize, 2 - SignalAck
} USER_MSG_HEADER, * PUSER_MSG_HEADER;

// Полное сообщение от UM (входной буфер FilterSendMessage)
typedef struct _USER_MESSAGE {
    USER_MSG_HEADER Header;
    union {
        TOKEN_MSG KeyMsg; // Заполняется если Command == CmdType_SetKey
        // Для CmdType_SignalAck данные не нужны
    } Data;
} USER_MESSAGE, * PUSER_MESSAGE;

//
// Communication
//

NTSTATUS Communication_Init(PFLT_FILTER Filter);

// Очистка ресурсов (при выгрузке драйвера)
VOID Communication_Shutdown();

// Функция для отправки простого сообщения (вид 1)
NTSTATUS Communication_SendMessage(PUNICODE_STRING Message);

// Функция для отправки больших данных (вид 2 + Shared Memory)
// Эта функция не блокирует поток фильтра, она ставит задачу в очередь.
NTSTATUS Communication_QueueBigData(PVOID Buffer, ULONG Length);
 