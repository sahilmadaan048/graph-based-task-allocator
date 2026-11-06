
import csv
import sys
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter

import numpy as np
from pyproj import CRS, Transformer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sumo_scenario import load_sumo_network

DATASET = ROOT.parent / "datasets" / "TAPASCologne"
NETWORK = DATASET / "cologne.net.xml"

INPUT = ROOT / "data" / "high_speed_transitions.csv"
OUTPUT = ROOT / "data" / "high_speed_road_limit_check.csv"

MAP_MATCH_THRESHOLD_M = 50.0
SPEED_TOLERANCE_KMH = 2.0

# --------------------------------------------------
# 1. Load the actual SUMO network
# --------------------------------------------------

print("Loading SUMO network...")

net, edge_id_to_idx = load_sumo_network(NETWORK)

print("Network edges:", len(net.edges))
print("Network nodes:", len(net.nodes))

if not net.edges:
    raise RuntimeError("No road edges loaded.")

if not hasattr(net.edges[0], "shape"):
    raise RuntimeError(
        "Road edges have no shape geometry. "
        "Check the Edge definition in road_network.py."
    )

# Recover original SUMO edge IDs.
sumo_id_by_idx = {
    idx: sumo_id
    for sumo_id, idx in edge_id_to_idx.items()
}

# --------------------------------------------------
# 2. Recover the exact SUMO coordinate transformation
# --------------------------------------------------

print("Preparing coordinate transformation...")

root = ET.parse(NETWORK).getroot()
location = root.find("location")

if location is None:
    raise RuntimeError("SUMO network location metadata missing.")

proj = location.get("projParameter")

if not proj or proj == "!":
    raise RuntimeError("Invalid SUMO projection.")

offset_x, offset_y = map(
    float,
    location.get("netOffset", "0,0").split(",")
)

coords = []

for node in root.findall("junction"):
    if node.get("id", "").startswith(":"):
        continue

    try:
        coords.append((
            float(node.get("x")),
            float(node.get("y"))
        ))
    except (TypeError, ValueError):
        continue

if not coords:
    raise RuntimeError("No usable SUMO junction coordinates.")

cx = sum(x for x, y in coords) / len(coords)
cy = sum(y for x, y in coords) / len(coords)

transformer = Transformer.from_crs(
    CRS.from_epsg(4326),
    CRS.from_user_input(proj),
    always_xy=True
)


def gps_to_local(lat, lon):
    px, py = transformer.transform(lon, lat)

    # Invert the SUMO netOffset and network centering.
    return (
        px + offset_x - cx,
        py + offset_y - cy
    )


# --------------------------------------------------
# 3. Build road geometry segments
# --------------------------------------------------

print("Building road geometry index...")

segments = []

for edge in net.edges:

    shape = edge.shape

    if len(shape) < 2:
        shape = (
            net.nodes[edge.u],
            net.nodes[edge.v]
        )

    for p1, p2 in zip(shape, shape[1:]):

        x1, y1 = p1
        x2, y2 = p2

        dx = x2 - x1
        dy = y2 - y1

        length_sq = dx * dx + dy * dy

        if length_sq < 1e-8:
            continue

        segments.append((
            x1, y1, dx, dy,
            length_sq,
            edge.eid
        ))

if not segments:
    raise RuntimeError("No usable road geometry segments.")

segments = np.asarray(segments, dtype=float)

sx = segments[:, 0]
sy = segments[:, 1]
sdx = segments[:, 2]
sdy = segments[:, 3]
slen_sq = segments[:, 4]
segment_edges = segments[:, 5].astype(int)

edge_by_idx = {
    edge.eid: edge
    for edge in net.edges
}

print("Road geometry segments:", len(segments))

# --------------------------------------------------
# 4. Find the nearest actual road segment
# --------------------------------------------------

def nearest_edge(x, y):

    t = (
        (x - sx) * sdx +
        (y - sy) * sdy
    ) / slen_sq

    t = np.clip(t, 0.0, 1.0)

    nearest_x = sx + t * sdx
    nearest_y = sy + t * sdy

    distances_sq = (
        (x - nearest_x) ** 2 +
        (y - nearest_y) ** 2
    )

    i = int(np.argmin(distances_sq))

    edge_idx = int(segment_edges[i])
    edge = edge_by_idx[edge_idx]

    return {
        "edge_idx": edge_idx,
        "sumo_edge_id": sumo_id_by_idx.get(
            edge_idx, str(edge_idx)
        ),
        "speed_limit_kmh": edge.speed_limit * 3.6,
        "distance_m": math.sqrt(distances_sq[i])
    }


# --------------------------------------------------
# 5. Inspect all suspicious transitions
# --------------------------------------------------

print("\nReading high-speed transitions...")

results = []

with open(INPUT, newline="", encoding="utf-8") as f:

    reader = csv.DictReader(f)

    for row in reader:

        lat1 = float(row["start_latitude"])
        lon1 = float(row["start_longitude"])

        lat2 = float(row["end_latitude"])
        lon2 = float(row["end_longitude"])

        observed = float(row["speed_kmh"])

        x1, y1 = gps_to_local(lat1, lon1)
        x2, y2 = gps_to_local(lat2, lon2)

        midpoint = (
            (x1 + x2) / 2,
            (y1 + y2) / 2
        )

        start = nearest_edge(x1, y1)
        middle = nearest_edge(*midpoint)
        end = nearest_edge(x2, y2)

        matches = [start, middle, end]

        limits = [
            m["speed_limit_kmh"]
            for m in matches
        ]

        max_distance = max(
            m["distance_m"]
            for m in matches
        )

        max_limit = max(limits)
        min_limit = min(limits)

        if max_distance > MAP_MATCH_THRESHOLD_M:
            status = "POOR_MAP_MATCH"

        elif observed > max_limit + SPEED_TOLERANCE_KMH:
            status = "ABOVE_ALL_MATCHED_LIMITS"

        elif observed <= min_limit + SPEED_TOLERANCE_KMH:
            status = "WITHIN_ALL_MATCHED_LIMITS"

        else:
            status = "AMBIGUOUS_NEARBY_LIMITS"

        results.append({
            "device_id": row["device_id"],
            "timestamp": row["start_timestamp"],
            "observed_speed_kmh": round(observed, 2),

            "start_edge": start["sumo_edge_id"],
            "start_limit_kmh": round(
                start["speed_limit_kmh"], 2
            ),
            "start_distance_m": round(
                start["distance_m"], 2
            ),

            "mid_edge": middle["sumo_edge_id"],
            "mid_limit_kmh": round(
                middle["speed_limit_kmh"], 2
            ),
            "mid_distance_m": round(
                middle["distance_m"], 2
            ),

            "end_edge": end["sumo_edge_id"],
            "end_limit_kmh": round(
                end["speed_limit_kmh"], 2
            ),
            "end_distance_m": round(
                end["distance_m"], 2
            ),

            "maximum_matched_limit_kmh": round(
                max_limit, 2
            ),

            "status": status
        })

# --------------------------------------------------
# 6. Save complete results
# --------------------------------------------------

fields = list(results[0].keys()) if results else []

with open(OUTPUT, "w", newline="", encoding="utf-8") as f:

    if fields:
        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        writer.writeheader()
        writer.writerows(results)

# --------------------------------------------------
# 7. Final report
# --------------------------------------------------

print("\n========== ROAD SPEED LIMIT AUDIT ==========")

print("Transitions checked:", len(results))

counts = Counter(
    r["status"] for r in results
)

for status, count in sorted(counts.items()):
    print(f"{status}: {count}")

print("\nTOP 20 TRANSITIONS:")

for i, r in enumerate(
    sorted(
        results,
        key=lambda x: x["observed_speed_kmh"],
        reverse=True
    )[:20],
    1
):

    print(
        f"{i}. Observed: "
        f"{r['observed_speed_kmh']} km/h | "

        f"Start limit: {r['start_limit_kmh']} | "

        f"Mid limit: {r['mid_limit_kmh']} | "

        f"End limit: {r['end_limit_kmh']} | "

        f"Road distance: "
        f"{max(r['start_distance_m'], r['mid_distance_m'], r['end_distance_m'])} m | "

        f"Status: {r['status']}"
    )

print("\nOutput:", OUTPUT)
print("========== AUDIT COMPLETE ==========")
