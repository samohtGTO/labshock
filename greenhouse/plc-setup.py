#!/usr/bin/env python3
"""Generate per-plot OpenPLC appdata so programs auto-load at container start.

For every greenhouse/plots/<id>/program.st this creates
greenhouse/plots/<id>/appdata/ containing:
- st_files/<id>.st          copy of program.st (CONFIGURATION appended if missing)
- st_files/blank_program.st default blank program
- openplc.db                Programs + Settings (Modbus 502, run at start, syslog)
- active_program            name of the program to load at startup

Run: python3 greenhouse/plc-setup.py
"""

import glob
import os
import re
import shutil
import sqlite3
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
PLOTS_DIR = os.path.join(ROOT, "plots")
BASE_DB = os.path.join(ROOT, "openplc.base.db")
LOGGING_HOST = "192.168.6.40"

SETTINGS = {
    "Modbus_port": "502",
    "Dnp3_port": "disabled",
    "Start_run_mode": "true",
    "Slave_polling": "100",
    "Slave_timeout": "1000",
    "Enip_port": "disabled",
    "Pstorage_polling": "disabled",
    "Syslog_server": f"{LOGGING_HOST}:514",
}

BLANK_PROGRAM = """PROGRAM prog0
  VAR
    var_in : BOOL;
    var_out : BOOL;
  END_VAR

  var_out := var_in;
END_PROGRAM


CONFIGURATION Config0

  RESOURCE Res0 ON PLC
    TASK Main(INTERVAL := T#50ms,PRIORITY := 0);
    PROGRAM Inst0 WITH Main : prog0;
  END_RESOURCE
END_CONFIGURATION
"""

CONFIGURATION_BLOCK = """

CONFIGURATION Config0

  RESOURCE Res0 ON PLC
    TASK task0(INTERVAL := T#20ms,PRIORITY := 0);
    PROGRAM instance0 WITH task0 : {prog};
  END_RESOURCE
END_CONFIGURATION
"""


def ensure_base_db():
    if os.path.exists(BASE_DB):
        return
    oil_db = os.path.normpath(os.path.join(ROOT, "..", "oilsprings", "plc", "appdata", "openplc.db"))
    if not os.path.exists(oil_db):
        raise SystemExit("basis openplc.db ontbreekt: " + oil_db)
    shutil.copyfile(oil_db, BASE_DB)


def build_plot(plot_id, program_path):
    appdata = os.path.join(PLOTS_DIR, plot_id, "appdata")
    st_dir = os.path.join(appdata, "st_files")
    os.makedirs(st_dir, exist_ok=True)

    src = open(program_path).read()
    prog_name = re.match(r"PROGRAM\s+(\w+)", src).group(1)
    if "CONFIGURATION" not in src:
        src = src.rstrip() + CONFIGURATION_BLOCK.format(prog=prog_name)
        with open(program_path, "w") as f:
            f.write(src)

    st_name = f"{plot_id}.st"
    with open(os.path.join(st_dir, st_name), "w") as f:
        f.write(src)
    with open(os.path.join(st_dir, "blank_program.st"), "w") as f:
        f.write(BLANK_PROGRAM)

    db_path = os.path.join(appdata, "openplc.db")
    shutil.copyfile(BASE_DB, db_path)
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    now = str(int(time.time()))
    cur.execute("DELETE FROM Programs")
    cur.execute(
        "INSERT INTO Programs (Prog_ID, Name, Description, File, Date_upload) VALUES (1, 'Blank Program', 'Dummy empty program', 'blank_program.st', ?)",
        (now,),
    )
    cur.execute(
        "INSERT INTO Programs (Prog_ID, Name, Description, File, Date_upload) VALUES (2, ?, 'Greenhouse plot program', ?, ?)",
        (plot_id, st_name, now),
    )
    for key, value in SETTINGS.items():
        cur.execute(
            "INSERT INTO Settings (Key, Value) VALUES (?, ?) ON CONFLICT(Key) DO UPDATE SET Value=excluded.Value",
            (key, value),
        )
    con.commit()
    con.close()

    with open(os.path.join(appdata, "active_program"), "w") as f:
        f.write(st_name)

    return st_name


def main():
    ensure_base_db()
    count = 0
    for program_path in sorted(glob.glob(os.path.join(PLOTS_DIR, "*", "program.st"))):
        plot_id = os.path.basename(os.path.dirname(program_path))
        st_name = build_plot(plot_id, program_path)
        print(f"{plot_id}: auto-load ingesteld ({st_name}, Modbus 502, syslog -> {LOGGING_HOST}:514)")
        count += 1
    print(f"{count} plot(s) klaar")


if __name__ == "__main__":
    main()
