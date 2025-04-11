#include "CryptoAI.h"

NN::CryptoAI::CryptoAI(const char* path)
{
	std::string script_path = "py ";
	script_path += path;
	system(script_path.c_str());

	int errStat = WSAStartup(MAKEWORD(2, 2), &wsData);
	sock = socket(AF_INET, SOCK_STREAM, 0);

	if (sock == INVALID_SOCKET) {
		closesocket(sock);
		WSACleanup();
	}

	errStat = inet_pton(AF_INET, "127.0.0.1", &ip_to_num);

	ZeroMemory(&servInfo, sizeof(servInfo));

	servInfo.sin_family = AF_INET;
	servInfo.sin_addr = ip_to_num;
	servInfo.sin_port = htons(9348);

	errStat = connect(sock, (sockaddr*)&servInfo, sizeof(servInfo));

}
