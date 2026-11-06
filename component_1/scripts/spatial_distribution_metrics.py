
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

# Count unique simulated vehicles per cell.
gps_cells = defaultdict(set)

with gzip.open(GPS, "rt") as f:
    for row in csv.DictReader(f):
        cell = grid_cell(
            float(row["latitude"]),
            float(row["longitude"])
        )
        gps_cells[cell].add(row["device_id"])

# Count TAPAS origins during 06:00–06:10.
origin_cells = Counter()
edge_cache = {}

for _, elem in ET.iterparse(TRIPS, events=("end",)):
    if elem.tag not in ("trip", "vehicle"):
        elem.clear()
        continue

    depart = elem.get("depart")
    edge_id = elem.get("from")

    if depart is None or edge_id is None:
        elem.clear()
        continue

    if 21600 <= float(depart) < 22200:
        try:
            if edge_id not in edge_cache:
                edge = net.getEdge(edge_id)
                shape = edge.getShape()
                x, y = shape[len(shape) // 2]
                lon, lat = net.convertXY2LonLat(x, y)
                edge_cache[edge_id] = grid_cell(lat, lon)

            origin_cells[edge_cache[edge_id]] += 1
        except (KeyError, ValueError, IndexError):
            pass

    elem.clear()

# Compare counts across every cell in the union.
all_cells = sorted(set(origin_cells) | set(gps_cells))

x = [origin_cells[c] for c in all_cells]
y = [len(gps_cells[c]) for c in all_cells]

def pearson(a, b):
    ma = sum(a) / len(a)
    mb = sum(b) / len(b)
    numerator = sum((u-ma)*(v-mb) for u, v in zip(a,b))
    da = math.sqrt(sum((u-ma)**2 for u in a))
    db = math.sqrt(sum((v-mb)**2 for v in b))
    return numerator / (da*db) if da and db else float("nan")

def ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    result = [0.0] * len(values)
    i = 0

    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j+1]] == values[order[i]]:
            j += 1

        average_rank = (i + j) / 2 + 1

        for k in range(i, j+1):
            result[order[k]] = average_rank

        i = j + 1

    return result

print("\n===== SPATIAL DISTRIBUTION METRICS =====")
print("Grid cells compared:", len(all_cells))
print("Pearson correlation:", round(pearson(x, y), 4))
print("Spearman correlation:", round(pearson(ranks(x), ranks(y)), 4))

top_origin = {
    cell for cell, count in origin_cells.most_common(20)
}
top_gps = set(sorted(
    gps_cells,
    key=lambda c: len(gps_cells[c]),
    reverse=True
)[:20])

print("Top 20 cell overlap:", len(top_origin & top_gps), "/ 20")

print("\n===== COMPLETE =====")
