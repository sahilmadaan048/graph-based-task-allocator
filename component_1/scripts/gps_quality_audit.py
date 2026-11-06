
import csv
import gzip
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

path = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    ROOT / "data" / "tapas_gps_600.0s.csv.gz"
)

if not path.is_absolute():
    path = ROOT / path

devices = defaultdict(list)
seen = set()
duplicates = 0
invalid = 0
records = 0

with gzip.open(path, "rt", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)

    expected = {
        "device_id", "timestamp", "latitude", "longitude"
    }

    print("Input file:", path)
    print("Schema:", reader.fieldnames)
    print("Schema correct:", set(reader.fieldnames or []) == expected)

    for row in reader:
        records += 1

        try:
            device = row["device_id"]
            timestamp = datetime.fromisoformat(row["timestamp"])
            lat = float(row["latitude"])
            lon = float(row["longitude"])

            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                invalid += 1
                continue

            key = (device, timestamp)

            if key in seen:
                duplicates += 1

            seen.add(key)
            devices[device].append((timestamp, lat, lon))

        except (ValueError, TypeError, KeyError):
            invalid += 1

speeds = []
gaps = 0

for device, fixes in devices.items():
    fixes.sort(key=lambda x: x[0])

    for a, b in zip(fixes, fixes[1:]):
        dt = (b[0] - a[0]).total_seconds()

        if dt <= 0:
            continue

        if dt > 1.01:
            gaps += 1

        lat1, lon1 = math.radians(a[1]), math.radians(a[2])
        lat2, lon2 = math.radians(b[1]), math.radians(b[2])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        h = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2)
            * math.sin(dlon / 2) ** 2
        )

        h = min(1.0, max(0.0, h))
        distance = 2 * 6371000 * math.asin(math.sqrt(h))
        speeds.append(distance / dt)

speeds.sort()


def percentile(values, p):
    if not values:
        return 0
    return values[min(int((len(values) - 1) * p), len(values) - 1)]


print("\n========== GPS QUALITY AUDIT ==========")
print("Total records:", records)
print("Unique devices:", len(devices))
print("Invalid records:", invalid)
print("Duplicate device/timestamp pairs:", duplicates)
print("Intervals greater than 1.01 seconds:", gaps)
print("Derived speed samples:", len(speeds))

if speeds:
    print("Median speed (m/s):", round(percentile(speeds, 0.50), 2))
    print("95th percentile (m/s):", round(percentile(speeds, 0.95), 2))
    print("Maximum speed (m/s):", round(speeds[-1], 2))
    print("Transitions above 55 m/s:", sum(s > 55 for s in speeds))
    print("Transitions above 40 m/s:", sum(s > 40 for s in speeds))
