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

- Portal: https://localhost:8443
- SCADA: https://localhost:1881
- PLC plot 1: https://localhost:8080
- PLC plot 2: https://localhost:8081
- Collector: https://localhost:2443

## SCADA (FUXA)

Het SCADA-dashboard is automatisch gevuld: `greenhouse/scada/generate.py` leest alle `plots/*/setpoints.json` en bouwt `greenhouse/scada/appdata/project.fuxap.db` met:

- startview "Kas Overzicht" met per plot temperatuur, vocht en water-events
- per plot een eigen view met schakelaars (lampen/warmte/water), actuele waardes en de setpoints
- een ModbusTCP-device per plot (al voorgeconfigureerd op plc_ip:502)

Na het aanpassen van setpoints opnieuw genereren en de container herstarten:

```bash
python3 greenhouse/scada/generate.py
docker compose restart scada
```

### Modbus tag-map per plot-PLC

| Functie | Type | Register | Tag | Factor |
|---|---|---|---|---|
| Lampen aan/uit | coil (schrijfbaar) | 000001 | `lamps_on` | - |
| Warmte aan/uit | coil (schrijfbaar) | 000002 | `heat_on` | - |
| Water aan/uit | coil (schrijfbaar) | 000003 | `water_on` | - |
| Temperatuur | input register | 300001 | `temp_c` | /10 |
| Bodemvocht % | input register | 300002 | `soil_moisture_pct` | - |
| Gietbeurten | input register | 300003 | `water_events` | - |
| Temp setpoint | holding register | 400001 | `temp_setpoint` | /10 |
| Vocht setpoint | holding register | 400002 | `moisture_setpoint` | - |

Kant-en-klare OpenPLC-programma's liggen per plot klaar (`plots/plot-01/program.st`, `plots/plot-02/program.st`) en simuleren de actuators conform deze tag-map.

## PLC activeren (Modbus op 502)

De PLC-programma's laden automatisch bij het opstarten van de containers. Dit werkt net als bij het oilsprings-voorbeeld: `greenhouse/plc-setup.py` schrijft per plot een `appdata/` mappoatrioom (st_files/, openplc.db, active_program) dat via docker-compose wordt gemount in de PLC-container (workdir/webserver). `Start_run_mode=true` in openplc.db zorgt dat het programma meteen start en Modbus op 502 luistert; events gaan via syslog naar de collector.

Na wijzigingen in program.st:

```bash
python3 greenhouse/plc-setup.py
docker compose restart plc-plot-01 plc-plot-02
```

Krijgt de SCADA toch `ECONNREFUSED <plc-ip>:502`?

1. Wacht even - Labshock in trial-modus heeft een initialisatietijd (5 min).
2. Controleer de PLC-runtime logs: `docker compose logs plc-plot-01`.
3. Test of Modbus open staat (vanaf de host, na `docker compose up`):

```bash
nc -zv 192.168.6.10 502
nc -zv 192.168.6.11 502
```

Zodra dit `succeeded` toont, verdwijnen de SCADA-verbindingsfouten en komen de waardes levend in het dashboard.

## Koppelen aan Wazuh (externe repo)

De Wazuh-stack staat in een externe omgeving. De collector (`greenhouse/collector/config.json`) stuurt syslog door naar `syslog_ip`:

1. Pas `syslog_ip` in `greenhouse/collector/config.json` aan naar het IP van de externe Wazuh-manager (syslog listener op UDP 514).
2. Sta in de Wazuh-manager het netwerk toe dat syslog stuurt (`<allowed-ips>` in `ossec.conf`), bv. het host-IP of docker-netwerk van deze machine.
3. Herstart de collector:

```bash
docker compose restart collector
```

Bronnen die de collector monitort staan in `greenhouse/collector/sources.json` (beide PLC's + SCADA).

## Nieuwe plot toevoegen

Eén commando voegt een plot volledig toe (setpoints-bestand, PLC-service in docker-compose, collector-bron en SCADA-device + view):

```bash
python3 greenhouse/add_plot.py plot-03 peper
docker compose up -d
```

De nieuwe plot krijgt automatisch het volgende vrije IP (192.168.6.12, .13, ...) en een unieke host-poort (8082, 8083, ...). Pas daarna de setpoints in `greenhouse/plots/plot-03/setpoints.json` aan naar de gewenste plant en regenereer desgewenst de SCADA.

## Testaanpak

1. Zet een PLC-actie af (lamp/warmte/water) en controleer of de gebeurtenis in de collector verschijnt.
2. Controleer of de gebeurtenis in de Wazuh-indices landt.
3. Bouw daarna regels/correlaties in Wazuh op plot-events (bv. beregening buiten venster, temperatuur-bypass, SCADA-write zonder commando).
