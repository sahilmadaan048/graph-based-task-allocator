
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "data" / "tapas_run_summary_600.0s.json"

def main():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    spawn_file = ROOT / summary["spawn_events_file"]
    events = json.loads(spawn_file.read_text(encoding="utf-8"))

    duration = summary["simulated_duration_s"]
    density = summary["density_multiplier"]
    scale = summary["dataset_scale"]

    # Simulation starts at 06:00, which is TAPAS 10-minute slot 36.
    tapas_departures = summary["departure_counts_per_10min"][36]
    expected = round(tapas_departures * density * scale)

    actual = sum(
        1 for event in events
        if 0 <= event["simulation_time_s"] < duration
    )

    agreement = 100 * actual / expected if expected else 0

    print("\n===== ACTUAL SPAWN TEMPORAL AUDIT =====")
    print("Interval: 06:00–06:10")
    print("TAPAS departures:", tapas_departures)
    print("Density multiplier:", density)
    print("Dataset scale:", scale)
    print("Expected scaled entries:", expected)
    print("Actual successful first entries:", actual)
    print("Count agreement:", f"{agreement:.2f}%")
    print("=======================================\n")


if __name__ == "__main__":
    main()
