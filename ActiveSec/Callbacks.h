#pragma once
#include <vector>
#include <set>
#include <ctime>
#include <algorithm>
#include "..\ActiveSec\CryptoAI.h"
#include <fltKernel.h>

namespace MiniFilter {

	unsigned char* AdjustBuffer(PVOID buffer, ULONG bufferLength, ULONG offset);

	const UINT16 gLookingTime = 10 * 60; //���������� �� ��������� �� 10 �����

	static NN::CryptoAI cryptoAI;

	struct TargetProcess
	{
		ULONG pid;
		ULONG additionTime;
		BOOLEAN isBlocked = FALSE;
	};

	static std::vector<TargetProcess> targetProcesses; //�������� ������� ���������� �����������



	//��������
	FLT_PREOP_CALLBACK_STATUS PreReadCallback(
		PFLT_CALLBACK_DATA Data,
		PCFLT_RELATED_OBJECTS FltObjects,
		PVOID* CompletionContext
	);



	//��������� �������� �� ��������
	FLT_PREOP_CALLBACK_STATUS PreWriteCallback(
		PFLT_CALLBACK_DATA Data,
		PCFLT_RELATED_OBJECTS FltObjects,
		PVOID* CompletionContext
	);


}