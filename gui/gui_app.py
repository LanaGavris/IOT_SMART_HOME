"""
Server Room Safety — Main GUI Dashboard (HiveMQ edition)
=========================================================
Real-time Tkinter dashboard connected to broker.hivemq.com
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tkinter as tk
from tkinter import font as tkfont
import paho.mqtt.client as mqtt
import json, threading
from datetime import datetime
from collections import deque
from config import BROKER_HOST, BROKER_PORT, KEEPALIVE, T, THRESHOLDS, PROJECT_ID

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates

HISTORY_LEN = 60

CLR = {
    "bg":      "#0d1117", "panel":   "#161b22", "border":  "#30363d",
    "text":    "#e6edf3", "subtext": "#8b949e", "green":   "#3fb950",
    "yellow":  "#d29922", "red":     "#f85149", "blue":    "#58a6ff",
    "purple":  "#bc8cff", "cyan":    "#39d353", "chart_bg":"#0d1117",
}


# ─── Shared state ──────────────────────────────────────────────────────────────
class AppState:
    def __init__(self):
        self.lock    = threading.Lock()
        self.sensors = {k: deque(maxlen=HISTORY_LEN)
                        for k in ("temperature","humidity","smoke","co2")}
        self.times   = {k: deque(maxlen=HISTORY_LEN)
                        for k in ("temperature","humidity","smoke","co2")}
        self.latest  = {k: None for k in ("temperature","humidity","smoke","co2")}
        self.devices = {"fan":"—","cooling":"—","door":"—","fan_speed":0}
        self.alerts  = []
        self.connected = False


state = AppState()
_mqtt_client = None


# ─── MQTT ──────────────────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    with state.lock:
        state.connected = (rc == 0)
    if rc == 0:
        for key in T.values():
            client.subscribe(key)
    else:
        print(f"[GUI] Connection failed rc={rc}")


def on_disconnect(client, userdata, rc):
    with state.lock:
        state.connected = False


def on_message(client, userdata, msg):
    topic = msg.topic
    try:
        payload = json.loads(msg.payload.decode())
    except Exception:
        return
    now = datetime.now()
    with state.lock:
        if topic == T["temperature"]:
            v = payload.get("value")
            if v is not None:
                state.sensors["temperature"].append(v)
                state.times["temperature"].append(now)
                state.latest["temperature"] = v
        elif topic == T["humidity"]:
            v = payload.get("value")
            if v is not None:
                state.sensors["humidity"].append(v)
                state.times["humidity"].append(now)
                state.latest["humidity"] = v
        elif topic == T["smoke"]:
            v = payload.get("value")
            if v is not None:
                state.sensors["smoke"].append(v)
                state.times["smoke"].append(now)
                state.latest["smoke"] = v
        elif topic == T["co2"]:
            v = payload.get("value")
            if v is not None:
                state.sensors["co2"].append(v)
                state.times["co2"].append(now)
                state.latest["co2"] = v
        elif topic == T["door"]:
            state.devices["door"] = payload.get("state","—")
        elif topic == T["fan"]:
            state.devices["fan"]       = payload.get("state","—")
            state.devices["fan_speed"] = payload.get("speed", 0)
        elif topic == T["cooling"]:
            state.devices["cooling"] = payload.get("state","—")
        elif topic in (T["warning"], T["alarm"]):
            state.alerts.insert(0, {
                "timestamp": payload.get("timestamp", now.isoformat()),
                "level":     payload.get("level","INFO"),
                "message":   payload.get("message", str(payload)),
            })
            state.alerts = state.alerts[:200]


def send_command(topic, command, speed=None):
    if _mqtt_client:
        p = {"command": command}
        if speed is not None:
            p["speed"] = speed
        _mqtt_client.publish(topic, json.dumps(p), qos=1)


# ─── GUI ───────────────────────────────────────────────────────────────────────
class Dashboard:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Server Room Safety — {PROJECT_ID}")
        self.root.configure(bg=CLR["bg"])
        self.root.geometry("1280x820")
        self.root.minsize(900, 640)
        self._fonts()
        self._build()
        self._start_mqtt()
        self.root.after(1000, self._tick)

    def _fonts(self):
        self.f_title = tkfont.Font(family="Helvetica", size=13, weight="bold")
        self.f_value = tkfont.Font(family="Courier",   size=28, weight="bold")
        self.f_unit  = tkfont.Font(family="Helvetica", size=11)
        self.f_label = tkfont.Font(family="Helvetica", size=10)
        self.f_alert = tkfont.Font(family="Courier",   size=9)
        self.f_small = tkfont.Font(family="Helvetica", size=9)

    def _build(self):
        # Title bar
        bar = tk.Frame(self.root, bg=CLR["panel"], height=48)
        bar.pack(fill=tk.X)
        tk.Label(bar, text="🖥  SERVER ROOM SAFETY MONITOR",
                 bg=CLR["panel"], fg=CLR["blue"],
                 font=self.f_title, pady=10).pack(side=tk.LEFT, padx=16)

        # Broker label
        tk.Label(bar, text=f"Broker: {BROKER_HOST}  |  {PROJECT_ID}",
                 bg=CLR["panel"], fg=CLR["subtext"],
                 font=self.f_small).pack(side=tk.LEFT, padx=8)

        self.lbl_conn = tk.Label(bar, text="● CONNECTING…",
                                 bg=CLR["panel"], fg=CLR["yellow"],
                                 font=self.f_small)
        self.lbl_conn.pack(side=tk.RIGHT, padx=16)
        self.lbl_time = tk.Label(bar, text="", bg=CLR["panel"],
                                 fg=CLR["subtext"], font=self.f_small)
        self.lbl_time.pack(side=tk.RIGHT, padx=8)

        # Main split
        main  = tk.Frame(self.root, bg=CLR["bg"])
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        left  = tk.Frame(main, bg=CLR["bg"])
        right = tk.Frame(main, bg=CLR["bg"], width=320)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(8,0))
        right.pack_propagate(False)

        self._gauges(left)
        self._charts(left)
        self._right_panel(right)

    def _gauges(self, parent):
        row = tk.Frame(parent, bg=CLR["bg"])
        row.pack(fill=tk.X, pady=(0,8))
        specs = [
            ("temperature","Temperature","°C",  CLR["red"]),
            ("humidity",   "Humidity",   "%",   CLR["blue"]),
            ("smoke",      "Smoke",      "ppm", CLR["yellow"]),
            ("co2",        "CO₂",        "ppm", CLR["purple"]),
        ]
        self.g_val    = {}
        self.g_status = {}
        self.g_frame  = {}
        for key, name, unit, color in specs:
            fr = tk.Frame(row, bg=CLR["panel"],
                          highlightbackground=CLR["border"],
                          highlightthickness=1)
            fr.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
            self.g_frame[key] = fr
            tk.Label(fr, text=name, bg=CLR["panel"], fg=CLR["subtext"],
                     font=self.f_label, pady=6).pack()
            vl = tk.Label(fr, text="—", bg=CLR["panel"],
                          fg=color, font=self.f_value)
            vl.pack()
            tk.Label(fr, text=unit, bg=CLR["panel"], fg=CLR["subtext"],
                     font=self.f_unit, pady=4).pack()
            sl = tk.Label(fr, text="●  OK", bg=CLR["panel"],
                          fg=CLR["green"], font=self.f_small, pady=6)
            sl.pack()
            self.g_val[key]    = vl
            self.g_status[key] = sl

    def _charts(self, parent):
        self.fig = Figure(figsize=(8,4.5), facecolor=CLR["chart_bg"])
        self.fig.subplots_adjust(hspace=0.5, left=0.07, right=0.97, top=0.92, bottom=0.12)
        specs = [
            ("temperature","Temperature (°C)",CLR["red"],    1),
            ("humidity",   "Humidity (%)",    CLR["blue"],   2),
            ("smoke",      "Smoke (ppm)",     CLR["yellow"], 3),
            ("co2",        "CO₂ (ppm)",       CLR["purple"], 4),
        ]
        self.axes  = {}
        self.lines = {}
        for key, title, color, idx in specs:
            ax = self.fig.add_subplot(2,2,idx)
            ax.set_facecolor(CLR["panel"])
            ax.tick_params(colors=CLR["subtext"], labelsize=7)
            for sp in ax.spines.values():
                sp.set_edgecolor(CLR["border"])
            ax.set_title(title, color=CLR["text"], fontsize=8, pad=4)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
            ax.xaxis.set_major_locator(mdates.SecondLocator(interval=30))
            import matplotlib.pyplot as plt
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right", fontsize=6)
            line, = ax.plot([], [], color=color, linewidth=1.5)
            th = THRESHOLDS.get(key,{})
            ax.axhline(y=th.get("warning",0), color=CLR["yellow"],
                       linewidth=0.8, linestyle="--", alpha=0.6)
            ax.axhline(y=th.get("alarm",0),   color=CLR["red"],
                       linewidth=0.8, linestyle="--", alpha=0.6)
            self.axes[key]  = ax
            self.lines[key] = line

        canvas = FigureCanvasTkAgg(self.fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas = canvas

    def _right_panel(self, parent):
        # Devices
        dev = tk.LabelFrame(parent, text=" Devices & Relays ",
                            bg=CLR["panel"], fg=CLR["subtext"],
                            font=self.f_label, relief=tk.FLAT,
                            highlightbackground=CLR["border"], highlightthickness=1)
        dev.pack(fill=tk.X, pady=(0,8))
        self.dev_lbl = {}
        for key, label, color in [
            ("door",    "🚪 Door",    CLR["text"]),
            ("fan",     "💨 Fan",     CLR["cyan"]),
            ("cooling", "❄️  Cooling", CLR["blue"]),
        ]:
            row = tk.Frame(dev, bg=CLR["panel"])
            row.pack(fill=tk.X, padx=10, pady=4)
            tk.Label(row, text=label, bg=CLR["panel"], fg=CLR["subtext"],
                     font=self.f_label, width=12, anchor=tk.W).pack(side=tk.LEFT)
            vl = tk.Label(row, text="—", bg=CLR["panel"],
                          fg=color, font=self.f_label, anchor=tk.E)
            vl.pack(side=tk.RIGHT)
            self.dev_lbl[key] = vl
        spd_row = tk.Frame(dev, bg=CLR["panel"])
        spd_row.pack(fill=tk.X, padx=10, pady=(0,6))
        tk.Label(spd_row, text="🎛  Fan Speed", bg=CLR["panel"], fg=CLR["subtext"],
                 font=self.f_label, width=12, anchor=tk.W).pack(side=tk.LEFT)
        self.lbl_spd = tk.Label(spd_row, text="0%", bg=CLR["panel"],
                                fg=CLR["cyan"], font=self.f_label, anchor=tk.E)
        self.lbl_spd.pack(side=tk.RIGHT)

        # Controls
        ctrl = tk.LabelFrame(parent, text=" Manual Controls ",
                             bg=CLR["panel"], fg=CLR["subtext"],
                             font=self.f_label, relief=tk.FLAT,
                             highlightbackground=CLR["border"], highlightthickness=1)
        ctrl.pack(fill=tk.X, pady=(0,8))
        for label, cmd, color in [
            ("Fan ON",      lambda: send_command(T["ctrl_fan"],     "ON",  speed=80), CLR["green"]),
            ("Fan OFF",     lambda: send_command(T["ctrl_fan"],     "OFF"),            CLR["red"]),
            ("Cooling ON",  lambda: send_command(T["ctrl_cooling"], "ON"),             CLR["blue"]),
            ("Cooling OFF", lambda: send_command(T["ctrl_cooling"], "OFF"),            CLR["yellow"]),
        ]:
            tk.Button(ctrl, text=label, command=cmd,
                      bg=CLR["panel"], fg=color,
                      activebackground=CLR["border"],
                      font=self.f_label, relief=tk.FLAT,
                      pady=5, padx=8, cursor="hand2").pack(fill=tk.X, padx=10, pady=3)

        # Alerts log
        al = tk.LabelFrame(parent, text=" Alerts & Events ",
                           bg=CLR["panel"], fg=CLR["subtext"],
                           font=self.f_label, relief=tk.FLAT,
                           highlightbackground=CLR["border"], highlightthickness=1)
        al.pack(fill=tk.BOTH, expand=True)
        self.alert_box = tk.Text(al, bg=CLR["bg"], fg=CLR["text"],
                                 font=self.f_alert, state=tk.DISABLED,
                                 wrap=tk.WORD, relief=tk.FLAT, padx=6, pady=6)
        self.alert_box.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.alert_box.tag_config("ALARM",   foreground=CLR["red"])
        self.alert_box.tag_config("WARNING", foreground=CLR["yellow"])
        self.alert_box.tag_config("INFO",    foreground=CLR["green"])
        self.alert_box.tag_config("TIME",    foreground=CLR["subtext"])

    # ── MQTT startup ─────────────────────────────────────────────────────────
    def _start_mqtt(self):
        global _mqtt_client
        client = mqtt.Client(f"gui_dashboard_{PROJECT_ID}")
        client.on_connect    = on_connect
        client.on_disconnect = on_disconnect
        client.on_message    = on_message
        _mqtt_client = client
        def _run():
            try:
                client.connect(BROKER_HOST, BROKER_PORT, KEEPALIVE)
                client.loop_forever()
            except Exception as e:
                print(f"[GUI] MQTT error: {e}")
        threading.Thread(target=_run, daemon=True).start()

    # ── Refresh ──────────────────────────────────────────────────────────────
    def _tick(self):
        self._refresh()
        self.root.after(1000, self._tick)

    def _refresh(self):
        self.lbl_time.config(text=datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
        with state.lock:
            connected = state.connected
            latest    = dict(state.latest)
            sensors   = {k: list(v) for k, v in state.sensors.items()}
            times     = {k: list(v) for k, v in state.times.items()}
            devs      = dict(state.devices)
            alerts    = list(state.alerts[:30])

        # Connection
        self.lbl_conn.config(
            text="● CONNECTED" if connected else "● OFFLINE",
            fg=CLR["green"] if connected else CLR["red"])

        # Gauges
        for key, vl in self.g_val.items():
            v = latest.get(key)
            if v is None:
                continue
            vl.config(text=f"{v:.1f}")
            th = THRESHOLDS.get(key, {})
            fr = self.g_frame[key]
            sl = self.g_status[key]
            if v >= th.get("alarm", float("inf")):
                sl.config(text="● ALARM",   fg=CLR["red"])
                fr.config(highlightbackground=CLR["red"])
            elif v >= th.get("warning", float("inf")):
                sl.config(text="● WARNING", fg=CLR["yellow"])
                fr.config(highlightbackground=CLR["yellow"])
            else:
                sl.config(text="●  OK",     fg=CLR["green"])
                fr.config(highlightbackground=CLR["border"])

        # Charts
        changed = False
        for key, ax in self.axes.items():
            y = sensors[key]; x = times[key]
            if len(y) < 2:
                continue
            self.lines[key].set_data(x, y)
            ax.relim(); ax.autoscale_view(tight=True)
            changed = True
        if changed:
            self.fig.autofmt_xdate()
            self.canvas.draw_idle()

        # Devices
        door_color = CLR["red"] if devs["door"] == "OPEN" else CLR["green"]
        self.dev_lbl["door"].config(text=devs.get("door","—"), fg=door_color)
        fan_state = devs.get("fan","—")
        self.dev_lbl["fan"].config(
            text=fan_state,
            fg=CLR["cyan"] if fan_state == "ON" else CLR["subtext"])
        cool_state = devs.get("cooling","—")
        self.dev_lbl["cooling"].config(
            text=cool_state,
            fg=CLR["blue"] if cool_state == "ON" else CLR["subtext"])
        self.lbl_spd.config(text=f"{devs.get('fan_speed',0):.0f}%")

        # Alerts
        self.alert_box.config(state=tk.NORMAL)
        self.alert_box.delete("1.0", tk.END)
        for a in alerts:
            ts_str = a.get("timestamp","")[:19].replace("T"," ")
            lvl    = a.get("level","INFO")
            msg    = a.get("message","")
            self.alert_box.insert(tk.END, f"[{ts_str}]\n", "TIME")
            self.alert_box.insert(tk.END, f"{msg}\n\n", lvl)
        self.alert_box.config(state=tk.DISABLED)


def main():
    root = tk.Tk()
    Dashboard(root)
    root.mainloop()


if __name__ == "__main__":
    main()
