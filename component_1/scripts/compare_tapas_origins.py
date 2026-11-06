
import gzip
import csv
import math
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
import sumolib

NET = "../datasets/TAPASCologne/cologne.net.xml"
TRIPS = "../datasets/TAPASCologne/cologne6to8.trips.xml"
GPS = "data/tapas_gps_600.0s.csv.gz"

net = sumolib.net.readNet(NET)

def grid_cell(lat, lon):
    x = lon * 111.32 * math.cos(math.radians(lat))
    y = lat * 111.32
    return int(x), int(y)

# Read GPS observations and count unique vehicles per cell.
gps_cells = defaultdict(set)

with gzip.open(GPS, "rt") as f:
    for row in csv.DictReader(f):
        cell = grid_cell(
            float(row["latitude"]),
            float(row["longitude"])
        )
        gps_cells[cell].add(row["device_id"])

# Count TAPAS trip origins during the first 10 minutes (06:00–06:10).
origin_cells = Counter()
edge_cache = {}
accepted = 0
missing_edges = 0

for _, elem in ET.iterparse(TRIPS, events=("end",)):
    if elem.tag not in ("trip", "vehicle"):
        elem.clear()
        continue

    depart = elem.get("depart")
    edge_id = elem.get("from")

    if depart is None or edge_id is None:
        elem.clear()
        continue

    if not (21600 <= float(depart) < 22200):
        elem.clear()
        continue

    try:
        if edge_id not in edge_cache:
            edge = net.getEdge(edge_id)
            shape = edge.getShape()

            if not shape:
                raise ValueError("No edge geometry")

            x, y = shape[len(shape) // 2]
            lon, lat = net.convertXY2LonLat(x, y)
            edge_cache[edge_id] = grid_cell(lat, lon)

        origin_cells[edge_cache[edge_id]] += 1
        accepted += 1

    except (KeyError, ValueError):
        missing_edges += 1

    elem.clear()

print("\n===== TAPAS ORIGIN vs GPS DISTRIBUTION =====")
print("TAPAS trips in first 10 minutes:", accepted)
print("Origins without usable geometry:", missing_edges)
print("GPS occupied cells:", len(gps_cells))
print("TAPAS origin cells:", len(origin_cells))

print("\nTop 10 TAPAS origin cells:")
for cell, count in origin_cells.most_common(10):
    print(cell, "Trip origins:", count)

print("\nTop 10 GPS cells by unique vehicles:")
for cell, devices in sorted(
    gps_cells.items(),
    key=lambda item: len(item[1]),
    reverse=True
)[:10]:
    print(cell, "Unique vehicles:", len(devices))

overlap = set(origin_cells) & set(gps_cells)
print("\nCells appearing in both distributions:", len(overlap))
print("TAPAS origin cells with GPS coverage:",
      round(100 * len(overlap) / max(1, len(origin_cells)), 2), "%")

print("\n===== COMPARISON COMPLETE =====")
