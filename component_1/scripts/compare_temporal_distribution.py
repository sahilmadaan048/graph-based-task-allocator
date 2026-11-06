
import gzip
import csv
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
import math

TRIPS = "../datasets/TAPASCologne/cologne6to8.trips.xml"
GPS = "data/tapas_gps_600.0s.csv.gz"

START_SECONDS = 21600  # 06:00
DURATION = 600
DENSITY = 1.3
MINUTES = 10

# --------------------------------------------------
# 1. Count TAPAS departures per minute
# --------------------------------------------------

tapas = Counter()

for _, elem in ET.iterparse(TRIPS, events=("end",)):

    if elem.tag not in ("trip", "vehicle"):
        elem.clear()
        continue

    depart = elem.get("depart")

    if depart is not None:
        depart = float(depart)
        offset = int(depart - START_SECONDS)

        if 0 <= offset < DURATION:
            minute = offset // 60
            tapas[minute] += 1

    elem.clear()


# --------------------------------------------------
# 2. Get first GPS timestamp for each device
# --------------------------------------------------

first_gps = {}

with gzip.open(GPS, "rt") as f:
    reader = csv.DictReader(f)

    for row in reader:
        device = row["device_id"]
        timestamp = datetime.fromisoformat(row["timestamp"])

        if device not in first_gps or timestamp < first_gps[device]:
            first_gps[device] = timestamp


# --------------------------------------------------
# 3. Count first GPS observations per minute
# --------------------------------------------------

simulator = Counter()

for timestamp in first_gps.values():
    offset = int(
        (timestamp - datetime.fromisoformat(
            "2026-01-01T06:00:00"
        )).total_seconds()
    )

    if 0 <= offset < DURATION:
        simulator[offset // 60] += 1


# --------------------------------------------------
# 4. Compare distributions
# --------------------------------------------------

actual = []
expected = []
observed = []

print("\n===== TEMPORAL DISTRIBUTION COMPARISON =====")
print("Time       TAPAS     Expected     Simulator")

for minute in range(MINUTES):

    tapas_count = tapas[minute]
    expected_count = round(tapas_count * DENSITY)
    simulator_count = simulator[minute]

    actual.append(tapas_count)
    expected.append(expected_count)
    observed.append(simulator_count)

    start_minute = 6 * 60 + minute

    print(
        f"{start_minute // 60:02d}:{start_minute % 60:02d}"
        f"       {tapas_count:6d}"
        f"       {expected_count:6d}"
        f"       {simulator_count:6d}"
    )


# --------------------------------------------------
# 5. Overall comparison
# --------------------------------------------------

total_tapas = sum(actual)
total_expected = sum(expected)
total_simulator = sum(observed)

print("\n===== TOTALS =====")
print("TAPAS departures:", total_tapas)
print("Expected scaled departures:", total_expected)
print("Simulator first GPS observations:", total_simulator)

if total_expected:
    print(
        "Overall count agreement:",
        round(100 * total_simulator / total_expected, 2),
        "%"
    )


def pearson(a, b):
    ma = sum(a) / len(a)
    mb = sum(b) / len(b)

    numerator = sum(
        (x - ma) * (y - mb)
        for x, y in zip(a, b)
    )

    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))

    return numerator / (da * db) if da and db else float("nan")


print(
    "Minute-level Pearson correlation:",
    round(pearson(expected, observed), 4)
)

print("\n===== COMPARISON COMPLETE =====")
