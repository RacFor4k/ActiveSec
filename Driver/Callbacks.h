#pragma once
#include <fltKernel.h>

FLT_PREOP_CALLBACK_STATUS PreCreateCallback(
	PFLT_CALLBACK_DATA Data,
	PCFLT_RELATED_OBJECTS FltObjects,
	PVOID* CompletionContext
);

FLT_PREOP_CALLBACK_STATUS PreReadCallback(
	PFLT_CALLBACK_DATA Data,
	PCFLT_RELATED_OBJECTS FltObjects,
	PVOID* CompletionContext
);

FLT_PREOP_CALLBACK_STATUS PreWriteCallback(
	PFLT_CALLBACK_DATA Data,
	PCFLT_RELATED_OBJECTS FltObjects,
	PVOID* CompletionContext
);