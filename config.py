"""
config.py — Central configuration for Server Room Safety
=========================================================
Change MQTT settings here once — all modules import from this file.
"""

import uuid

# ─── HiveMQ Public Broker ──────────────────────────────────────────────────────
BROKER_HOST = "broker.hivemq.com"
BROKER_PORT = 1883          # plain TCP
# BROKER_PORT = 8883        # TLS (uncomment if needed)
KEEPALIVE   = 60

# ─── Unique project prefix ─────────────────────────────────────────────────────
# IMPORTANT: HiveMQ is a PUBLIC broker shared by thousands of users.
# A unique prefix prevents collisions with other projects using the same topic names.
# Change this to something personal, e.g. your student ID or name.
PROJECT_ID  = "serverroom_safety_g7x2"   # <-- change if needed

# ─── Topic definitions ────────────────────────────────────────────────────────
T = {
    "temperature":  f"{PROJECT_ID}/temperature",
    "humidity":     f"{PROJECT_ID}/humidity",
    "smoke":        f"{PROJECT_ID}/smoke",
    "co2":          f"{PROJECT_ID}/co2",
    "door":         f"{PROJECT_ID}/door",
    "fan":          f"{PROJECT_ID}/fan",
    "cooling":      f"{PROJECT_ID}/cooling",
    "fan_speed":    f"{PROJECT_ID}/fan_speed",
    "warning":      f"{PROJECT_ID}/alert/warning",
    "alarm":        f"{PROJECT_ID}/alert/alarm",
    "ctrl_fan":     f"{PROJECT_ID}/control/fan",
    "ctrl_cooling": f"{PROJECT_ID}/control/cooling",
}

# ─── Thresholds ───────────────────────────────────────────────────────────────
THRESHOLDS = {
    "temperature": {"warning": 28.0,   "alarm": 35.0,   "unit": "°C"},
    "humidity":    {"warning": 70.0,   "alarm": 85.0,   "unit": "%"},
    "smoke":       {"warning": 200.0,  "alarm": 500.0,  "unit": "ppm"},
    "co2":         {"warning": 1000.0, "alarm": 2000.0, "unit": "ppm"},
}

# ─── Publish intervals (seconds) ──────────────────────────────────────────────
INTERVAL_DHT    = 2
INTERVAL_SMOKE  = 3
INTERVAL_BUTTON = 5
