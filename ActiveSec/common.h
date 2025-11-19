#pragma once

#define AS_TAG 'ceSA' //Представляется как ASec - ActiveSec

#define MAX_LOG_BUFFER_LEN 10*1024 //максимальная длина логируемого буфера 10KiB

#define PORT_NAME L"\\ActiveSec"

#define Print(format, ...) \
    { \
        LARGE_INTEGER currentTime; \
        KeQuerySystemTime(&currentTime); \
        ULONG activeSec = (ULONG)(currentTime.QuadPart / 10000000ULL) % 60; \
        DbgPrint("ActiveSec: [%lu] " format, activeSec, __VA_ARGS__); \
    }
