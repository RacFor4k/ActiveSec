#pragma once
#include <FltKernel.h>
#include <bcrypt.h>

#define MY_CRYPTO_TAG 'pyrC'
#define KEY_LENGTH 32   // 256-bit key
#define SALT_MASK 0xC0000003
#define DATA_LEN   32   // шифруем ровно 32 байта

NTSTATUS CUGenerateRandomBytes(UCHAR* outputBuffer);

NTSTATUS CUEncryptAES256(
    const UCHAR* key32,
    const UCHAR* input32,
    UCHAR* output32
);

NTSTATUS CUDecryptAES256(
    const UCHAR* key32,
    const UCHAR* input32,
    UCHAR* output32
);

BOOLEAN CUCompareWithSaltMask(
    const UCHAR* str1,
    const UCHAR* str2,
    UINT32 mask
);
