#include "CryptoAI.h"
#include <iostream>
#include <vector>
#include <ctime>
#include <fstream>
#include <algorithm>

using namespace std;


bool replace(std::string& str, const std::string& from, const std::string& to) {
	size_t start_pos = str.find(from);
	if (start_pos == std::string::npos)
		return false;
	str.replace(start_pos, from.length(), to);
	return true;
}


int main() {
	srand(time(0));
	NN::CryptoAI crypto("utfdtrd5ufi");
	char* b = new char[256];
	while (1) {
		string a;
		cin >> a;
		a = string(a.begin() + 1, a.end() - 1);
		ifstream fin(a, ios_base::binary);
		fin.read(b, 256);
		bool e = crypto.check(b);
		cout << char(8) << e << endl;
	}

}