#include "CryptoUtils.h"

NTSTATUS CUGenerateRandomBytes(UCHAR* outputBuffer)
{
    if (!outputBuffer) return STATUS_INVALID_PARAMETER;

    return BCryptGenRandom(
        NULL,
        outputBuffer,
        KEY_LENGTH,
        BCRYPT_USE_SYSTEM_PREFERRED_RNG
    );
}


// ============================================================
// Encryption (input → output)
// ============================================================

NTSTATUS CUCryptoAes(
    const UCHAR* key32,
    const UCHAR* input32,
    UCHAR* output32,
    BOOLEAN encrypt
)
{
    if (!key32 || !input32 || !output32)
        return STATUS_INVALID_PARAMETER;

    NTSTATUS status = STATUS_SUCCESS;
    BCRYPT_ALG_HANDLE hAlg = NULL;
    BCRYPT_KEY_HANDLE hKey = NULL;
    PUCHAR pbKeyObject = NULL;
    ULONG cbKeyObject = 0;
    ULONG cbData = 0;
    ULONG resultLength = 0;

    // 1. AES provider
    status = BCryptOpenAlgorithmProvider(&hAlg, BCRYPT_AES_ALGORITHM, NULL, 0);
    if (!NT_SUCCESS(status)) goto Cleanup;

    // 2. ECB mode
    status = BCryptSetProperty(
        hAlg,
        BCRYPT_CHAINING_MODE,
        (PUCHAR)BCRYPT_CHAIN_MODE_ECB,
        sizeof(BCRYPT_CHAIN_MODE_ECB),
        0
    );
    if (!NT_SUCCESS(status)) goto Cleanup;

    // 3. Key object size
    status = BCryptGetProperty(
        hAlg,
        BCRYPT_OBJECT_LENGTH,
        (PUCHAR)&cbKeyObject,
        sizeof(ULONG),
        &cbData,
        0
    );
    if (!NT_SUCCESS(status)) goto Cleanup;

    pbKeyObject = ExAllocatePool2(POOL_FLAG_NON_PAGED, cbKeyObject, MY_CRYPTO_TAG);
    if (!pbKeyObject) {
        status = STATUS_INSUFFICIENT_RESOURCES;
        goto Cleanup;
    }

    // 4. Create symmetric key
    status = BCryptGenerateSymmetricKey(
        hAlg,
        &hKey,
        pbKeyObject,
        cbKeyObject,
        (PUCHAR)key32,
        KEY_LENGTH,
        0
    );
    if (!NT_SUCCESS(status)) goto Cleanup;

    // 5. Encrypt or decrypt
    if (encrypt)
    {
        status = BCryptEncrypt(
            hKey,
            (PUCHAR)input32,
            DATA_LEN,
            NULL,
            NULL,
            0,
            output32,
            DATA_LEN,
            &resultLength,
            0
        );
    }
    else
    {
        status = BCryptDecrypt(
            hKey,
            (PUCHAR)input32,
            DATA_LEN,
            NULL,
            NULL,
            0,
            output32,
            DATA_LEN,
            &resultLength,
            0
        );
    }

    if (NT_SUCCESS(status) && resultLength != DATA_LEN)
        status = STATUS_UNSUCCESSFUL;

Cleanup:
    if (hKey) BCryptDestroyKey(hKey);
    if (hAlg) BCryptCloseAlgorithmProvider(hAlg, 0);
    if (pbKeyObject) ExFreePoolWithTag(pbKeyObject, MY_CRYPTO_TAG);

    return status;
}



// ============================================================
// Public wrappers
// ============================================================

NTSTATUS CUEncryptAES256(const UCHAR* key32, const UCHAR* input32, UCHAR* output32)
{
    return CUCryptoAes(key32, input32, output32, TRUE);
}

NTSTATUS CUDecryptAES256(const UCHAR* key32, const UCHAR* input32, UCHAR* output32)
{
    return CUCryptoAes(key32, input32, output32, FALSE);
}



// ============================================================
// Compare with mask
// ============================================================

BOOLEAN CUCompareWithSaltMask(const UCHAR* str1, const UCHAR* str2, UINT32 mask)
{
    if (!str1 || !str2) return FALSE;

    for (int i = 0; i < DATA_LEN; i++)
    {
        BOOLEAN isSalt = (mask >> i) & 1;

        if (!isSalt) {
            if (str1[i] != str2[i])
                return FALSE;
        }
    }
    return TRUE;
}
