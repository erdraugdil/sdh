#include <sqlite3.h>
#include <stdio.h>
#include <string.h>
#include <stdexcept>
#include <mutex>
#include <iostream>
#include <sstream>
#include <string>
#include <memory>
#include <utility>
#include <stdexcept>

namespace {

const int call_count_limit = 25*20; //about 20 pages

struct AtSpec {
  AtSpec(std::string row_str, std::string col_str)
    : row(0), col(0)
  {
    try {
      if ((row_str == "*") || row_str.empty())
      {
        row = -1;
      }
      else
      {
        row = std::stoi(row_str);
        if (row < 0)
        {
          row = 0;
        }
      }
    } 
    catch(...) {
      row = 0;
    }
    try {
      if ((col_str == "*") || col_str.empty())
      {
        col = -1;
      }
      else
      {
        col = std::stoi(col_str);
        if (col < 0)
        {
          col = 0;
        }
      }
    }
    catch(...) {
      col = 0;
    }
    //if ((row == 0) || (col == 0)) throw std::runtime_error("Invalid row or column");
  }
  int row;
  int col;
};

struct CallbackUserArg {
  CallbackUserArg(const AtSpec* at, const char* sep) : separator{sep}, call_count{0}, output{}, at_specifier{at} {}
  explicit CallbackUserArg(const char* sep) : separator{sep}, call_count{0}, output{}, at_specifier{nullptr} {}
  CallbackUserArg() : separator{nullptr}, call_count{0}, output{}, at_specifier{nullptr} {}
  const char* separator;
  int call_count;
  std::stringstream output;
  const AtSpec* const at_specifier;
};

int callback(void* void_pfd, int argc, char** argv, char** azColName)
{
  CallbackUserArg* pfd = static_cast<CallbackUserArg*>(void_pfd);
  if (!pfd) return 1;
  if (pfd->call_count > call_count_limit)
  {
    pfd->output << "SDH warning: Too many lines, truncated\n";
    return 1;
  }
  if (pfd->call_count == 0)
  {
    for(int i=0; i<argc; i++)
    {
      pfd->output << azColName[i];
      if (i < (argc-1))
      {
        pfd->output << pfd->separator;
      }
    }
    pfd->output << "\n";
  }
  for(int i=0; i<argc; i++)
  {
    pfd->output << (argv[i] ? argv[i] : "NULL");
    if (i < (argc-1))
    {
      pfd->output << pfd->separator;
    }
  }
  pfd->output << "\n";
  ++pfd->call_count;
  return 0;
}

int callback_at(void* void_pfd, int argc, char** argv, char** azColName)
{
  CallbackUserArg* pfd = static_cast<CallbackUserArg*>(void_pfd);
  if (!pfd) return 1;

  if ((pfd->at_specifier->row == 0) || (pfd->at_specifier->col == 0))
  {
    pfd->output << "SDH error: Invalid row and/or column specified\n";
    return 1;
  }

  if (((pfd->call_count+1) == pfd->at_specifier->row) || (pfd->at_specifier->row == -1))
  {
    int i_0 = (pfd->at_specifier->col == -1) ? 0 : (pfd->at_specifier->col - 1);
    int i_end = (pfd->at_specifier->col == -1) ? (argc) : (i_0 + 1);

    if (i_end > argc)
    {
      pfd->output << "SDH error: Invalid column specified\n";
      return 1;
    }

    if ((pfd->call_count > 0) && (pfd->at_specifier->row == -1))
    {
      pfd->output << "\n";
    }

    for(int i=i_0; i<i_end; ++i)
    {
      pfd->output << (argv[i] ? argv[i] : "NULL");
      if ((i < (argc-1)) && ((i_end - i_0) > 1))
      {
        pfd->output << pfd->separator;
      }
    }
  }
  ++pfd->call_count;
  return 0;
}

int callback_count(void* void_pfd, int argc, char** argv, char** azColName)
{
  CallbackUserArg* pfd = static_cast<CallbackUserArg*>(void_pfd);
  if (!pfd) return 1;
  ++pfd->call_count;
  return 0;
}

} //namespace

extern "C" {

const char* sdh_exec(const char* sql, sqlite3* db, const char* separator)
{
  char *zErrMsg = 0;
  std::unique_ptr<CallbackUserArg> pfd(new CallbackUserArg(separator));
  auto rc = sqlite3_exec(db, sql, &callback, (void*)pfd.get(), &zErrMsg);
  if(rc != SQLITE_OK)
  {
    if (pfd->call_count <= call_count_limit)
    {
      pfd->output << "SDH error: SQLite error (" << zErrMsg << ")\n";
    }
    sqlite3_free(zErrMsg);
  }
  return strdup(pfd->output.str().c_str());
}

int sdh_exec_count(const char* sql, sqlite3* db)
{
  char *zErrMsg = 0;
  std::unique_ptr<CallbackUserArg> pfd(new CallbackUserArg);
  auto rc = sqlite3_exec(db, sql, &callback_count, (void*)pfd.get(), &zErrMsg);
  if(rc != SQLITE_OK)
  {
    sqlite3_free(zErrMsg);
    return -1;
  }
  return pfd->call_count;
}

// at specifier: [row]:[column]
// row: <number> | '*'
// column: <number> | '*'
const char* sdh_exec_at(const char* sql, const char* at, sqlite3* db, const char* separator)
{
  char *zErrMsg = 0;

  std::string at_str{at};
  auto at_sep_i = at_str.find_first_of(':');
  if (at_sep_i == std::string::npos)
  {
    return strdup("SDH error: invalid input format specified\n");
  }
  AtSpec at_spec{at_str.substr(0, at_sep_i), at_str.substr(at_sep_i+1)};
  std::unique_ptr<CallbackUserArg> pfd(new CallbackUserArg(&at_spec, separator));

  auto rc = sqlite3_exec(db, sql, &callback_at, (void*)pfd.get(), &zErrMsg);
  if(rc != SQLITE_OK)
  {
    pfd->output << "SDH error: SQLite error (" << zErrMsg << ")\n";
    sqlite3_free(zErrMsg);
  }

  if ((pfd->call_count > 1) && (pfd->at_specifier->row == -1))
  {
    pfd->output << "\n";
  }

  return strdup(pfd->output.str().c_str());
}

} //extern C

