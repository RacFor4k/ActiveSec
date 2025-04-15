#include "hash.h"

NTSTATUS HashBuffer(PUCHAR Data, ULONG DataLength, PUCHAR HashOutput)
{
    BCRYPT_ALG_HANDLE hAlg = NULL;
    BCRYPT_HASH_HANDLE hHash = NULL;
    PUCHAR pbHashObject = NULL;
    ULONG cbHashObject = 0;
    ULONG cbData = 0;
    NTSTATUS status = STATUS_SUCCESS;

    status = BCryptOpenAlgorithmProvider(&hAlg, HASH_ALG, NULL, 0);
    if (!NT_SUCCESS(status)) goto cleanup;

    status = BCryptGetProperty(hAlg, BCRYPT_OBJECT_LENGTH, (PUCHAR)&cbHashObject, sizeof(ULONG), &cbData, 0);
    if (!NT_SUCCESS(status)) goto cleanup;

    pbHashObject = (PUCHAR)ExAllocatePoolWithTag(NonPagedPoolNx, cbHashObject, 'hObj');
    if (!pbHashObject) {
        status = STATUS_INSUFFICIENT_RESOURCES;
        goto cleanup;
    }

    status = BCryptCreateHash(hAlg, &hHash, pbHashObject, cbHashObject, NULL, 0, 0);
    if (!NT_SUCCESS(status)) goto cleanup;

    status = BCryptHashData(hHash, Data, DataLength, 0);
    if (!NT_SUCCESS(status)) goto cleanup;

    status = BCryptFinishHash(hHash, HashOutput, HASH_LEN, 0);

cleanup:
    if (hHash) BCryptDestroyHash(hHash);
    if (pbHashObject) ExFreePoolWithTag(pbHashObject, 'hObj');
    if (hAlg) BCryptCloseAlgorithmProvider(hAlg, 0);

    return status;
}

NTSTATUS HashFile(PCUNICODE_STRING FilePath, PUCHAR HashOutput)
{

    OBJECT_ATTRIBUTES objAttr;
    IO_STATUS_BLOCK ioStatus = { 0 };
    HANDLE hFile = NULL;
    PUCHAR buffer = NULL;
    const ULONG BufferSize = 4096;
    NTSTATUS status;

    PUNICODE_STRING ntFilePath;

    status = DosToNtPath(FilePath, ntFilePath, NonPagedPool, 'ntPT');

    if (!NT_SUCCESS(status)) return status;

    InitializeObjectAttributes(&objAttr, (PUNICODE_STRING)FilePath, OBJ_KERNEL_HANDLE | OBJ_CASE_INSENSITIVE, NULL, NULL);

    status = ZwCreateFile(
        &hFile, GENERIC_READ, &objAttr, &ioStatus, NULL,
        FILE_ATTRIBUTE_NORMAL, FILE_SHARE_READ,
        FILE_OPEN, FILE_SYNCHRONOUS_IO_NONALERT | FILE_NON_DIRECTORY_FILE, NULL, 0);

    if (!NT_SUCCESS(status)) return status;

    BCRYPT_ALG_HANDLE hAlg = NULL;
    BCRYPT_HASH_HANDLE hHash = NULL;
    PUCHAR pbHashObject = NULL;
    ULONG cbHashObject = 0, cbData = 0;

    buffer = (PUCHAR)ExAllocatePoolWithTag(NonPagedPoolNx, BufferSize, 'buff');
    if (!buffer) {
        status = STATUS_INSUFFICIENT_RESOURCES;
        goto cleanup;
    }

    status = BCryptOpenAlgorithmProvider(&hAlg, HASH_ALG, NULL, 0);
    if (!NT_SUCCESS(status)) goto cleanup;

    status = BCryptGetProperty(hAlg, BCRYPT_OBJECT_LENGTH, (PUCHAR)&cbHashObject, sizeof(ULONG), &cbData, 0);
    if (!NT_SUCCESS(status)) goto cleanup;

    pbHashObject = (PUCHAR)ExAllocatePoolWithTag(NonPagedPoolNx, cbHashObject, 'fHsh');
    if (!pbHashObject) {
        status = STATUS_INSUFFICIENT_RESOURCES;
        goto cleanup;
    }

    status = BCryptCreateHash(hAlg, &hHash, pbHashObject, cbHashObject, NULL, 0, 0);
    if (!NT_SUCCESS(status)) goto cleanup;

    LARGE_INTEGER offset = { 0 };
    while (TRUE) {
        status = ZwReadFile(hFile, NULL, NULL, NULL, &ioStatus, buffer, BufferSize, &offset, NULL);
        if (status == STATUS_END_OF_FILE || ioStatus.Information == 0) break;
        if (!NT_SUCCESS(status)) goto cleanup;

        status = BCryptHashData(hHash, buffer, (ULONG)ioStatus.Information, 0);
        if (!NT_SUCCESS(status)) goto cleanup;

        offset.QuadPart += ioStatus.Information;
    }

    status = BCryptFinishHash(hHash, HashOutput, HASH_LEN, 0);

cleanup:
    if (buffer) ExFreePoolWithTag(buffer, 'buff');
    if (hHash) BCryptDestroyHash(hHash);
    if (pbHashObject) ExFreePoolWithTag(pbHashObject, 'fHsh');
    if (hAlg) BCryptCloseAlgorithmProvider(hAlg, 0);
    if (hFile) ZwClose(hFile);

    return status;
}

NTSTATUS DosToNtPath(PCUNICODE_STRING DosPath, PUNICODE_STRING NtPath, POOL_TYPE PoolType, ULONG Tag)
{
    if (!DosPath || !NtPath || !DosPath->Buffer) return STATUS_INVALID_PARAMETER;

    const WCHAR* Prefix = L"\\??\\";
    SIZE_T PrefixLen = wcslen(Prefix);
    SIZE_T DosLen = DosPath->Length / sizeof(WCHAR);
    SIZE_T NewLen = PrefixLen + DosLen;

    // +1 for null terminator
    PWCHAR NewBuf = (PWCHAR)ExAllocatePoolWithTag(PoolType, (NewLen + 1) * sizeof(WCHAR), Tag);
    if (!NewBuf) return STATUS_INSUFFICIENT_RESOURCES;

    RtlCopyMemory(NewBuf, Prefix, PrefixLen * sizeof(WCHAR));
    RtlCopyMemory(NewBuf + PrefixLen, DosPath->Buffer, DosPath->Length);
    NewBuf[NewLen] = L'\0';

    NtPath->Buffer = NewBuf;
    NtPath->Length = (USHORT)(NewLen * sizeof(WCHAR));
    NtPath->MaximumLength = (USHORT)((NewLen + 1) * sizeof(WCHAR));

    return STATUS_SUCCESS;
}


