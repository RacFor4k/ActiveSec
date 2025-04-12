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

		// �������� ����� � char* ��� �������� ������ � �������
		unsigned char* byteBuffer = (unsigned char*)buffer;

		// ���� ����� ������ ������ 256 ����
		if (bufferLength < MAX_LENGTH) {
			// ��������� ����� ������ �� 256 ����, ������� � ����� ������
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

	const UINT16 gLookingTime = 10 * 60; //���������� �� ��������� �� 10 �����

	static NN::CryptoAI cryptoAI;

	struct TargetProcess
	{
		HANDLE pid;
		ULONG additionTime;
		BOOLEAN isBlocked = FALSE;
	};

	static std::vector<TargetProcess> targetProcesses; //�������� ������� ���������� �����������



	//��������
	FLT_PREOP_CALLBACK_STATUS PreReadCallback(
		PFLT_CALLBACK_DATA Data, 
		PCFLT_RELATED_OBJECTS FltObjects, 
		PVOID* CompletionContext
	) {
		UNREFERENCED_PARAMETER(Data);
		UNREFERENCED_PARAMETER(FltObjects);
		UNREFERENCED_PARAMETER(CompletionContext);

		return FLT_PREOP_SUCCESS_NO_CALLBACK;
	}


	//��������� �������� �� ��������
	FLT_PREOP_CALLBACK_STATUS MyPreWriteCallback(
		PFLT_CALLBACK_DATA Data,
		PCFLT_RELATED_OBJECTS FltObjects,
		PVOID* CompletionContext
	) {
		UNREFERENCED_PARAMETER(Data);
		UNREFERENCED_PARAMETER(FltObjects);
		UNREFERENCED_PARAMETER(CompletionContext);

		//��������� �������� ������� �������� �������� ������ � �����
		PEPROCESS process = PsGetCurrentProcess();
		HANDLE pid = PsGetProcessId(process);

		//����� �������� � ������ ������������� ��������� 
		auto target = std::find_if(targetProcesses.begin(), targetProcesses.end(), [pid](TargetProcess a) {return a.pid == pid; });

		if (target == targetProcesses.end()) {
			return FLT_PREOP_SUCCESS_NO_CALLBACK;
		}
		if ((*target).additionTime + gLookingTime <= time(0)) {
			targetProcesses.erase(target);
			return FLT_PREOP_SUCCESS_NO_CALLBACK;
		}

		PVOID buffer = Data->Iopb->Parameters.Write.WriteBuffer;
		ULONG lenght = Data->Iopb->Parameters.Write.Length;

		for (int i = 0; i < (lenght + 255) / 256; i++) {
			unsigned char* adjBuff = AdjustBuffer(buffer, lenght, 256*(lenght/256));
			if (cryptoAI.check(adjBuff)) {
				//������� ����� ����������� ������, ����� ���-�� ������
				return FLT_PREOP_COMPLETE; //����������� ������� ������
			}
		}
		return FLT_PREOP_SUCCESS_NO_CALLBACK; //���� �������� ���������� �� �������, ���������� ������ �� ������
	}


}