#pragma once
#include "SQLite/sqlite3.h"    //������ � ��, ������ �� ��, �������� �� ��
#include <string>


class Database
{
public:
	Database();
	~Database();

private:
	std::string dbPath = ""
};