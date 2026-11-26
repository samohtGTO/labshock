#!/usr/bin/env python3
import sqlite3
import json

conn = sqlite3.connect('/tmp/project.fuxap.db')
cur = conn.cursor()

# Get all devices
cur.execute('SELECT name, value FROM devices')
for name, value in cur.fetchall():
    dev = json.loads(value)
    print(f"\n{dev.get('name', name)}:")
    print(f"  ID: {dev.get('id')}")
    print(f"  Type: {dev.get('type')}")
    print(f"  Address: {dev.get('property', {}).get('address')}")
    print(f"  Enabled: {dev.get('enabled')}")
