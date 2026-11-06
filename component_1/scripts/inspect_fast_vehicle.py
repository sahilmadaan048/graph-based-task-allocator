
import gzip
import csv
from collections import defaultdict
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2

path = "data/tapas_gps_600.0s.csv.gz"
target = "dev_53e6c274252d"

rows = []
with gzip.open(path, "rt") as f:
    for row in csv.DictReader(f):
        if row["device_id"] == target:
            rows.append(row)

rows.sort(key=lambda r: r["timestamp"])

print("Device:", target)
print("Timestamp          Latitude      Longitude      Speed")

for a, b in zip(rows, rows[1:]):
    t1 = datetime.fromisoformat(a["timestamp"])
    t2 = datetime.fromisoformat(b["timestamp"])
    dt = (t2 - t1).total_seconds()

    if dt <= 0:
        continue

    lat1, lon1 = radians(float(a["latitude"])), radians(float(a["longitude"]))
    lat2, lon2 = radians(float(b["latitude"])), radians(float(b["longitude"]))

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    distance = 6371000 * 2 * atan2(sqrt(h), sqrt(1 - h))
    speed = distance / dt

    if speed > 40:
        print(
            b["timestamp"],
            b["latitude"],
            b["longitude"],
            round(speed, 2), "m/s",
            round(speed * 3.6, 2), "km/h"
        )
