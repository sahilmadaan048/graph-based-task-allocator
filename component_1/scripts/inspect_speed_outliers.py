
import csv
import gzip
import math
from collections import defaultdict

path = "data/tapas_smoke_60s_v2.csv.gz"
devices = defaultdict(list)

with gzip.open(path, "rt", newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        devices[row["device_id"]].append((
            row["timestamp"],
            float(row["latitude"]),
            float(row["longitude"])
        ))

results = []

for device, fixes in devices.items():
    fixes.sort()

    for a, b in zip(fixes, fixes[1:]):
        from datetime import datetime

        dt = (
            datetime.fromisoformat(b[0])
            - datetime.fromisoformat(a[0])
        ).total_seconds()

        if dt <= 0:
            continue

        lat1, lon1 = map(math.radians, a[1:])
        lat2, lon2 = map(math.radians, b[1:])

        h = (
            math.sin((lat2-lat1)/2)**2
            + math.cos(lat1)*math.cos(lat2)
            * math.sin((lon2-lon1)/2)**2
        )

        distance = 2 * 6371000 * math.asin(math.sqrt(h))
        speed = distance / dt

        results.append((speed, device, a, b))

results.sort(reverse=True)

print("TOP 10 HIGHEST GPS-DERIVED SPEED TRANSITIONS")

for speed, device, a, b in results[:10]:
    print("\nDevice:", device)
    print("From:", a)
    print("To:  ", b)
    print("Speed:", round(speed, 2), "m/s")
    print("Speed:", round(speed * 3.6, 2), "km/h")
