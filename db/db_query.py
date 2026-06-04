"""
DB Query Helper — Server Room Safety
=====================================
Handy CLI for inspecting the SQLite database without a GUI.
Usage:
    python db_query.py                    # summary
    python db_query.py --table readings   # last 20 sensor readings
    python db_query.py --table alerts     # all alerts
    python db_query.py --table devices    # device state changes
    python db_query.py --export csv       # export all tables to CSV
"""

import sqlite3
import os
import argparse
import csv
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "serverroom.db")


def connect():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database not found: {DB_PATH}")
        print("  Run data_manager.py first, or: python db/init_db.py")
        return None
    return sqlite3.connect(DB_PATH)


def show_summary(conn):
    c = conn.cursor()
    print("\n" + "=" * 50)
    print("  Server Room Safety — DB Summary")
    print("=" * 50)
    for table, label in [
        ("sensor_readings", "Sensor Readings"),
        ("device_states",   "Device State Changes"),
        ("alerts",          "Alerts (WARNING + ALARM)"),
    ]:
        c.execute(f"SELECT COUNT(*) FROM {table}")
        count = c.fetchone()[0]
        print(f"  {label:30s} {count:>6} rows")

    # Latest readings
    print("\n  Latest sensor values:")
    for stype in ["temperature", "humidity", "smoke", "co2"]:
        c.execute(
            "SELECT value, unit, timestamp FROM sensor_readings "
            "WHERE sensor_type=? ORDER BY id DESC LIMIT 1",
            (stype,),
        )
        row = c.fetchone()
        if row:
            print(f"    {stype:15s} {row[0]:8.2f} {row[1]:8s}  @ {row[2][:19]}")
        else:
            print(f"    {stype:15s} no data yet")

    # Alert breakdown
    print("\n  Alert breakdown:")
    for level in ["WARNING", "ALARM"]:
        c.execute("SELECT COUNT(*) FROM alerts WHERE level=?", (level,))
        print(f"    {level:10s} {c.fetchone()[0]:>5}")
    print()


def show_readings(conn, n=20):
    c = conn.cursor()
    c.execute(
        "SELECT timestamp, sensor_type, value, unit FROM sensor_readings "
        "ORDER BY id DESC LIMIT ?", (n,)
    )
    rows = c.fetchall()
    print(f"\n  Last {n} sensor readings (newest first):")
    print(f"  {'Timestamp':20s}  {'Sensor':15s}  {'Value':>10}  Unit")
    print("  " + "-" * 60)
    for r in rows:
        print(f"  {r[0][:19]:20s}  {r[1]:15s}  {r[2]:>10.2f}  {r[3]}")


def show_alerts(conn, n=50):
    c = conn.cursor()
    c.execute(
        "SELECT timestamp, level, sensor_type, value, message FROM alerts "
        "ORDER BY id DESC LIMIT ?", (n,)
    )
    rows = c.fetchall()
    print(f"\n  Last {n} alerts (newest first):")
    for r in rows:
        lvl_marker = "🚨" if r[1] == "ALARM" else "⚠️ "
        print(f"  {r[0][:19]}  {lvl_marker} {r[1]:8s}  {r[4]}")


def show_devices(conn, n=30):
    c = conn.cursor()
    c.execute(
        "SELECT timestamp, device, state, extra FROM device_states "
        "ORDER BY id DESC LIMIT ?", (n,)
    )
    rows = c.fetchall()
    print(f"\n  Last {n} device state changes (newest first):")
    print(f"  {'Timestamp':20s}  {'Device':10s}  {'State':10s}  Extra")
    print("  " + "-" * 60)
    for r in rows:
        print(f"  {r[0][:19]:20s}  {r[1]:10s}  {r[2]:10s}  {r[3] or ''}")


def export_csv(conn):
    export_dir = os.path.join(os.path.dirname(__file__), "exports")
    os.makedirs(export_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    tables = {
        "sensor_readings": "SELECT * FROM sensor_readings ORDER BY id",
        "device_states":   "SELECT * FROM device_states ORDER BY id",
        "alerts":          "SELECT * FROM alerts ORDER BY id",
    }
    for table, query in tables.items():
        path = os.path.join(export_dir, f"{table}_{ts}.csv")
        c = conn.cursor()
        c.execute(query)
        rows = c.fetchall()
        headers = [d[0] for d in c.description]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(headers)
            w.writerows(rows)
        print(f"  Exported {len(rows):5d} rows → {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Server Room DB Inspector")
    parser.add_argument("--table",  choices=["readings", "alerts", "devices"],
                        default=None)
    parser.add_argument("--export", choices=["csv"], default=None)
    parser.add_argument("--n", type=int, default=20, help="Rows to display")
    args = parser.parse_args()

    conn = connect()
    if conn is None:
        exit(1)

    if args.export == "csv":
        print("\n  Exporting all tables to CSV…")
        export_csv(conn)
    elif args.table == "readings":
        show_readings(conn, args.n)
    elif args.table == "alerts":
        show_alerts(conn, args.n)
    elif args.table == "devices":
        show_devices(conn, args.n)
    else:
        show_summary(conn)

    conn.close()
