#pragma once
#include <cstdio>
#include <string>
#include <iostream>
#include <WinSock2.h>
#include <WS2tcpip.h>
#include <stdio.h>
#include <vector>
#include <thread>


#pragma comment(lib, "Ws2_32.lib")

namespace NN {
	class CryptoAI
	{
	public:
		CryptoAI(const char* module_path);
		CryptoAI();

		bool check(const char* bytes);
		bool check(const unsigned char* bytes);

		~CryptoAI();

	private:
		int age;
		const std::string path;
		WSADATA wsData;
		SOCKET sock;
		in_addr ip_to_num;
		sockaddr_in servInfo;

		std::thread AI_th;
	};
}
