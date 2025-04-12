#include "CryptoAI.h"

NN::CryptoAI::CryptoAI(const char* path)
{
	std::string script_path = "py ";
	script_path += path;
	script_path += "detect.py ";
	script_path += path;
	script_path += "model.pth";

	AI_th = std::thread(system, script_path.c_str());

	int errStat = WSAStartup(MAKEWORD(2, 2), &wsData);
	sock = socket(AF_INET, SOCK_STREAM, 0);

	if (sock == INVALID_SOCKET) {

		closesocket(sock);
		WSACleanup();
		return;
	}

	errStat = inet_pton(AF_INET, "127.0.0.1", &ip_to_num);

	ZeroMemory(&servInfo, sizeof(servInfo));

	servInfo.sin_family = AF_INET;
	servInfo.sin_addr = ip_to_num;
	servInfo.sin_port = htons(9348);
	errStat = -1;
	while (errStat == -1) {
		Sleep(20);
		errStat = connect(sock, (sockaddr*)&servInfo, sizeof(servInfo));
	}
}

bool NN::CryptoAI::check(const char* bytes)
{
	send(sock, bytes, 256, 0);
	char* buff = new char[1];
	recv(sock, buff, 1, 0);
	bool res = bool(buff[0] - '0');
	delete[] buff;
	return res;
}

bool NN::CryptoAI::check(const unsigned char* bytes)
{
	return check((const char*)bytes);
}

NN::CryptoAI::~CryptoAI()
{
	AI_th.detach();
}

NN::CryptoAI::CryptoAI() : CryptoAI("..\\CryptoAI\\")
{
	
}
