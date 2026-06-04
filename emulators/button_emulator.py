"""
Button / Door Emulator — Knob + Button + Fan Relay Actuator
HiveMQ public broker edition.

Topics published : <PROJECT_ID>/door | fan | fan_speed
Topics subscribed: <PROJECT_ID>/control/fan
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import paho.mqtt.client as mqtt
import time, random, json, argparse
from config import BROKER_HOST, BROKER_PORT, KEEPALIVE, T, INTERVAL_BUTTON, PROJECT_ID

fan_relay_on      = False
fan_speed         = 0.0
door_open         = False
door_countdown    = 0


def simulate_knob(current):
    return round(max(0, min(100, current + random.gauss(0, 3))), 1)


def simulate_door(open_state, countdown):
    if open_state:
        countdown -= 1
        return (False, 0) if countdown <= 0 else (True, countdown)
    if random.random() < 0.05:
        return True, random.randint(2, 6)
    return False, 0


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[BUTTON] Connected → {BROKER_HOST}:{BROKER_PORT}")
        client.subscribe(T["ctrl_fan"])
        print(f"[BUTTON] Subscribed: {T['ctrl_fan']}")
    else:
        print(f"[BUTTON] Connection failed (rc={rc})")


def on_message(client, userdata, msg):
    global fan_relay_on, fan_speed
    try:
        payload = json.loads(msg.payload.decode())
        command = payload.get("command", "").upper()
        speed   = payload.get("speed", fan_speed)
        if msg.topic == T["ctrl_fan"]:
            if command == "ON":
                fan_relay_on, fan_speed = True, float(speed)
                print(f"[BUTTON] 💨 Fan ON  speed={fan_speed:.0f}%")
            elif command == "OFF":
                fan_relay_on, fan_speed = False, 0
                print("[BUTTON] 💨 Fan OFF")
            elif command == "SPEED":
                fan_speed = float(speed)
                print(f"[BUTTON] 🎛️ Fan speed → {fan_speed:.0f}%")
    except Exception as e:
        print(f"[BUTTON] Bad message: {e}")


def main(scenario="normal"):
    global door_open, door_countdown, fan_speed
    print(f"[BUTTON] HiveMQ broker: {BROKER_HOST}:{BROKER_PORT}")
    print(f"[BUTTON] Project prefix: {PROJECT_ID}")
    print(f"[BUTTON] Scenario: {scenario}\n")

    if scenario == "door_open":
        door_open, door_countdown = True, 999

    client = mqtt.Client(f"button_emulator_{PROJECT_ID}")
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(BROKER_HOST, BROKER_PORT, KEEPALIVE)
    except Exception as e:
        print(f"[BUTTON] Cannot connect: {e}")
        return

    client.loop_start()
    tick = 0
    try:
        while True:
            door_open, door_countdown = simulate_door(door_open, door_countdown)
            door_state = "OPEN" if door_open else "CLOSED"
            fan_speed  = simulate_knob(fan_speed if fan_relay_on and fan_speed > 0 else 50) \
                         if fan_relay_on else 0

            client.publish(T["door"], json.dumps(
                {"sensor": "door_contact", "state": door_state,
                 "numeric": 1 if door_open else 0}), qos=1)
            client.publish(T["fan"], json.dumps(
                {"relay": "fan", "state": "ON" if fan_relay_on else "OFF",
                 "speed": fan_speed}), qos=1)
            client.publish(T["fan_speed"], json.dumps(
                {"actuator": "knob", "unit": "percent", "value": fan_speed}), qos=1)

            d_icon = "🚪 OPEN" if door_open else "🔒 CLOSED"
            f_icon = f"💨 {'ON' if fan_relay_on else 'OFF'} ({fan_speed:.0f}%)"
            print(f"[BUTTON] tick={tick:04d}  door={d_icon}  fan={f_icon}")
            tick += 1
            time.sleep(INTERVAL_BUTTON)
    except KeyboardInterrupt:
        print("[BUTTON] Stopped.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["normal", "door_open"], default="normal")
    args = parser.parse_args()
    main(args.scenario)
