# 🖥️ Server Room Safety — IoT Monitoring System (HiveMQ edition)

Real-time IoT monitoring for server room environmental safety.  
**Broker:** `broker.hivemq.com:1883` (public, no auth required)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      EMULATORS (Producers)                      │
│  dht_emulator.py  │  smoke_emulator.py  │  button_emulator.py  │
│  (Temp/Humidity)  │  (Smoke/CO2+Relay)  │  (Door/Fan Relay)    │
└────────────────────────────┬────────────────────────────────────┘
                             │ MQTT  broker.hivemq.com:1883
┌────────────────────────────▼────────────────────────────────────┐
│                      DATA MANAGER APP                           │
│  data_manager.py — Collect, store SQLite, send Warning/Alarm    │
└────────────────────────────┬────────────────────────────────────┘
                             │ MQTT + SQLite
┌────────────────────────────▼────────────────────────────────────┐
│                        MAIN GUI APP                             │
│  gui_app.py — Live dashboard, charts, alerts, relay controls    │
└─────────────────────────────────────────────────────────────────┘
```

## ⚠️ Public Broker Note

`broker.hivemq.com` is a **shared public broker**.  
All MQTT topics are prefixed with a unique project ID defined in `config.py`:

```python
PROJECT_ID = "serverroom_safety_g7x2"   
```

All topics become: `serverroom_safety_g7x2/temperature`, etc.  
This prevents collisions with other users on the same broker.

## MQTT Topics (with PROJECT_ID prefix)

| Topic | Description |
|-------|-------------|
| `{id}/temperature` | Temperature (°C) |
| `{id}/humidity` | Humidity (%) |
| `{id}/smoke` | Smoke level (ppm) |
| `{id}/co2` | CO2 level (ppm) |
| `{id}/door` | Door OPEN / CLOSED |
| `{id}/fan` | Fan relay state + speed |
| `{id}/cooling` | Cooling relay state |
| `{id}/fan_speed` | Fan speed % (knob) |
| `{id}/alert/warning` | Warning messages |
| `{id}/alert/alarm` | Critical alarm messages |
| `{id}/control/fan` | Fan control commands |
| `{id}/control/cooling` | Cooling control commands |

## Thresholds

| Sensor | Warning | Alarm | Auto-action |
|--------|---------|-------|-------------|
| Temperature | > 28 °C | > 35 °C | Fan 100% + Cooling ON |
| Humidity | > 70 % | > 85 % | Alert only |
| Smoke | > 200 ppm | > 500 ppm | Fan 100% |
| CO2 | > 1000 ppm | > 2000 ppm | Alert only |

## Requirements

```bash
pip install paho-mqtt matplotlib
```

No local broker needed — uses `broker.hivemq.com` directly.

## Quick Start

```bash
# Single command (all components)
python run_all.py

# With scenario
python run_all.py --scenario heating    # temperature rises → alarm
python run_all.py --scenario smoke      # smoke rises → alarm
python run_all.py --no-gui              # headless / server mode
```

## Manual Start (4 terminals)

```bash
# Terminal 1 — Data Manager
python data_manager/data_manager.py

# Terminal 2 — GUI
python gui/gui_app.py

# Terminal 3 — DHT emulator
python emulators/dht_emulator.py --scenario heating

# Terminal 4 — Smoke & Button
python emulators/smoke_emulator.py &
python emulators/button_emulator.py
```

## Project Structure

```
ServerRoomSafety/
├── config.py                 ← ⭐ Central config (broker, topics, thresholds)
├── run_all.py                ← All-in-one launcher
├── requirements.txt
├── README.md
├── emulators/
│   ├── dht_emulator.py       # DHT22: temperature & humidity
│   ├── smoke_emulator.py     # MQ-2/MQ-135: smoke/CO2 + cooling relay
│   └── button_emulator.py    # Door contact + knob + fan relay
├── data_manager/
│   └── data_manager.py       # MQTT → SQLite + alert engine
├── gui/
│   └── gui_app.py            # Tkinter real-time dashboard
└── db/
    ├── init_db.py
    ├── db_query.py
    └── serverroom.db         # auto-created
```
