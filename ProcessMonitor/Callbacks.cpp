#include "Callbacks.h"



FLT_PREOP_CALLBACK_STATUS MiniFilter::PreReadCallback(PFLT_CALLBACK_DATA Data, PCFLT_RELATED_OBJECTS FltObjects, PVOID* CompletionContext)
{

	UNREFERENCED_PARAMETER(Data);
	UNREFERENCED_PARAMETER(FltObjects);
	UNREFERENCED_PARAMETER(CompletionContext);

	return FLT_PREOP_SUCCESS_NO_CALLBACK;
}

FLT_PREOP_CALLBACK_STATUS MiniFilter::PreWriteCallback(PFLT_CALLBACK_DATA Data, PCFLT_RELATED_OBJECTS FltObjects, PVOID* CompletionContext)
{
	UNREFERENCED_PARAMETER(Data);
	UNREFERENCED_PARAMETER(FltObjects);
	UNREFERENCED_PARAMETER(CompletionContext);

	//Получение процесса который пытается получить доступ к файлу
	HANDLE pid = PsGetProcessId(PsGetCurrentProcess());

	//Поиск процесса в списке отслеживаемых процессов 
	size_t i;
	for (i = 0; i < targetProcesses.size(); i++) {
		if (targetProcesses[i].pid == pid)
			break;
		else if (i == targetProcesses.size() - 1)
			i = targetProcesses.size();
	}

	if (i == targetProcesses.size()) {
		return FLT_PREOP_SUCCESS_NO_CALLBACK;
	}
	if (targetProcesses[i].additionTime + gLookingTime <= cutils::GetSystemTimeSeconds()) {
		targetProcesses.remove(i);
		return FLT_PREOP_SUCCESS_NO_CALLBACK;
	}

	PVOID buffer = Data->Iopb->Parameters.Write.WriteBuffer;
	ULONG lenght = Data->Iopb->Parameters.Write.Length;

	for (int i = 0; i < (lenght + 255) / 256; i++) {
		unsigned char* adjBuff = cutils::AdjustBuffer(buffer, lenght, 256 * (lenght / 256));
		//if (cryptoAI.check(adjBuff)) {
		//	//Процесс пишет шифрованные данные, нужно что-то делать
		//	return FLT_PREOP_COMPLETE; //блокируется попытка записи
		//}
	}
	return FLT_PREOP_SUCCESS_NO_CALLBACK; //если признаки шифрования не найдены, пропускаем запрос на запись
}

VOID CreateProcessNotifyRoutineEx(PEPROCESS Process, HANDLE ProcessId, PPS_CREATE_NOTIFY_INFO CreateInfo)
{
	//Прочесс создан
	if (CreateInfo) {
		MiniFilter::targetProcesses.append({ ProcessId, cutils::GetSystemTimeSeconds(), FALSE });
	}
	else {
		size_t i;
		for (i = 0; i < MiniFilter::targetProcesses.size(); i++) {
			if (MiniFilter::targetProcesses[i].pid == ProcessId)
				break;
			else if (i == MiniFilter::targetProcesses.size() - 1)
				i = MiniFilter::targetProcesses.size();
		}
		MiniFilter::targetProcesses.remove(i);
	}
}
