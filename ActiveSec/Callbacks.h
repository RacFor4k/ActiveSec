#pragma once
#include <vector>
#include <set>
#include <ctime>
#include <algorithm>
#include "..\ActiveSec\CryptoAI.h"
#include <fltKernel.h>

namespace MiniFilter {

	unsigned char* AdjustBuffer(PVOID buffer, ULONG bufferLength, ULONG offset) {
		const ULONG MAX_LENGTH = 256;

		// Приводим буфер к char* для удобства работы с памятью
		unsigned char* byteBuffer = (unsigned char*)buffer;

		// Если буфер длиной меньше 256 байт
		if (bufferLength < MAX_LENGTH) {
			// Дополняем буфер нулями до 256 байт, начиная с конца буфера
			std::memset(byteBuffer + bufferLength, 0, MAX_LENGTH - bufferLength);
			return byteBuffer;
		}
		if (bufferLength == MAX_LENGTH) {
			return byteBuffer;
		}
		if (bufferLength > MAX_LENGTH) {
			byteBuffer = new unsigned char[MAX_LENGTH];
			offset = max(offset, bufferLength - 256);
			std::memcpy(byteBuffer, (unsigned char*)buffer + offset, MAX_LENGTH);

		}
	}

	const UINT16 gLookingTime = 10 * 60; //наблидение за процессом до 10 минут

	static NN::CryptoAI cryptoAI;

	struct TargetProcess
	{
		HANDLE pid;
		ULONG additionTime;
		BOOLEAN isBlocked = FALSE;
	};

	static std::vector<TargetProcess> targetProcesses; //процессы которые необходимо отслеживать



	//заглушка
	FLT_PREOP_CALLBACK_STATUS PreReadCallback(
		PFLT_CALLBACK_DATA Data,
		PCFLT_RELATED_OBJECTS FltObjects,
		PVOID* CompletionContext
	);


	//Обзаботка запросов на запись
	FLT_PREOP_CALLBACK_STATUS MyPreWriteCallback(
		PFLT_CALLBACK_DATA Data,
		PCFLT_RELATED_OBJECTS FltObjects,
		PVOID* CompletionContext
	);


}