"""
run_all.py — Launch all Server Room Safety components (HiveMQ edition)
=======================================================================
Usage:
    python run_all.py
    python run_all.py --scenario heating
    python run_all.py --scenario smoke
    python run_all.py --no-gui
"""

import subprocess, sys, os, time, argparse, signal

BASE      = os.path.dirname(os.path.abspath(__file__))
processes = []


def launch(script_path, extra_args=None):
    args = [sys.executable, script_path] + (extra_args or [])
    p = subprocess.Popen(args, cwd=BASE)
    print(f"   PID {p.pid:6d}  →  {os.path.basename(script_path)}")
    return p


def stop_all(sig=None, frame=None):
    print("\n[LAUNCHER] Stopping all processes…")
    for p in processes:
        try: p.terminate()
        except Exception: pass
    for p in processes:
        try: p.wait(timeout=5)
        except Exception: p.kill()
    print("[LAUNCHER] All stopped.")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Server Room Safety Launcher (HiveMQ)")
    parser.add_argument("--scenario",
        choices=["normal","heating","cooling","critical","smoke"],
        default="normal")
    parser.add_argument("--no-gui", action="store_true")
    args = parser.parse_args()

    # Import config to show project ID
    sys.path.insert(0, BASE)
    from config import BROKER_HOST, BROKER_PORT, PROJECT_ID

    print("=" * 60)
    print("  🖥  Server Room Safety — Launcher (HiveMQ)")
    print(f"  Broker   : {BROKER_HOST}:{BROKER_PORT}")
    print(f"  Project  : {PROJECT_ID}")
    print(f"  Scenario : {args.scenario}")
    print("=" * 60)

    signal.signal(signal.SIGINT,  stop_all)
    signal.signal(signal.SIGTERM, stop_all)

    dht_sc   = args.scenario if args.scenario in ["normal","heating","cooling","critical"] else "normal"
    smoke_sc = args.scenario if args.scenario in ["normal","smoke","critical"] else "normal"

    print("\n[LAUNCHER] Starting emulators…")
    processes.append(launch(os.path.join(BASE,"emulators","dht_emulator.py"),
                            ["--scenario", dht_sc]))
    time.sleep(0.5)
    processes.append(launch(os.path.join(BASE,"emulators","smoke_emulator.py"),
                            ["--scenario", smoke_sc]))
    time.sleep(0.5)
    processes.append(launch(os.path.join(BASE,"emulators","button_emulator.py")))
    time.sleep(1)

    print("\n[LAUNCHER] Starting Data Manager…")
    processes.append(launch(os.path.join(BASE,"data_manager","data_manager.py")))
    time.sleep(1.5)

    if not args.no_gui:
        print("\n[LAUNCHER] Starting GUI Dashboard…")
        processes.append(launch(os.path.join(BASE,"gui","gui_app.py")))

    print("\n[LAUNCHER] All running. Ctrl+C to stop.\n")
    try:
        while True:
            for p in processes:
                if p.poll() is not None:
                    name = os.path.basename(p.args[1]) if len(p.args) > 1 else "?"
                    print(f"\n[LAUNCHER] {name} exited. Stopping all…")
                    stop_all()
            time.sleep(1)
    except KeyboardInterrupt:
        stop_all()


if __name__ == "__main__":
    main()
