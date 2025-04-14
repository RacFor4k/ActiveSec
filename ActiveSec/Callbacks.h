#pragma once
#include <vector>
#include <set>
#include <ctime>
#include <algorithm>
#include "..\ActiveSec\CryptoAI.h"
#include <fltKernel.h>

namespace MiniFilter {

	unsigned char* AdjustBuffer(PVOID buffer, ULONG bufferLength, ULONG offset);

	const UINT16 gLookingTime = 10 * 60; //наблидение за процессом до 10 минут

	static NN::CryptoAI cryptoAI;

	struct TargetProcess
	{
		ULONG pid;
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



	//Обзаботка запросов на записать
	FLT_PREOP_CALLBACK_STATUS PreWriteCallback(
		PFLT_CALLBACK_DATA Data,
		PCFLT_RELATED_OBJECTS FltObjects,
		PVOID* CompletionContext
	);


}