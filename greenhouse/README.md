# Greenhouse OT Lab (Soc test)

OT-omgeving voor de kas-scenario binnen Labshock: één kas met twee plotten, elke plot heeft zijn eigen PLC die drie actoren stuurt (lampen, warmte, water). Elke plant heeft andere vereisten, vastgelegd in de setpoints per plot. De SCADA heeft zicht op beide plotten. Logging loopt via de collector en kan later worden doorgelinkt naar de externe Wazuh-omgeving.

## Topologie

| Component | Service | IP (ot_network) | Poort (host) | Doel |
|---|---|---|---|---|
| PLC plot 1 (tomaat) | `plc-plot-01` | 192.168.6.10 | 8080 | lampen, warmte, water |
| PLC plot 2 (sla) | `plc-plot-02` | 192.168.6.11 | 8081 | lampen, warmte, water |
| SCADA | `scada` | 192.168.6.20 | 1881 | overzicht van beide plotten |
| Collector | `collector` | 192.168.6.40 | 2443 | syslog verzamelen + doorsturen |
| Portal | `portal` | - | 8443 | Labshock portal/beheer |

Netwerk: `ot_network` (192.168.6.0/24).

## Setpoints per plot

- `plots/plot-01/setpoints.json` - tomaat: 16u licht, dag 21C / nacht 18C, bodemvocht 60-65%, 3x water per dag
- `plots/plot-02/setpoints.json` - slas: 14u licht, dag 19C / nacht 15C, bodemvocht 70-75%, 4x water per dag

Beide setpoints-bestanden worden als volume in de betreffende PLC-container gemount (`/workdir/setpoints.json`).

## Starten

```bash
docker compose up -d
```

Open daarna:

- SCADA: https://localhost:1881
- PLC plot 1: https://localhost:8080
- PLC plot 2: https://localhost:8081
- Collector: https://localhost:2443

## SCADA koppelen

In de SCADA (FUXA) twee apparaten toevoegen:

- Plot 1 PLC: Modbus TCP / webapi naar `192.168.6.10`
- Plot 2 PLC: Modbus TCP / webapi naar `192.168.6.11`

Tags per PLC: `lampen` (on/off + niveau), `warmte` (temperatuur setpoint/actueel), `water` (vocht + gietbeurten).

## Koppelen aan Wazuh (externe repo)

De Wazuh-stack staat in een externe omgeving. De collector (`greenhouse/collector/config.json`) stuurt syslog door naar `syslog_ip`:

1. Pas `syslog_ip` in `greenhouse/collector/config.json` aan naar het IP van de externe Wazuh-manager (syslog listener op UDP 514).
2. Sta in de Wazuh-manager het netwerk toe dat syslog stuurt (`<allowed-ips>` in `ossec.conf`), bv. het host-IP of docker-netwerk van deze machine.
3. Herstart de collector:

```bash
docker compose restart collector
```

Bronnen die de collector monitort staan in `greenhouse/collector/sources.json` (beide PLC's + SCADA).

## Testaanpak

1. Zet een PLC-actie af (lamp/warmte/water) en controleer of de gebeurtenis in de collector verschijnt.
2. Controleer of de gebeurtenis in de Wazuh-indices landt.
3. Bouw daarna regels/correlaties in Wazuh op plot-events (bv. beregening buiten venster, temperatuur-bypass, SCADA-write zonder commando).
