import argparse
import csv
import gzip
import json
import time
from pathlib import Path
from datetime import datetime
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sumo_scenario import load_tapas_scenario
from src.vehicle_sim import VehicleSimulation




def main():
    parser = argparse.ArgumentParser(
        description="Run custom vehicle simulation using TAPASCologne demand."
    )
    parser.add_argument("--duration", type=float, default=60)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--density", type=float, default=1.3)
    parser.add_argument("--dataset-scale", type=float, default=1.0)
    args = parser.parse_args()

    # Load the base simulation configuration.
    with open(ROOT / "config" / "sim_config.json", encoding="utf-8") as f:
        cfg = json.load(f)

    cfg["seed"] = args.seed
    cfg["sim"]["start_datetime"] = "2026-01-01T06:00:00"
    cfg["arrivals"]["density_multiplier"] = args.density
    cfg["arrivals"]["dataset_scale"] = args.dataset_scale

    # Actual TAPASCologne source files.
    dataset = ROOT.parent / "datasets" / "TAPASCologne"
    net_file = dataset / "cologne.net.xml"
    route_file = dataset / "cologne6to8.trips.xml"

    if not net_file.exists() or not route_file.exists():
        raise FileNotFoundError(
            f"TAPASCologne files not found in {dataset}"
        )

    print("Loading TAPASCologne network and trip demand...")

    net, demand = load_tapas_scenario(
        net_file=net_file,
        route_file=route_file,
    )

    print("Network edges:", len(net.edges))
    print("Accepted TAPAS trips:", demand["accepted_route_records"])
    print("Starting custom vehicle simulation...")

    sim = VehicleSimulation(cfg, net=net)

    output_dir = ROOT / "data"
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f"tapas_gps_{args.duration}s.csv.gz"
    summary_file = output_dir / f"tapas_run_summary_{args.duration}s.json"
    spawn_file = output_dir / f"tapas_spawn_events_{args.duration}s.json"

    columns = [
        "device_id",
        "timestamp",
        "latitude",
        "longitude",
    ]

    start = time.perf_counter()
    records = 0
    observed_devices = set()

    with gzip.open(
        output_file, "wt", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()

        for _, batch in sim.stream(args.duration):
            if batch:
                writer.writerows(batch)
                records += len(batch)
                observed_devices.update(
                    row["device_id"] for row in batch
                )

    elapsed = time.perf_counter() - start
    # Save actual first-entry timestamps for temporal validation.
    with open(spawn_file, "w", encoding="utf-8") as f:
        json.dump(sim.spawn_events, f, indent=2)

    summary = {
        "source": "TAPASCologne network and trip demand",
        "movement_model": "Custom rule-based vehicle simulator",
        "requested_duration_s": args.duration,
        "simulated_duration_s": sim.t,
        "wall_clock_s": round(elapsed, 3),
        "gps_records": records,
        "unique_devices_observed": len(observed_devices),
        "output_schema": columns,
        "downstream_payload_contains_only_gps_fields": True,
        "config_seed": args.seed,
        "density_multiplier": args.density,
        "dataset_scale": args.dataset_scale,
        "accepted_tapas_trips": demand["accepted_route_records"],
        "departure_counts_per_10min": demand[
            "departure_counts_per_10min"
        ],
        "final_counts": sim.counts(),
        "simulator_spawned_total": sim.n_spawned,
        "simulator_exited_total": sim.n_exited,
        "output_file": str(output_file.relative_to(ROOT)),
        "actual_first_entry_events": len(sim.spawn_events),
        "spawn_events_file": str(spawn_file.relative_to(ROOT)),
    }

    summary_file.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print("\n========== TAPAS SIMULATION COMPLETE ==========")
    print("GPS records:", records)
    print("Observed devices:", len(observed_devices))
    print("Vehicles spawned:", sim.n_spawned)
    print("Vehicles exited:", sim.n_exited)
    print("Simulated duration:", sim.t)
    print("Wall-clock time:", round(elapsed, 2), "seconds")
    print("GPS output:", output_file)
    print("Summary:", summary_file)
    print("Spawn events:", len(sim.spawn_events))
    print("Spawn log:", spawn_file)


if __name__ == "__main__":
    main()
