#include "cutils.h"

ULONGLONG cutils::GetSystemTimeSeconds()
{
    LARGE_INTEGER systemTime;
    KeQuerySystemTime(&systemTime); // врем€ в 100-нс интервалах с 1601 года

    // ѕереводим в секунды (1 сек = 10,000,000 * 100нс)
    return systemTime.QuadPart / 10000000;
}

unsigned char* cutils::AdjustBuffer(PVOID buffer, ULONG bufferLength, ULONG offset, ULONG poolTag = 'cBuf')
{
    const ULONG MAX_LENGTH = 256;
    unsigned char* byteBuffer = static_cast<unsigned char*>(buffer);

    if (bufferLength < MAX_LENGTH)
    {
        unsigned char* newBuffer = static_cast<unsigned char*>(
            ExAllocatePoolWithTag(NonPagedPoolNx, MAX_LENGTH, poolTag)
            );
        if (!newBuffer) return nullptr;

        RtlCopyMemory(newBuffer, byteBuffer, bufferLength);
        RtlZeroMemory(newBuffer + bufferLength, MAX_LENGTH - bufferLength);

        return newBuffer;
    }

    if (bufferLength == MAX_LENGTH)
    {
        // ¬ернуть копию, т.к. нельз€ довер€ть исходному буферу
        unsigned char* newBuffer = static_cast<unsigned char*>(
            ExAllocatePoolWithTag(NonPagedPoolNx, MAX_LENGTH, poolTag)
            );
        if (!newBuffer) return nullptr;

        RtlCopyMemory(newBuffer, byteBuffer, MAX_LENGTH);
        return newBuffer;
    }

    if (bufferLength > MAX_LENGTH)
    {
        unsigned char* newBuffer = static_cast<unsigned char*>(
            ExAllocatePoolWithTag(NonPagedPoolNx, MAX_LENGTH, poolTag)
            );
        if (!newBuffer) return nullptr;

        ULONG safeOffset = (offset > bufferLength - MAX_LENGTH) ? bufferLength - MAX_LENGTH : offset;

        RtlCopyMemory(newBuffer, byteBuffer + safeOffset, MAX_LENGTH);
        return newBuffer;
    }

    return nullptr; // если по какой-то причине ничего не подошло
}
