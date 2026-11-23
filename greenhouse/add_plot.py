#!/usr/bin/env python3
"""Add a new plot to the greenhouse lab in one command.

Creates the plot setpoints file, registers the plot in the collector,
adds the PLC service to docker-compose.yml and regenerates the SCADA project.

Usage: python3 greenhouse/add_plot.py <plot-id> <plant_type>
Example: python3 greenhouse/add_plot.py plot-03 pepper
"""

import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(ROOT, ".."))
PLOTS_DIR = os.path.join(ROOT, "plots")
COMPOSE = os.path.join(REPO, "docker-compose.yml")
SOURCES = os.path.join(ROOT, "collector", "sources.json")

BASE_IP = "192.168.6."
FIRST_IP_LAST_OCTET = 10
FIRST_HOST_PORT = 8080


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    plot_id, plant = sys.argv[1], sys.argv[2].lower()
    axis = sys.argv[3] if len(sys.argv) > 3 else None

    plot_dir = os.path.join(PLOTS_DIR, plot_id)
    if os.path.exists(plot_dir):
        raise SystemExit(f"{plot_id} bestaat al")

    n = len(glob.glob(os.path.join(PLOTS_DIR, "*", "setpoints.json")))
    ip = axis or f"{BASE_IP}{FIRST_IP_LAST_OCTET + n}"
    host_port = FIRST_HOST_PORT + n
    os.makedirs(plot_dir, exist_ok=True)

    setpoints = {
        "plot": plot_id,
        "plant_type": plant,
        "plc_ip": ip,
        "scada_ip": "192.168.6.20",
        "setpoints": {
            "light": {"photoperiod_hours": 14, "dark_hours": 10, "dli_target_mol_m2_day": 17, "lamp_on_level_pct": 80},
            "heat": {"day_temp_c": 19.0, "night_temp_c": 15.0, "max_temp_c": 25.0, "min_temp_c": 10.0},
            "water": {"soil_moisture_pct_min": 65, "soil_moisture_pct_target": 70, "watering_times_per_day": 3, "ec_ms_cm": 2.0},
        },
        "logging": {"syslog_host": "192.168.6.40", "syslog_port": 514},
    }
    with open(os.path.join(plot_dir, "setpoints.json"), "w") as f:
        json.dump(setpoints, f, indent=2)
        f.write("\n")

    with open(SOURCES) as f:
        sources = json.load(f)
    name = f'{plot_id.replace("-", "").title()}-PLC-{plant.title()}'
    if not any(s["name"] == name for s in sources):
        sources.append({
            "name": name, "type": "plc", "ip": ip, "protocol": "syslog",
            "impact": "high", "zone": "L2", "state": "on",
        })
    with open(SOURCES, "w") as f:
        json.dump(sources, f, indent=2)
        f.write("\n")

    with open(COMPOSE) as f:
        compose = f.read()
    m = re.search(r"^  scada:$", compose, re.M)
    if not m:
        raise SystemExit("scada service niet gevonden in docker-compose.yml")
    block = (
        f'  plc-{plot_id}:\n'
        f'    image: zakharbz/labshock-plc:v1.1.1\n'
        f'    container_name: kas-plc-{plot_id}\n'
        f'    hostname: kas-plc-{plot_id}\n'
        f'    networks:\n'
        f'      ot_network:\n'
        f'        ipv4_address: {ip}\n'
        f'    ports:\n'
        f'      - "{host_port}:8080"\n'
        f'    volumes:\n'
        f'      - ./greenhouse/plots/{plot_id}/setpoints.json:/workdir/setpoints.json:ro\n\n'
    )
    compose = compose[:m.start()] + block + compose[m.start():]
    with open(COMPOSE, "w") as f:
        f.write(compose)

    subprocess.run([sys.executable, os.path.join(ROOT, "scada", "generate.py")], check=True)

    print(f"Plot toegevoegd: {plot_id} ({plant}) op {ip}, SCADA: http://localhost:{host_port}")
    print("Volgende stappen:")
    print(f"  - programmeer de PLC op http://localhost:{host_port} met de tag-map uit greenhouse/README.md")
    print("  - docker compose up -d")


if __name__ == "__main__":
    main()
