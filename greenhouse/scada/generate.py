#!/usr/bin/env python3
"""Generate the FUXA SCADA project (project.fuxap.db) for the greenhouse lab.

Reads greenhouse/plots/*/setpoints.json and creates:
- one ModbusTCP device per plot (lamps/heat/water coils + temp/moisture registers)
- one dashboard view per plot + an overview start view

Run: python3 greenhouse/scada/generate.py
"""

import glob
import json
import os
import sqlite3
import uuid
from xml.dom import minidom

ROOT = os.path.dirname(os.path.abspath(__file__))
PLOTS_DIR = os.path.normpath(os.path.join(ROOT, "..", "plots"))
OUT_DIR = os.path.join(ROOT, "appdata")
DB_PATH = os.path.join(OUT_DIR, "project.fuxap.db")

POLLING = 1000
VIEW_W, VIEW_H = 1920, 1080

PLC_TAG_MAP = [
    ("lamps_on", "Bool", "000000", 1, None),
    ("heat_on", "Bool", "000001", 2, None),
    ("water_on", "Bool", "000002", 3, None),
    ("temp_c", "Int16", "300000", 1, 10),
    ("soil_moisture_pct", "Int16", "300001", 2, 1),
    ("water_events", "Int16", "300002", 3, 1),
    ("temp_setpoint", "Int16", "400000", 1, 10),
    ("moisture_setpoint", "Int16", "400001", 2, 1),
]


def uid(prefix, key_len=8):
    u = uuid.uuid4().hex
    return f"{prefix}_{u[:key_len]}-{u[key_len:key_len + 6]}"


def esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_tags():
    tags = {}
    for name, ttype, memaddr, address, divisor in PLC_TAG_MAP:
        tid = uid("t")
        tags[tid] = {
            "id": tid,
            "name": name,
            "type": ttype,
            "memaddress": memaddr,
            "address": address,
            "divisor": divisor,
            "daq": {"enabled": False, "interval": 60, "changed": False, "restored": False},
        }
    return tags


def find_tag_id(tags, name):
    for tid, tag in tags.items():
        if tag["name"] == name:
            return tid
    raise KeyError(name)


def make_device(dev_id, dev_name, ip):
    return {
        "id": dev_id,
        "name": dev_name,
        "enabled": True,
        "property": {
            "address": f"{ip}:502",
            "port": None,
            "slot": None,
            "rack": None,
            "baudrate": 9600,
            "databits": 8,
            "stopbits": 1,
            "parity": "None",
            "connectionOption": "TcpPort",
            "delay": 10,
        },
        "type": "ModbusTCP",
        "polling": POLLING,
        "tags": build_tags(),
    }


def svg_label(x, y, text, size, fill="#FFFFFF"):
    gid = uid("svg")
    svg = (
        f'  <g type="svg-ext-shapes-text" id="{gid}">\n'
        f'   <text data-name="label" stroke-width="0" fill="{fill}" font-size="{size}" '
        f'font-family="Quicksand-Bold" xml:space="preserve" x="{x}" y="{y}">{esc(text)}</text>\n'
        f'  </g>\n'
    )
    item = {"id": gid, "type": "svg-ext-shapes-text", "name": "", "property": None, "label": "Shapes"}
    return svg, gid, item


def svg_value(x, y, tag_id, size=24, raw="##.#"):
    gid = uid("VAL")
    inner = uid("VAL")
    svg = (
        f'  <g data-name="output_1" id="{gid}" type="svg-ext-value" fill="#000000" stroke="#000000" '
        f'font-size="14" stroke-width="0" font-family="Quicksand-Bold" text-anchor="middle">\n'
        f'   <text data-name="shape_14" id="{inner}" stroke-width="0" fill="#FFFFFF" stroke="#000000" '
        f'font-size="{size}" font-family="Quicksand-Bold" text-anchor="start" xml:space="preserve" '
        f'x="{x}" y="{y}">{raw}</text>\n'
        f'  </g>\n'
    )
    prop = {
        "events": [],
        "actions": [],
        "address": "http://127.0.0.1:1881/_widgets/dynamicSVG/valve_3d_common1.svg",
        "variableId": tag_id,
        "variableValue": "0",
        "ranges": [{
            "min": 0, "max": 10000, "text": "", "textId": None, "color": "",
            "type": 1, "stroke": "", "fractionDigitsId": None, "fractionDigits": "1",
        }],
    }
    item = {"id": gid, "type": "svg-ext-value", "name": "output_1", "property": prop, "label": "WIDGETS"}
    return svg, gid, item


def svg_switch(x, y, tag_id):
    gid = uid("HXT")
    svg = (
        f'  <g data-name="switch_1" type="svg-ext-html_switch" fill="rgba(0,0,0,0)" '
        f'stroke="rgba(0,0,0,0)" id="{gid}">\n'
        f'   <rect data-name="shape_6" stroke-width="0" x="{x}" y="{y}" width="50" height="28" '
        f'id="{uid("svg", 14)}"/>\n'
        f'   <foreignObject x="{x}" y="{y}" height="28" width="50" id="H-{uid("HXT", 14)}">\n'
        f'    <LABEL id="T-{uid("HXT", 14)}" style="width: calc(100% - 6px); height: calc(100% - 6px); '
        f'text-align: center; background-color: rgb(191, 191, 191); color: rgb(0, 0, 0); margin: 3px; '
        f'border-radius: 4px;" class="md-switch">\n'
        f'     <NGX-SWITCH class="ng-star-inserted">\n'
        f'      <LABEL style="border-radius: 4px;" class="md-switch">\n'
        f'       <DIV style="background-color: rgb(83, 88, 95);" class="toggle-button">\n'
        f'        <INPUT type="checkbox"/>\n'
        f'        <DIV style="text-align: center; line-height: 22px; font-size: 12px; '
        f'background-color: rgb(255, 66, 69); color: rgb(0, 0, 0);" class="inner-circle"></DIV>\n'
        f'       </DIV>\n'
        f'      </LABEL>\n'
        f'     </NGX-SWITCH>\n'
        f'    </LABEL>\n'
        f'   </foreignObject>\n'
        f'  </g>\n'
    )
    prop = {
        "variableId": tag_id,
        "events": [],
        "actions": [],
        "options": {
            "offValue": 0, "onValue": 1,
            "offBackground": "#53585fff", "onBackground": "#53585fff",
            "offText": "", "onText": "",
            "offSliderColor": "#ff4245ff", "onSliderColor": "#32d74bff",
            "offTextColor": "#000", "onTextColor": "#fff",
            "fontSize": 12, "fontFamily": "", "radius": 4, "height": 22,
        },
    }
    item = {"id": gid, "type": "svg-ext-html_switch", "name": "switch_1", "property": prop, "label": "WIDGETS"}
    return svg, gid, item


def svg_frame(content, width=VIEW_W, height=VIEW_H):
    return (
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:svg="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'xmlns:html="http://www.w3.org/1999/xhtml">\n'
        f' <filter id="blur-filter" x="-3" y="-3" width="200" height="200">\n'
        f'  <feGaussianBlur stdDeviation="3"/>\n'
        f' </filter>\n'
        f' <g>\n'
        f'  <title>Layer 1</title>\n'
        f'{content} </g>\n'
        f'</svg>'
    )


def make_view(vid, name, items, content_svg):
    return {
        "id": vid,
        "name": name,
        "profile": {
            "width": VIEW_W, "height": VIEW_H, "bkcolor": "#000000ff",
            "margin": 10, "align": "topCenter", "gridType": "fixed",
        },
        "items": items,
        "variables": {},
        "svgcontent": svg_frame(content_svg),
        "type": "svg",
        "property": {"events": [], "actions": []},
    }


def load_plots():
    plots = []
    for path in sorted(glob.glob(os.path.join(PLOTS_DIR, "*", "setpoints.json"))):
        with open(path) as f:
            plots.append(json.load(f))
    if not plots:
        raise SystemExit("no plots found in " + PLOTS_DIR)
    return plots


def build_plot_view(plot, device):
    tags = device["tags"]
    sp = plot["setpoints"]
    items = {}
    svg = ""

    for svg_part, gid, item in (
        svg_label(60, 90, f'{plot["plot"]} - {plot["plant_type"]}', 34),
        svg_label(60, 130, f'PLC: {device["property"]["address"]}   Modbus TCP', 18, "#777777"),
        svg_label(340, 180, "actueel", 16, "#777777"),
        svg_label(560, 180, "setpoints", 16, "#777777"),
    ):
        svg += svg_part
        items[gid] = item

    rows = [
        ("Lampen", "lamps_on", 220, "temp_c", "Temp (C)", "Licht: {} u/dag".format(sp["light"]["photoperiod_hours"])),
        ("Warmte", "heat_on", 320, "soil_moisture_pct", "Vocht (%)",
         "Dag/nacht: {} / {} C".format(sp["heat"]["day_temp_c"], sp["heat"]["night_temp_c"])),
        ("Water", "water_on", 420, "water_events", "Water events",
         "Vocht: {} - {} %".format(sp["water"]["soil_moisture_pct_min"], sp["water"]["soil_moisture_pct_target"])),
    ]
    for label, coil, y, value_tag, value_label, setpoint_text in rows:
        for svg_part, gid, item in (
            svg_label(60, y + 20, label, 22),
            svg_label(340, y, value_label, 18, "#AAAAAA"),
        ):
            svg += svg_part
            items[gid] = item

        sw_svg, sw_gid, sw_item = svg_switch(200, y, find_tag_id(tags, coil))
        svg += sw_svg
        items[sw_gid] = sw_item

        val_svg, val_gid, val_item = svg_value(340, y + 30, find_tag_id(tags, value_tag))
        svg += val_svg
        items[val_gid] = val_item

        sp_svg, sp_gid, sp_item = svg_label(560, y + 20, setpoint_text, 18, "#AAAAAA")
        svg += sp_svg
        items[sp_gid] = sp_item

    giet_svg, giet_gid, giet_item = svg_label(
        560, 440, "Water: {} x per dag".format(sp["water"]["watering_times_per_day"]), 18, "#AAAAAA"
    )
    svg += giet_svg
    items[giet_gid] = giet_item

    vid = uid("v", 10)
    return vid, f'{plot["plot"]} - {plot["plant_type"]}', items, svg


def build_home_view(plots, devices):
    items = {}
    svg = ""
    for svg_part, gid, item in (
        svg_label(60, 90, "Kas - overzicht", 34),
        svg_label(340, 180, "Temp (C)", 18, "#AAAAAA"),
        svg_label(520, 180, "Vocht (%)", 18, "#AAAAAA"),
        svg_label(700, 180, "Water events", 18, "#AAAAAA"),
    ):
        svg += svg_part
        items[gid] = item

    y = 240
    for plot, device in zip(plots, devices):
        t_svg, t_gid, t_item = svg_label(
            60, y, f'{plot["plot"]} - {plot["plant_type"]}   ({device["property"]["address"]})', 24
        )
        svg += t_svg
        items[t_gid] = t_item

        for offset, tag_name, in ((340, "temp_c"), (520, "soil_moisture_pct"), (700, "water_events")):
            val_svg, val_gid, val_item = svg_value(60 + offset, y + 10, find_tag_id(device["tags"], tag_name))
            svg += val_svg
            items[val_gid] = val_item
        y += 120

    vid = uid("v", 10)
    return vid, "Kas Overzicht", items, svg


def build_layout(home_id):
    header_item = lambda text, idx: {
        "id": f"i_kas_label_{idx}", "type": "label",
        "marginLeft": 5, "marginRight": 5,
        "property": {"events": [], "actions": [], "variableId": None, "variableValue": "", "text": text},
        "status": {"variablesValue": {}, "onlyChange": True, "takeValue": False},
        "element": {},
    }
    return {
        "autoresize": False,
        "start": home_id,
        "navigation": {
            "mode": "void", "type": "block",
            "bkcolor": "#F4F5F7", "fgcolor": "#1D1D1D", "items": [], "logo": False,
        },
        "header": {
            "alarms": "fix", "infos": "fix",
            "bkcolor": "#7f7f7fff", "fgcolor": "#000000",
            "fontFamily": "Sans-serif", "fontSize": 13,
            "items": [header_item("Labshock", 1), header_item("Kas SCADA", 2)],
            "itemsAnchor": "left", "loginInfo": "username",
            "dateTimeDisplay": "dd/MM/yyyy - hh:mm:aa",
        },
        "showdev": True, "zoom": "autoresize", "inputdialog": "false",
        "hidenavigation": "false", "theme": "", "loginonstart": False,
        "loginoverlaycolor": "none", "show_connection_error": True, "customStyles": "",
    }


def main():
    plots = load_plots()

    devices = []
    for i, plot in enumerate(plots):
        ip = plot.get("plc_ip", f"192.168.6.{10 + i}")
        devices.append(make_device(uid("d"), plot["plot"], ip))

    views = []

    home_id, home_name, home_items, home_svg = build_home_view(plots, devices)
    minidom.parseString(svg_frame(home_svg))
    views.append((home_id, home_name, home_items, home_svg))

    for plot, device in zip(plots, devices):
        vid, name, items, svg = build_plot_view(plot, device)
        minidom.parseString(svg_frame(svg))
        views.append((vid, name, items, svg))

    os.makedirs(OUT_DIR, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS reports (name TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS scripts (name TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS notifications (name TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS alarms (name TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS texts (name TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS devicesSecurity (name TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS devices (name TEXT PRIMARY KEY, value TEXT, connection TEXT, cntid TEXT, cntpwd TEXT);
        CREATE TABLE IF NOT EXISTS views (name TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS general (name TEXT PRIMARY KEY, value TEXT);
        DELETE FROM devices;
        DELETE FROM views;
        DELETE FROM general;
        """
    )

    server_device = {
        "id": "0",
        "name": "SCADA",
        "type": "FuxaServer",
        "property": {},
        "enabled": True,
        "tags": {},
        "polling": POLLING,
    }
    cur.execute("INSERT INTO devices (name, value) VALUES (?, ?)", ("0", json.dumps(server_device)))
    for device in devices:
        cur.execute("INSERT INTO devices (name, value) VALUES (?, ?)", (device["id"], json.dumps(device)))
    for vid, name, items, svg in views:
        cur.execute(
            "INSERT INTO views (name, value) VALUES (?, ?)",
            (vid, json.dumps(make_view(vid, name, items, svg))),
        )

    layout = build_layout(home_id)
    cur.execute("INSERT INTO general (name, value) VALUES ('layout', ?)", (json.dumps(layout),))
    cur.execute("INSERT INTO general (name, value) VALUES ('ulayout', ?)", (json.dumps(layout),))
    cur.execute("INSERT INTO general (name, value) VALUES ('charts', '[]')")
    cur.execute("INSERT INTO general (name, value) VALUES ('version', '\"1.00\"')")
    db.commit()
    db.close()

    with open(os.path.join(OUT_DIR, "mysettings.json"), "w") as f:
        json.dump({
            "language": "en",
            "uiPort": 1881,
            "secureEnabled": False,
            "tokenExpiresIn": "",
            "broadcastAll": False,
            "smtp": {"host": "", "port": 587, "mailsender": "", "username": ""},
            "daqstore": {"type": "SQlite", "credentials": {}, "retention": "year1"},
            "alarms": {"retention": "year1"},
            "logFull": False,
            "syslogHost": "192.168.6.40",
            "syslogPort": 514,
        }, f, indent=4)

    print(f"SCADA project generated: {DB_PATH}")
    print(f"views: {1 + len(plots)} | devices: {1 + len(plots)}")


if __name__ == "__main__":
    main()
