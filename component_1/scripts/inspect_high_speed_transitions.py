
import csv
import gzip
import math
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
GPS_FILE = ROOT / "data" / "tapas_gps_600.0s.csv.gz"
OUTPUT_FILE = ROOT / "data" / "high_speed_transitions.csv"

THRESHOLD = 40.0  # m/s = 144 km/h
EARTH_RADIUS = 6371000


def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1 = math.radians(lat1), math.radians(lon1)
    lat2, lon2 = math.radians(lat2), math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    h = min(1.0, max(0.0, h))
    return 2 * EARTH_RADIUS * math.asin(math.sqrt(h))


devices = defaultdict(list)

print("Reading GPS data...")

with gzip.open(GPS_FILE, "rt", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)

    for row in reader:
        devices[row["device_id"]].append((
            datetime.fromisoformat(row["timestamp"]),
            float(row["latitude"]),
            float(row["longitude"])
        ))

print("Checking vehicle transitions...")

high_speed = []

for device, fixes in devices.items():
    fixes.sort(key=lambda x: x[0])

    for a, b in zip(fixes, fixes[1:]):
        dt = (b[0] - a[0]).total_seconds()

        if dt <= 0:
            continue

        distance = haversine(a[1], a[2], b[1], b[2])
        speed = distance / dt

        if speed > THRESHOLD:
            high_speed.append({
                "device_id": device,
                "start_timestamp": a[0].isoformat(),
                "end_timestamp": b[0].isoformat(),
                "time_difference_s": round(dt, 3),
                "distance_m": round(distance, 2),
                "speed_mps": round(speed, 2),
                "speed_kmh": round(speed * 3.6, 2),
                "start_latitude": a[1],
                "start_longitude": a[2],
                "end_latitude": b[1],
                "end_longitude": b[2],
            })

high_speed.sort(key=lambda x: x["speed_mps"], reverse=True)

fields = [
    "device_id",
    "start_timestamp",
    "end_timestamp",
    "time_difference_s",
    "distance_m",
    "speed_mps",
    "speed_kmh",
    "start_latitude",
    "start_longitude",
    "end_latitude",
    "end_longitude",
]

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(high_speed)

print("\n========== HIGH SPEED INSPECTION ==========")
print("Vehicles inspected:", len(devices))
print("Transitions above 40 m/s:", len(high_speed))
print("Threshold:", THRESHOLD, "m/s")
print("Output:", OUTPUT_FILE)

print("\nTOP 20 HIGHEST SPEED TRANSITIONS:")

for i, item in enumerate(high_speed[:20], 1):
    print(
        f"{i}. Vehicle: {item['device_id']} | "
        f"Speed: {item['speed_kmh']} km/h | "
        f"Distance: {item['distance_m']} m | "
        f"Time: {item['time_difference_s']} s | "
        f"Timestamp: {item['start_timestamp']}"
    )

if high_speed:
    print("\nMaximum speed:", high_speed[0]["speed_kmh"], "km/h")
    print(
        "Minimum flagged speed:",
        high_speed[-1]["speed_kmh"],
        "km/h"
    )

print("\nInspection complete.")
