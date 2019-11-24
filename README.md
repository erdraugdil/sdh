# sdh
SQLite Debugger Helper

This is a plugin for GDB and it makes it possible to run SQL queries from the debugger directly. It also supports conditional breakpoints with SQL queries.

## Installation

```
cd sdh
./build.sh
```

## Usage

### Loading

Start gdb (gdb <path_to_an_executable_that_uses_sqlite)
```
source <path_to_sdh_install>/sdh.py
start
```

### Commands

Stop program execution after at least one SQLite call

```
sql
sqlcount
sqlat
```
