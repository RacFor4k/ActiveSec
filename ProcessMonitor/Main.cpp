#include <fltKernel.h>

PFLT_FILTER gFilterHandle = NULL;



NTSTATUS DriverEntry(PDRIVER_OBJECT DriverObject, PUNICODE_STRING RegistryPath) {
	NTSTATUS status;
	PFLT_PORT serverPort = NULL;

	status = FltRegisterFilter(DriverObject, &FilterRegistration, &gFilterHandle)
}