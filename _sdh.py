print("***************************************************************************************")
print("* SQLite Debugger Helper - Copyright (C) 2017-2019 Laszlo Bodor. All rights reserved. *")
print("***************************************************************************************")


import os
import hashlib
import getpass
import socket
import gdb
from sdh import sdh_root_directory

def load_sharedobject():
  global g_sharedobject_loaded
  if 'g_sharedobject_loaded' not in globals():
    g_sharedobject_loaded = False
  if not verify():
    return
  if not g_sharedobject_loaded:
    try:
      sofile = os.path.join(sdh_root_directory, "libsdh.so")
      cmd = 'dlopen("' + sofile.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\\n") + '", 258)'
      if gdb.parse_and_eval(cmd) == 0:
        raise gdb.GdbError("SDH error: Couldn't load helper library")
      g_sharedobject_loaded = True
    except:
      if len(gdb.inferiors()) > 0:
        if gdb.inferiors()[0].is_valid() and (gdb.inferiors()[0].pid > 0):
          raise gdb.GdbError("SDH error: Couldn't load helper library")
      raise gdb.GdbError("SDH warning: Function and or command only works if a program is running")


class DbHandleBreakpoint(gdb.Breakpoint):
  def __init__(self, spec):
    super(DbHandleBreakpoint, self).__init__(spec, gdb.BP_BREAKPOINT, internal = True)

  def stop(self):
    gdb.execute("set variable $sdh_db = db", False, False)
    gdb.execute("set variable $sdh_ppDb = 0", False, False)
    return False

class PointerToDbHandleBreakpoint(gdb.Breakpoint):
  def __init__(self, spec):
    super(PointerToDbHandleBreakpoint, self).__init__(spec, gdb.BP_BREAKPOINT, internal = True)

  def stop(self):
    gdb.execute("set variable $sdh_db = 0", False, False)
    gdb.execute("set variable $sdh_ppDb = ppDb", False, False)
    return False

class CloseDbHandleBreakpoint(gdb.Breakpoint):
  def __init__(self, spec):
    super(CloseDbHandleBreakpoint, self).__init__(spec, gdb.BP_BREAKPOINT, internal = True)

  def stop(self):
    if gdb.parse_and_eval("$sdh_ppDb != 0"):
      if gdb.parse_and_eval("*$sdh_ppDb == db"):
        gdb.execute("set variable $sdh_db = 0", False, False)
        gdb.execute("set variable $sdh_ppDb = 0", False, False)
        return False
    if gdb.parse_and_eval("$sdh_db == db"):
      gdb.execute("set variable $sdh_db = 0", False, False)
      gdb.execute("set variable $sdh_ppDb = 0", False, False)
      return False
    return False


def verify():
  return True

class SDHEnable(gdb.Command):
  """Enables the hooks necessary for SQL queries to work.
  Normally it is called automatically at program startup or when the debugger is attached."""

  def __init__ (self):
    super(SDHEnable, self).__init__ ("sdh-enable", gdb.COMMAND_NONE, gdb.COMPLETE_NONE)

  def invoke (self, args, from_tty):
    global g_sdh_enabled
    global g_sdh_breakpoints
    if 'g_sdh_enabled' not in globals():
      g_sdh_enabled = False
    if 'g_sdh_breakpoints' not in globals():
      g_sdh_breakpoints = []
    if not verify():
      return
    if not g_sdh_enabled:
      gdb.execute("set variable $sdh_db = 0", False, False)
      gdb.execute("set variable $sdh_ppDb = 0", False, False)
      g_sdh_breakpoints.append(PointerToDbHandleBreakpoint("sqlite3_open"))
      g_sdh_breakpoints.append(PointerToDbHandleBreakpoint("sqlite3_open16"))
      g_sdh_breakpoints.append(PointerToDbHandleBreakpoint("sqlite3_open_v2"))
      g_sdh_breakpoints.append(DbHandleBreakpoint("sqlite3_prepare"))
      g_sdh_breakpoints.append(DbHandleBreakpoint("sqlite3_prepare_v2"))
      g_sdh_breakpoints.append(DbHandleBreakpoint("sqlite3_prepare16"))
      g_sdh_breakpoints.append(DbHandleBreakpoint("sqlite3_prepare16_v2"))
      g_sdh_breakpoints.append(CloseDbHandleBreakpoint("sqlite3_close"))
      g_sdh_enabled = True

SDHEnable()


def stop_handler(event):
  gdb.execute("sdh-enable", False, False)

gdb.events.stop.connect(stop_handler)

def new_objfile_handler(event):
  gdb.execute("sdh-enable", False, False)

gdb.events.new_objfile.connect(new_objfile_handler)

def exited_handler(event):
  global g_sharedobject_loaded
  g_sharedobject_loaded = False

gdb.events.exited.connect(exited_handler)


def breakpoints_disable():
  all_breakpoints_state = {}
  for brk in gdb.breakpoints():
    all_breakpoints_state[brk.number] = brk.enabled
    brk.enabled = False
  return all_breakpoints_state

def breakpoints_enable(all_breakpoints_state):
  for num in all_breakpoints_state:
    for brk in gdb.breakpoints():
      if brk.number == num:
        brk.enabled = all_breakpoints_state[num]


class SQLCommand(gdb.Command):
  """Displays the result of a SQL statement using SQLite engine.
  First argument is the SQL statement specified as a string."""

  def __init__ (self):
    super(SQLCommand, self).__init__ ("sql", gdb.COMMAND_NONE, gdb.COMPLETE_NONE)

  def invoke (self, stmt, from_tty):
    load_sharedobject()
    try:
      gdb.execute("sdh-enable", False, False)
      gdb.execute('init-if-undefined $sdh_separator = (const char*)"|"', False, False)
      if (len(stmt.replace(" ", "")) == 0) or (stmt.replace(" ", "") == "\"\""):
        raise gdb.GdbError("SDH error: Invalid input")
      s = 'set variable $sdh_result = (const char*)sdh_exec((const char*)' + stmt + ', '
      if gdb.parse_and_eval("$sdh_db") != 0:
        s = s + '$sdh_db'
      elif gdb.parse_and_eval("$sdh_ppDb") != 0:
        s = s + '*$sdh_ppDb'
      else:
        raise gdb.GdbError("SDH error: SQLite DB handle cannot be found")
      s = s + ', "' + gdb.parse_and_eval("$sdh_separator").string() + '")'
      all_breakpoints_state = breakpoints_disable()
      gdb.execute(s, False, False)
      gdb.execute('printf "%s", $sdh_result', False, False)
      gdb.execute('call (void)free((void*)$sdh_result)', False, False)
      breakpoints_enable(all_breakpoints_state)
    except gdb.GdbError:
      raise
    except:
      raise gdb.GdbError("SDH error: Couldn't call helper library or invalid input")

SQLCommand()


class SQL(gdb.Function):
  def __init__(self):
    super(SQL, self).__init__("sql")

  def invoke(self, stmt):
    # SQL command already verifies so for speed considerations we don't want to double check
    load_sharedobject()
    try:
      if len(stmt.string().replace(" ", "").replace("\t", "").replace("\n", "")) == 0:
        raise gdb.GdbError("SDH error: Invalid input")
      s = 'sql "' + stmt.string().replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\\n") + '"'
      return gdb.execute(s, False, True)
    except gdb.GdbError:
      raise
    except:
      raise gdb.GdbError("SDH error: Couldn't call sql command or invalid input")

SQL()


class SQLAt(gdb.Function):
  def __init__(self):
    super(SQLAt, self).__init__("sqlat")

  def invoke(self, stmt, at_spec):
    load_sharedobject()
    try:
      gdb.execute("sdh-enable", False, False)
      gdb.execute('init-if-undefined $sdh_separator = (const char*)"|"', False, False)
      if len(stmt.string().replace(" ", "").replace("\t", "").replace("\n", "")) == 0:
        raise gdb.GdbError("SDH error: invalid input")
      #TODO check at_spec validity
      s = 'set variable $sdh_result = sdh_exec_at((const char*)"' + stmt.string().replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\\n") + '", '
      s = s + '(const char*)"' + at_spec.string().replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\\n") + '", '
      if gdb.parse_and_eval("$sdh_db") != 0:
        s = s + '$sdh_db'
      elif gdb.parse_and_eval("$sdh_ppDb") != 0:
        s = s + '*$sdh_ppDb'
      else:
        raise gdb.GdbError("SDH error: SQLite DB handle cannot be found")
      s = s + ', "' + gdb.parse_and_eval("$sdh_separator").string() + '")'
      all_breakpoints_state = breakpoints_disable()
      gdb.execute(s, False, False)
      ret_val = gdb.parse_and_eval("(const char*)$sdh_result")
      gdb.execute('call (void)free((void*)$sdh_result)', False, False)
      breakpoints_enable(all_breakpoints_state)
      return ret_val
    except gdb.GdbError:
      raise
    except:
      raise gdb.GdbError("SDH error: Couldn't call helper library or invalid input")

SQLAt()


class SQLCount(gdb.Function):
  def __init__(self):
    super(SQLCount, self).__init__("sqlcount")

  def invoke(self, stmt):
    load_sharedobject()
    try:
      gdb.execute("sdh-enable", False, False)
      if len(stmt.string().replace(" ", "").replace("\t", "").replace("\n", "")) == 0:
        return -1
      s = 'sdh_exec_count((const char*)"' + stmt.string().replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\\n") + '", '
      if gdb.parse_and_eval("$sdh_db") != 0:
        s = s + '$sdh_db'
      elif gdb.parse_and_eval("$sdh_ppDb") != 0:
        s = s + '*$sdh_ppDb'
      else:
        print("SDH error: SQLite DB handle cannot be found")
        return -1
      s = s + ')'
      all_breakpoints_state = breakpoints_disable()
      count = gdb.parse_and_eval(s)
      breakpoints_enable(all_breakpoints_state)
      return count
    except gdb.GdbError:
      raise
    except:
      print("SDH error: Couldn't call helper library or invalid input")
      return -1

SQLCount()

