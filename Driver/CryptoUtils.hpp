#pragma once
#include <FltKernel.h>
#include <bcrypt.h>

// Тег для выделения памяти (полезно для отладки утечек)
#define MY_CRYPTO_TAG 'pyrC' 
#define KEY_LENGHT 32

namespace CryptoUtils
{
    // ----------------------------------------------------------------------
    // 1. Генерация случайного char[32]
    // ----------------------------------------------------------------------

    /*
     * Генерирует 32 байта криптографически стойкой случайной информации.
     * Использует BCRYPT_USE_SYSTEM_PREFERRED_RNG (доступно с Win 8/Server 2012),
     * что позволяет не открывать провайдер алгоритма вручную.
     */
    NTSTATUS GenerateRandomBytes(
        _Outptr_ char* outputBuffer
    );

    // ----------------------------------------------------------------------
    // 2. Расшифровка char[32] (AES-256 ECB)
    // ----------------------------------------------------------------------

    /*
     * Расшифровывает данные алгоритмом AES-256.
     * Режим: ECB (так как нет IV и данные фиксированы).
     * Ключ: 32 байта (256 бит).
     * Данные: 32 байта.
     */
    NTSTATUS DecryptAES256(
        _In_ const char* key32,
        _Inout_ char* encryptedData32
    );

    // ----------------------------------------------------------------------
    // 3. Сверка строк с учетом маски (соли)
    // ----------------------------------------------------------------------

    /*
     * Сравнивает два массива char[32].
     * mask (uint32_t): битовая маска длиной 32 бита.
     * Если бит == 1: символ является солью (пропускаем проверку).
     * Если бит == 0: символ является данными (сравниваем).
     */
    BOOLEAN CompareWithSaltMask(
        _In_ const char* str1,
        _In_ const char* str2,
        UINT32 mask
    );


    NTSTATUS GenerateRandomBytes(char* outputBuffer)
    {
        if (!outputBuffer) return STATUS_INVALID_PARAMETER;

        // BCRYPT_USE_SYSTEM_PREFERRED_RNG работает на IRQL = PASSIVE_LEVEL
        return BCryptGenRandom(
            NULL,
            (PUCHAR)outputBuffer,
            KEY_LENGHT,
            BCRYPT_USE_SYSTEM_PREFERRED_RNG
        );
    }

    NTSTATUS DecryptAES256(const char* key32, char* encryptedData32)
    {
        // Примечание: encryptedData32 теперь не const, так как он будет перезаписан.
        if (!key32 || !encryptedData32) return STATUS_INVALID_PARAMETER;

        BCRYPT_ALG_HANDLE hAlg = NULL;
        BCRYPT_KEY_HANDLE hKey = NULL;
        PCHAR pbKeyObject = NULL;
        NTSTATUS status = STATUS_SUCCESS;
        ULONG cbKeyObject = 0;
        ULONG cbData = 0;

        // 1. Открываем провайдер алгоритма AES
        status = BCryptOpenAlgorithmProvider(&hAlg, BCRYPT_AES_ALGORITHM, NULL, 0);
        if (!NT_SUCCESS(status)) goto Cleanup;

        // 2. Устанавливаем режим цепочки ECB 
        status = BCryptSetProperty(hAlg, BCRYPT_CHAINING_MODE, (PUCHAR)BCRYPT_CHAIN_MODE_ECB, sizeof(BCRYPT_CHAIN_MODE_ECB), 0);
        if (!NT_SUCCESS(status)) goto Cleanup;

        // 3. Получаем размер объекта ключа
        status = BCryptGetProperty(hAlg, BCRYPT_OBJECT_LENGTH, (PUCHAR)&cbKeyObject, sizeof(ULONG), &cbData, 0);
        if (!NT_SUCCESS(status)) goto Cleanup;

        // 4. Выделяем память под объект ключа (NonPagedPool для KM)
        pbKeyObject = (PCHAR)ExAllocatePool2(POOL_FLAG_NON_PAGED, cbKeyObject, MY_CRYPTO_TAG);
        if (!pbKeyObject) {
            status = STATUS_INSUFFICIENT_RESOURCES;
            goto Cleanup;
        }

        // 5. Генерируем симметричный ключ из переданного пароля (key32)
        // Используем KEY_LENGHT для длины ключа (32 байта)
        status = BCryptGenerateSymmetricKey(hAlg, &hKey, (PUCHAR)pbKeyObject, cbKeyObject, (PUCHAR)key32, KEY_LENGHT, 0);
        if (!NT_SUCCESS(status)) goto Cleanup;

        // 6. Расшифровываем данные (In-place)
        ULONG resultLength = 0;

        // В BCryptDecrypt мы передаем один и тот же буфер для входа и выхода.
        status = BCryptDecrypt(
            hKey,
            (PUCHAR)encryptedData32, // Входной буфер
            KEY_LENGHT,             // Длина входного буфера (32)
            NULL,                    // PaddingInfo (не используется в ECB)
            NULL,                    // IV буфер (не используется в ECB)
            0,                       // IV размер
            (PUCHAR)encryptedData32, // Выходной буфер (тот же самый)
            KEY_LENGHT,             // Длина выходного буфера
            &resultLength,
            0 // Флаги
        );

        // BCryptDecrypt должен вернуть resultLength равный DATA_LENGTH (32)
        if (NT_SUCCESS(status) && resultLength != KEY_LENGHT) {
            // Это маловероятно для ECB без паддинга, но хорошая практика
            status = STATUS_UNSUCCESSFUL;
        }

    Cleanup:
        if (hKey) BCryptDestroyKey(hKey);
        if (hAlg) BCryptCloseAlgorithmProvider(hAlg, 0);
        if (pbKeyObject) ExFreePoolWithTag(pbKeyObject, MY_CRYPTO_TAG);

        return status;
    }

    BOOLEAN CompareWithSaltMask(const char* str1, const char* str2, UINT32 mask)
    {
        if (!str1 || !str2) return FALSE;

        for (int i = 0; i < 32; i++)
        {
            // Проверяем i-й бит маски
            // (mask >> i) сдвигает маску на i позиций вправо
            // & 1 берет последний бит
            BOOLEAN isSalt = (mask >> i) & 1;

            if (isSalt)
            {
                // Если это соль (бит = 1), мы игнорируем различие в этом байте
                continue;
            }
            else
            {
                // Если это данные (бит = 0), байты должны совпадать
                if (str1[i] != str2[i])
                {
                    return FALSE; // Найдено несоответствие
                }
            }
        }

        return TRUE; // Все значащие байты совпали
    }
}