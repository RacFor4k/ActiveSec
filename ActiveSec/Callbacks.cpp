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

	//Получение процесса который пытается получить доступ к файлу
	PEPROCESS process = PsGetCurrentProcess();
	HANDLE pid = PsGetProcessId(process);

	//Поиск процесса в списке отслеживаемых процессов 
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
			//Процесс пишет шифрованные данные, нужно что-то делать
			return FLT_PREOP_COMPLETE; //блокируется попытка записи
		}
	}
	return FLT_PREOP_SUCCESS_NO_CALLBACK; //если признаки шифрования не найдены, пропускаем запрос на запись
}