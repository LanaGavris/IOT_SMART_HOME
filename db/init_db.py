"""
Database Initializer — Server Room Safety
==========================================
Run this script once to create the SQLite database and all tables.
The data_manager.py also calls init_db() automatically, so this
script is optional — useful for inspecting the schema manually.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "serverroom.db")


def init_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.executescript("""
        -- Sensor readings (temperature, humidity, smoke, co2, fan_speed)
        CREATE TABLE IF NOT EXISTS sensor_readings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            sensor_type TEXT    NOT NULL,   -- 'temperature'|'humidity'|'smoke'|'co2'
            value       REAL    NOT NULL,
            unit        TEXT                -- 'celsius'|'percent'|'ppm'
        );

        -- Device / relay state changes
        CREATE TABLE IF NOT EXISTS device_states (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            device      TEXT    NOT NULL,   -- 'fan'|'cooling'|'door'
            state       TEXT    NOT NULL,   -- 'ON'|'OFF'|'OPEN'|'CLOSED'
            extra       TEXT                -- e.g. 'speed=80'
        );

        -- Warning and Alarm events
        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            level       TEXT    NOT NULL,   -- 'WARNING'|'ALARM'
            sensor_type TEXT,
            value       REAL,
            message     TEXT    NOT NULL
        );

        -- Optional: human-readable event log
        CREATE TABLE IF NOT EXISTS event_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            event_type  TEXT    NOT NULL,
            description TEXT    NOT NULL
        );
    """)

    conn.commit()
    print(f"[DB] Initialized: {db_path}")
    return conn


def print_schema(conn: sqlite3.Connection):
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in c.fetchall()]
    print(f"\n[DB] Tables: {tables}")
    for t in tables:
        c.execute(f"PRAGMA table_info({t})")
        cols = c.fetchall()
        print(f"\n  {t}:")
        for col in cols:
            print(f"    {col[1]:20s} {col[2]}")


def print_summary(conn: sqlite3.Connection):
    c = conn.cursor()
    for table in ["sensor_readings", "device_states", "alerts", "event_log"]:
        try:
            c.execute(f"SELECT COUNT(*) FROM {table}")
            count = c.fetchone()[0]
            print(f"  {table:25s} → {count} rows")
        except Exception as e:
            print(f"  {table:25s} → ERROR: {e}")


if __name__ == "__main__":
    conn = init_db()
    print_schema(conn)
    print("\n[DB] Row counts:")
    print_summary(conn)
    conn.close()
