
import gzip
import csv
import math
import xml.etree.ElementTree as ET
from collections import Counter
import sumolib

NET = "../datasets/TAPASCologne/cologne.net.xml"
TRIPS = "../datasets/TAPASCologne/cologne6to8.trips.xml"
GPS = "data/tapas_gps_600.0s.csv.gz"


def grid_cell(lat, lon):
    x = lon * 111.32 * math.cos(math.radians(lat))
    y = lat * 111.32
    return int(x), int(y)


# --------------------------------------------------
# 1. Load first GPS observation per vehicle
# --------------------------------------------------

first_gps = {}

with gzip.open(GPS, "rt") as f:
    reader = csv.DictReader(f)

    for row in reader:
        device = row["device_id"]
        timestamp = row["timestamp"]

        if device not in first_gps or timestamp < first_gps[device][0]:
            first_gps[device] = (
                timestamp,
                grid_cell(
                    float(row["latitude"]),
                    float(row["longitude"])
                )
            )

gps_start_cells = Counter(
    cell for timestamp, cell in first_gps.values()
)


# --------------------------------------------------
# 2. Load TAPAS trip origins (06:00–06:10)
# --------------------------------------------------

net = sumolib.net.readNet(NET)

origin_cells = Counter()
edge_cache = {}
accepted = 0
missing = 0

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

                if not shape:
                    raise ValueError("Missing edge geometry")

                x, y = shape[len(shape) // 2]
                lon, lat = net.convertXY2LonLat(x, y)

                edge_cache[edge_id] = grid_cell(lat, lon)

            origin_cells[edge_cache[edge_id]] += 1
            accepted += 1

        except (KeyError, ValueError, IndexError):
            missing += 1

    elem.clear()


# --------------------------------------------------
# 3. Compare distributions
# --------------------------------------------------

all_cells = sorted(set(origin_cells) | set(gps_start_cells))

x = [origin_cells[c] for c in all_cells]
y = [gps_start_cells[c] for c in all_cells]


def pearson(a, b):
    ma = sum(a) / len(a)
    mb = sum(b) / len(b)

    numerator = sum(
        (u - ma) * (v - mb)
        for u, v in zip(a, b)
    )

    da = math.sqrt(sum((u - ma) ** 2 for u in a))
    db = math.sqrt(sum((v - mb) ** 2 for v in b))

    return numerator / (da * db) if da and db else float("nan")


def ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    result = [0.0] * len(values)

    i = 0
    while i < len(order):
        j = i

        while (
            j + 1 < len(order)
            and values[order[j + 1]] == values[order[i]]
        ):
            j += 1

        average_rank = (i + j) / 2 + 1

        for k in range(i, j + 1):
            result[order[k]] = average_rank

        i = j + 1

    return result


top_origins = {
    cell for cell, count in origin_cells.most_common(20)
}

top_gps = {
    cell for cell, count in gps_start_cells.most_common(20)
}

overlap = len(top_origins & top_gps)

common_cells = set(origin_cells) & set(gps_start_cells)


# --------------------------------------------------
# 4. Print results
# --------------------------------------------------

print("\n===== STARTING DISTRIBUTION COMPARISON =====")

print("TAPAS trips:", accepted)
print("Missing origin geometries:", missing)
print("Vehicles with first GPS observation:", len(first_gps))

print("\nOccupied cells:")
print("TAPAS origin cells:", len(origin_cells))
print("GPS starting cells:", len(gps_start_cells))
print("Common cells:", len(common_cells))

print("\nCorrelation:")
print("Pearson:", round(pearson(x, y), 4))
print("Spearman:", round(pearson(ranks(x), ranks(y)), 4))

print("\nTop-20 overlap:", overlap, "/ 20")

print("\nTop 10 TAPAS origin cells:")
for cell, count in origin_cells.most_common(10):
    print(cell, "Trips:", count)

print("\nTop 10 GPS starting cells:")
for cell, count in gps_start_cells.most_common(10):
    print(cell, "Vehicles:", count)

print("\n===== COMPARISON COMPLETE =====")
