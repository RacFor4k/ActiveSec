#include "Callbacks.h"

FLT_PREOP_CALLBACK_STATUS MiniFilter::PreReadCallback(PFLT_CALLBACK_DATA Data, PCFLT_RELATED_OBJECTS FltObjects, PVOID* CompletionContext)
{

	UNREFERENCED_PARAMETER(Data);
	UNREFERENCED_PARAMETER(FltObjects);
	UNREFERENCED_PARAMETER(CompletionContext);

	return FLT_PREOP_SUCCESS_NO_CALLBACK;
}

FLT_PREOP_CALLBACK_STATUS MiniFilter::MyPreWriteCallback(PFLT_CALLBACK_DATA Data, PCFLT_RELATED_OBJECTS FltObjects, PVOID* CompletionContext)
{
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
		unsigned char* adjBuff = AdjustBuffer(buffer, lenght, 256 * (lenght / 256));
		if (cryptoAI.check(adjBuff)) {
			//������� ����� ����������� ������, ����� ���-�� ������
			return FLT_PREOP_COMPLETE; //����������� ������� ������
		}
	}
	return FLT_PREOP_SUCCESS_NO_CALLBACK; //���� �������� ���������� �� �������, ���������� ������ �� ������
}