#pragma once
#include "SQLite/sqlite3.h"    //запись в БД, чтение из БД, удаление из БД
#include <string>


class Database
{
public:
	Database();
	~Database();

private:
	std::string dbPath = ""
};