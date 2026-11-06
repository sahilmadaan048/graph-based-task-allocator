
import gzip
import csv
import math
from collections import Counter, defaultdict

path = "data/tapas_gps_600.0s.csv.gz"

records = 0
lat_min = 90
lat_max = -90
lon_min = 180
lon_max = -180

cells = defaultdict(set)
devices = set()

# Approximately 1 km grid cells
for source in gzip.open(path, "rt"):
    pass

with gzip.open(path, "rt") as f:
    reader = csv.DictReader(f)

    for row in reader:
        lat = float(row["latitude"])
        lon = float(row["longitude"])

        records += 1
        devices.add(row["device_id"])

        lat_min = min(lat_min, lat)
        lat_max = max(lat_max, lat)
        lon_min = min(lon_min, lon)
        lon_max = max(lon_max, lon)

        x = lon * 111.32 * math.cos(math.radians(lat))
        y = lat * 111.32

        cell = (int(x), int(y))
        cells[cell].add(row["device_id"])

print("\n===== SPATIAL COVERAGE AUDIT =====")
print("GPS records:", records)
print("Unique vehicles:", len(devices))
print("Occupied 1km grid cells:", len(cells))

print("\nGeographic bounds:")
print("Latitude:", lat_min, "to", lat_max)
print("Longitude:", lon_min, "to", lon_max)

print("\nTop 10 cells by unique vehicles:")
for cell, devices in sorted(
    cells.items(),
    key=lambda item: len(item[1]),
    reverse=True
)[:10]:
    print(cell, "Unique vehicles:", len(devices))

print("\n===== AUDIT COMPLETE =====")
