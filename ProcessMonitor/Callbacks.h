#pragma once
#include <ctime>
#include "..\ActiveSec\CryptoAI.h"
#include <fltKernel.h>
#include "dynamic.h"
#include "cutils.h"

namespace MiniFilter {

	const UINT16 gLookingTime = 10 * 60; //наблидение за процессом до 10 минут

	static NN::CryptoAI cryptoAI;

	struct TargetProcess
	{
		HANDLE  pid;
		ULONGLONG additionTime;
		BOOLEAN isBlocked = FALSE;
	};

	static list<TargetProcess> targetProcesses; //процессы которые необходимо отслеживать



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

VOID CreateProcessNotifyRoutineEx(
	_Inout_ PEPROCESS Process,
	_In_ HANDLE ProcessId,
	_In_opt_ PPS_CREATE_NOTIFY_INFO CreateInfo
);