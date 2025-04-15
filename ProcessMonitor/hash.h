#pragma once

#include <ntifs.h>
#include <bcrypt.h>

#define HASH_ALG BCRYPT_SHA256_ALGORITHM
#define HASH_LEN 32 // SHA-256 = 32 bytes

NTSTATUS HashBuffer(
    _In_reads_bytes_(DataLength) PUCHAR Data,
    _In_ ULONG DataLength,
    _Out_writes_bytes_(HASH_LEN) PUCHAR HashOutput
);

NTSTATUS HashFile(
    _In_ PCUNICODE_STRING FilePath,
    _Out_writes_bytes_(HASH_LEN) PUCHAR HashOutput
);

NTSTATUS DosToNtPath(
    _In_ PCUNICODE_STRING DosPath,
    _Out_ PUNICODE_STRING NtPath,
    _In_ POOL_TYPE PoolType,
    _In_ ULONG Tag
);