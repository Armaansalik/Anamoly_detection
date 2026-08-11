"""SentinelAgent sensor simulator.

Streams realistic telemetry for 3 manufacturing machines and 2 servers into a
running backend, occasionally injecting anomalies to exercise detection,
reasoning and actions.

Usage:
    py simulator/sensor_simulator.py --url http://localhost:8000 --interval 2
"""

from __future__ import annotations

import argparse
import random
import time

import requests

MACHINES = ["machine_01", "machine_02", "machine_03"]
SERVERS = ["server_a", "server_b"]

BASE_MACHINE = {
    "temperature": (75.0, 2.0),
    "vibration": (3.0, 0.5),
    "current": (11.0, 1.5),
    "rpm": (1450.0, 30.0),
}
BASE_SERVER = {
    "cpu": (40.0, 8.0),
    "memory": (55.0, 6.0),
    "latency_ms": (15.0, 4.0),
}

ANOMALY = {
    "temperature": 100.0,
    "vibration": 9.0,
    "current": 17.5,
    "rpm": 1900.0,
    "cpu": 96.0,
    "memory": 97.0,
    "latency_ms": 600.0,
}


def build_machine_payload(seed: dict, anomaly_ticks: int) -> dict:
    payload = {}
    for metric, (base, spread) in BASE_MACHINE.items():
        if anomaly_ticks > 0:
            payload[metric] = round(ANOMALY[metric] + random.uniform(-1, 1), 2)
        else:
            payload[metric] = round(base + random.uniform(-spread, spread), 2)
    return payload


def build_server_payload(seed: dict, anomaly_ticks: int) -> dict:
    payload = {}
    for metric, (base, spread) in BASE_SERVER.items():
        if anomaly_ticks > 0:
            payload[metric] = round(ANOMALY[metric] + random.uniform(-2, 2), 2)
        else:
            payload[metric] = round(base + random.uniform(-spread, spread), 2)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="SentinelAgent sensor simulator")
    parser.add_argument("--url", default="http://localhost:8000", help="backend base URL")
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between ticks")
    parser.add_argument("--minutes", type=float, default=0.0, help="stop after N minutes (0 = run forever)")
    args = parser.parse_args()

    anomalies: dict[str, int] = {}
    tick = 0
    start = time.time()
    print(f"Simulator streaming to {args.url} every {args.interval}s (Ctrl+C to stop)")

    try:
        while True:
            tick += 1
            events = []
            for machine in MACHINES:
                if random.random() < 0.08:
                    anomalies[machine] = random.randint(3, 6)
                if anomalies.get(machine, 0) > 0:
                    anomalies[machine] -= 1
                events.append(
                    {
                        "domain": "manufacturing",
                        "source_id": machine,
                        "payload": build_machine_payload({}, anomalies.get(machine, 0)),
                    }
                )
            for server in SERVERS:
                if random.random() < 0.06:
                    anomalies[server] = random.randint(3, 6)
                if anomalies.get(server, 0) > 0:
                    anomalies[server] -= 1
                events.append(
                    {
                        "domain": "server_health",
                        "source_id": server,
                        "payload": build_server_payload({}, anomalies.get(server, 0)),
                    }
                )

            ok = True
            for event in events:
                resp = requests.post(f"{args.url}/api/v1/events", json=event, timeout=10)
                if resp.status_code not in (200, 202):
                    ok = False
                    print(f"  POST failed ({resp.status_code}): {resp.text[:200]}")

            status = "OK" if ok else "ERROR"
            active = [k for k, v in anomalies.items() if v > 0]
            print(f"tick {tick:4d}  [{status}]  sources={len(events)}  active_anomalies={active}")

            if args.minutes > 0 and (time.time() - start) > args.minutes * 60:
                print("Simulator finished.")
                return
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nSimulator stopped.")


if __name__ == "__main__":
    main()
