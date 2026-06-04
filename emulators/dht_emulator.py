"""
DHT Emulator — Temperature & Humidity Sensor
Emulates a DHT22 sensor publishing to HiveMQ public broker.
Topics: <PROJECT_ID>/temperature  |  <PROJECT_ID>/humidity
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import paho.mqtt.client as mqtt
import time, random, json, math, argparse
from config import BROKER_HOST, BROKER_PORT, KEEPALIVE, T, INTERVAL_DHT, PROJECT_ID

TEMP_BASE = 22.0
HUM_BASE  = 50.0


def get_temperature(tick, scenario):
    noise = random.gauss(0, 0.3)
    wave  = 1.5 * math.sin(tick / 30)
    base  = {
        "normal":   TEMP_BASE,
        "heating":  TEMP_BASE + min(tick * 0.15, 18),
        "cooling":  max(TEMP_BASE - min(tick * 0.1, 8), 14),
        "critical": TEMP_BASE + 15 + random.uniform(0, 5),
    }.get(scenario, TEMP_BASE)
    return round(base + wave + noise, 2)


def get_humidity(tick, scenario):
    noise = random.gauss(0, 0.8)
    wave  = 3.0 * math.sin(tick / 45 + 1)
    base  = {
        "normal":   HUM_BASE,
        "heating":  HUM_BASE - 5,
        "cooling":  HUM_BASE + 15,
        "critical": HUM_BASE + 30 + random.uniform(0, 10),
    }.get(scenario, HUM_BASE)
    return round(max(0, min(100, base + wave + noise)), 2)


def on_connect(client, userdata, flags, rc):
    status = {0: "OK", 1: "Bad protocol", 2: "Bad client ID",
              3: "Unavailable", 4: "Bad credentials", 5: "Not authorized"}
    print(f"[DHT] Broker: {status.get(rc, f'rc={rc}')}")


def main(scenario="normal"):
    print(f"[DHT] HiveMQ broker: {BROKER_HOST}:{BROKER_PORT}")
    print(f"[DHT] Project prefix: {PROJECT_ID}")
    print(f"[DHT] Scenario: {scenario}\n")

    client = mqtt.Client(f"dht_emulator_{PROJECT_ID}")
    client.on_connect = on_connect
    try:
        client.connect(BROKER_HOST, BROKER_PORT, KEEPALIVE)
    except Exception as e:
        print(f"[DHT] Cannot connect: {e}")
        return

    client.loop_start()
    tick = 0
    try:
        while True:
            temp = get_temperature(tick, scenario)
            hum  = get_humidity(tick, scenario)
            client.publish(T["temperature"], json.dumps(
                {"sensor": "DHT22", "unit": "celsius", "value": temp, "tick": tick}), qos=1)
            client.publish(T["humidity"], json.dumps(
                {"sensor": "DHT22", "unit": "percent", "value": hum, "tick": tick}), qos=1)
            print(f"[DHT] tick={tick:04d}  temp={temp:5.2f}°C  hum={hum:5.2f}%")
            tick += 1
            time.sleep(INTERVAL_DHT)
    except KeyboardInterrupt:
        print("[DHT] Stopped.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario",
        choices=["normal", "heating", "cooling", "critical"], default="normal")
    args = parser.parse_args()
    main(args.scenario)
