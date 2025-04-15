#pragma once
#include <ntddk.h>

namespace cutils {
    ULONGLONG GetSystemTimeSeconds();

	unsigned char* AdjustBuffer(PVOID buffer, ULONG bufferLength, ULONG offset, ULONG poolTag = 'cBuf');

}



