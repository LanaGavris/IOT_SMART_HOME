"""
Smoke & CO2 Emulator — MQ-2/MQ-135 Sensor + Cooling Relay Actuator
HiveMQ public broker edition.

Topics published : <PROJECT_ID>/smoke | co2 | cooling
Topics subscribed: <PROJECT_ID>/control/cooling
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import paho.mqtt.client as mqtt
import time, random, json, math, argparse
from config import BROKER_HOST, BROKER_PORT, KEEPALIVE, T, INTERVAL_SMOKE, PROJECT_ID

SMOKE_BASE = 50
CO2_BASE   = 400
relay_cooling = False


def get_smoke(tick, scenario):
    noise = random.gauss(0, 5)
    wave  = 10 * math.sin(tick / 20)
    base  = {
        "normal":   SMOKE_BASE,
        "smoke":    SMOKE_BASE + min(tick * 3, 600),
        "critical": 550 + random.uniform(0, 150),
    }.get(scenario, SMOKE_BASE)
    return round(max(0, base + wave + noise), 1)


def get_co2(tick, scenario):
    noise = random.gauss(0, 20)
    wave  = 50 * math.sin(tick / 35 + 0.5)
    base  = {
        "normal":   CO2_BASE + 200,
        "smoke":    CO2_BASE + 800 + min(tick * 10, 1800),
        "critical": 2200 + random.uniform(0, 300),
    }.get(scenario, CO2_BASE + 200)
    return round(max(0, base + wave + noise), 1)


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[SMOKE] Connected → {BROKER_HOST}:{BROKER_PORT}")
        client.subscribe(T["ctrl_cooling"])
        print(f"[SMOKE] Subscribed: {T['ctrl_cooling']}")
    else:
        print(f"[SMOKE] Connection failed (rc={rc})")


def on_message(client, userdata, msg):
    global relay_cooling
    try:
        payload = json.loads(msg.payload.decode())
        command = payload.get("command", "").upper()
        if msg.topic == T["ctrl_cooling"] and command in ("ON", "OFF"):
            relay_cooling = (command == "ON")
            state = "ON" if relay_cooling else "OFF"
            print(f"[SMOKE] 🔌 Cooling relay → {state}")
            client.publish(T["cooling"],
                json.dumps({"relay": "cooling", "state": state}), qos=1)
    except Exception as e:
        print(f"[SMOKE] Bad message: {e}")


def main(scenario="normal"):
    print(f"[SMOKE] HiveMQ broker: {BROKER_HOST}:{BROKER_PORT}")
    print(f"[SMOKE] Project prefix: {PROJECT_ID}")
    print(f"[SMOKE] Scenario: {scenario}\n")

    client = mqtt.Client(f"smoke_emulator_{PROJECT_ID}")
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(BROKER_HOST, BROKER_PORT, KEEPALIVE)
    except Exception as e:
        print(f"[SMOKE] Cannot connect: {e}")
        return

    client.loop_start()
    tick = 0
    try:
        while True:
            smoke = get_smoke(tick, scenario)
            co2   = get_co2(tick, scenario)
            client.publish(T["smoke"], json.dumps(
                {"sensor": "MQ-2",   "unit": "ppm", "value": smoke}), qos=1)
            client.publish(T["co2"],  json.dumps(
                {"sensor": "MQ-135", "unit": "ppm", "value": co2}),   qos=1)
            cool_icon = "❄️ ON" if relay_cooling else "⬜ OFF"
            print(f"[SMOKE] tick={tick:04d}  smoke={smoke:6.1f}ppm  co2={co2:7.1f}ppm  cooling={cool_icon}")
            tick += 1
            time.sleep(INTERVAL_SMOKE)
    except KeyboardInterrupt:
        print("[SMOKE] Stopped.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario",
        choices=["normal", "smoke", "critical"], default="normal")
    args = parser.parse_args()
    main(args.scenario)
