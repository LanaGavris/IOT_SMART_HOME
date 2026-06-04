"""
Data Manager — Server Room Safety (HiveMQ edition)
====================================================
1. Subscribe to all sensor MQTT topics on broker.hivemq.com
2. Write readings to SQLite database
3. Evaluate thresholds → publish WARNING / ALARM messages
4. Send automatic relay commands on alarm
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import paho.mqtt.client as mqtt
import sqlite3, json, threading, time
from datetime import datetime
from config import (BROKER_HOST, BROKER_PORT, KEEPALIVE,
                    T, THRESHOLDS, PROJECT_ID)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "serverroom.db")

# ─── Database ──────────────────────────────────────────────────────────────────
def init_db(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            sensor_type TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT
        );
        CREATE TABLE IF NOT EXISTS device_states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            device TEXT NOT NULL,
            state TEXT NOT NULL,
            extra TEXT
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            level TEXT NOT NULL,
            sensor_type TEXT,
            value REAL,
            message TEXT NOT NULL
        );
    """)
    conn.commit()
    print(f"[DB] Ready: {path}")
    return conn


def ts():
    return datetime.utcnow().isoformat()


def insert_reading(conn, sensor_type, value, unit=""):
    conn.execute(
        "INSERT INTO sensor_readings (timestamp,sensor_type,value,unit) VALUES (?,?,?,?)",
        (ts(), sensor_type, value, unit))
    conn.commit()


def insert_device(conn, device, state, extra=""):
    conn.execute(
        "INSERT INTO device_states (timestamp,device,state,extra) VALUES (?,?,?,?)",
        (ts(), device, state, extra))
    conn.commit()


def insert_alert(conn, level, sensor_type, value, message):
    conn.execute(
        "INSERT INTO alerts (timestamp,level,sensor_type,value,message) VALUES (?,?,?,?,?)",
        (ts(), level, sensor_type, value, message))
    conn.commit()


# ─── Alert engine ──────────────────────────────────────────────────────────────
_last_alert = {}


def evaluate(client, conn, sensor_type, value):
    if sensor_type not in THRESHOLDS:
        return
    th    = THRESHOLDS[sensor_type]
    level = None

    if value >= th["alarm"]:
        level = "ALARM"
        msg   = (f"🚨 ALARM: {sensor_type.upper()} critical! "
                 f"{value}{th['unit']} >= {th['alarm']}{th['unit']}")
    elif value >= th["warning"]:
        level = "WARNING"
        msg   = (f"⚠️  WARNING: {sensor_type.upper()} elevated. "
                 f"{value}{th['unit']} >= {th['warning']}{th['unit']}")

    if level is None:
        _last_alert[sensor_type] = None
        return
    if _last_alert.get(sensor_type) == level:
        return
    _last_alert[sensor_type] = level

    payload = json.dumps({
        "timestamp": ts(), "level": level,
        "sensor": sensor_type, "value": value,
        "unit": th["unit"], "threshold": th[level.lower()],
        "message": msg,
    })
    topic = T["alarm"] if level == "ALARM" else T["warning"]
    client.publish(topic, payload, qos=1)
    insert_alert(conn, level, sensor_type, value, msg)
    print(f"[ALERT] {msg}")

    # Auto-remediation
    if level == "ALARM" and sensor_type == "temperature":
        _relay(client, T["ctrl_fan"],     "ON",  speed=100)
        _relay(client, T["ctrl_cooling"], "ON")
    elif level == "WARNING" and sensor_type == "temperature":
        _relay(client, T["ctrl_fan"],     "ON",  speed=70)
        _relay(client, T["ctrl_cooling"], "ON")
    elif level == "ALARM" and sensor_type == "smoke":
        _relay(client, T["ctrl_fan"],     "ON",  speed=100)


def _relay(client, topic, command, speed=None):
    payload = {"command": command}
    if speed is not None:
        payload["speed"] = speed
    client.publish(topic, json.dumps(payload), qos=1)
    print(f"[AUTO] → {topic.split('/')[-1].upper()} {command}"
          + (f" speed={speed}" if speed else ""))


# ─── MQTT callbacks ─────────────────────────────────────────────────────────────
SUBSCRIBE_TOPICS = [
    T["temperature"], T["humidity"], T["smoke"],  T["co2"],
    T["door"],        T["fan"],      T["cooling"], T["fan_speed"],
]


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[DM] Connected → {BROKER_HOST}:{BROKER_PORT}")
        print(f"[DM] Project prefix: {PROJECT_ID}")
        for t in SUBSCRIBE_TOPICS:
            client.subscribe(t)
            print(f"[DM] Sub: {t}")
    else:
        print(f"[DM] Connection failed (rc={rc})")


def make_on_message(conn):
    def on_message(client, userdata, msg):
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode())
        except Exception:
            return

        if topic == T["temperature"]:
            v = payload.get("value")
            if v is not None:
                insert_reading(conn, "temperature", v, "celsius")
                evaluate(client, conn, "temperature", v)

        elif topic == T["humidity"]:
            v = payload.get("value")
            if v is not None:
                insert_reading(conn, "humidity", v, "percent")
                evaluate(client, conn, "humidity", v)

        elif topic == T["smoke"]:
            v = payload.get("value")
            if v is not None:
                insert_reading(conn, "smoke", v, "ppm")
                evaluate(client, conn, "smoke", v)

        elif topic == T["co2"]:
            v = payload.get("value")
            if v is not None:
                insert_reading(conn, "co2", v, "ppm")
                evaluate(client, conn, "co2", v)

        elif topic == T["door"]:
            state = payload.get("state", "UNKNOWN")
            insert_device(conn, "door", state)
            if state == "OPEN":
                wmsg = "⚠️  WARNING: Server room door OPEN!"
                client.publish(T["warning"], json.dumps({
                    "timestamp": ts(), "level": "WARNING",
                    "sensor": "door", "value": 1, "message": wmsg,
                }), qos=1)
                insert_alert(conn, "WARNING", "door", 1, wmsg)
                print(f"[ALERT] {wmsg}")

        elif topic == T["fan"]:
            insert_device(conn, "fan", payload.get("state","?"),
                          f"speed={payload.get('speed',0)}")

        elif topic == T["cooling"]:
            insert_device(conn, "cooling", payload.get("state","?"))

        elif topic == T["fan_speed"]:
            v = payload.get("value", 0)
            insert_reading(conn, "fan_speed", v, "percent")

    return on_message


def stats_loop(conn):
    while True:
        time.sleep(30)
        try:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM sensor_readings"); r = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM alerts WHERE level='WARNING'"); w = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM alerts WHERE level='ALARM'");  a = c.fetchone()[0]
            print(f"\n[DB STATS] readings={r}  warnings={w}  alarms={a}\n")
        except Exception:
            pass


def main():
    print("=" * 60)
    print("  Server Room Safety — Data Manager (HiveMQ)")
    print("=" * 60)
    conn   = init_db(DB_PATH)
    client = mqtt.Client(f"data_manager_{PROJECT_ID}")
    client.on_connect = on_connect
    client.on_message = make_on_message(conn)
    try:
        client.connect(BROKER_HOST, BROKER_PORT, KEEPALIVE)
    except Exception as e:
        print(f"[DM] Cannot connect: {e}")
        return

    threading.Thread(target=stats_loop, args=(conn,), daemon=True).start()
    print("[DM] Running. Ctrl+C to stop.\n")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("[DM] Stopped.")
    finally:
        client.disconnect()
        conn.close()


if __name__ == "__main__":
    main()
