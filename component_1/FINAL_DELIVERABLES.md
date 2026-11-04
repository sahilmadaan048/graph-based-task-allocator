# GNN Project — Component 1 Final Deliverables

This folder is the consolidated handover package for Component 1: a replaceable, GPS-only vehicle mobility observation source with a live map dashboard.

## Included

- `src/`: simulator, road-network utilities, GPS observation contract, and TAPASCologne/SUMO scenario adapter.
- `run_simulation.py`: batch simulation and GPS CSV export.
- `run_dashboard.py` and `templates/index.html`: browser-based live map with moving device dots.
- `config/sim_config.json`: simulation configuration and random seed.
- `tests/`: automated tests for the simulator, GPS contract, and SUMO scenario parser.
- `data/vehicle_positions_gps_only.csv.gz`: generated GPS-only trace.
- `data/gps_only_run_summary.json`: provenance and aggregate run diagnostics.
- `COMPONENT_1_RESEARCH.md`: research background, citations, adaptations from the literature, rationale, and limitations.
- `README.md`: installation, execution, data contract, and dashboard instructions.

## Critical research/provenance qualification

The included 40-minute trace was generated using the **synthetic radial/ring fallback network**, not the TAPASCologne dataset. It contains 1,437,527 GPS rows from 1,302 pseudonymous devices. This revision changes the GPS error to a temporally correlated model, sets the main density multiplier to 1.3, and reports both driving and resting devices at a common one-second cadence. Batch export writes incrementally to compressed CSV rather than retaining the entire trace in memory. The TAPASCologne/SUMO network and route-demand adapter is included, but the actual Cologne network and route files were not present in the supplied project files. Therefore this package does not claim a completed Cologne-data-driven simulation or validation against Cologne observations.

To run with TAPASCologne, obtain the official scenario files and pass both the SUMO `.net.xml` and `.rou.xml` files to `run_simulation.py`. The scenario adapter uses the real network and demand as offline inputs; the simulator generates new GPS observations rather than replaying original trajectories.

## GPS-only public interface

Every downstream observation contains exactly:

```text
device_id,timestamp,latitude,longitude
```

Speed, acceleration, heading, distance, route, road-edge ID, parking state, and simulator ground truth are not part of the downstream observation contract. Those features must be derived from consecutive GPS observations where needed.

## Quick start

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python run_dashboard.py --host 127.0.0.1 --port 8050
```

For the TAPASCologne map, pass `--net` and `--routes` at server startup. The dashboard accepts only loopback bind addresses and never accepts filesystem paths from browser query parameters.

Open `http://127.0.0.1:8050`. The dashboard's OpenStreetMap basemap requires internet access; the simulator and GPS stream run locally.

For a batch run:

```bash
python run_simulation.py --duration 3600 \
  --output data/vehicle_positions_gps_only.csv.gz \
  --summary data/gps_only_run_summary.json
```

For a TAPASCologne-backed run, add:

```bash
  --net /path/to/Cologne.net.xml \
  --routes /path/to/Cologne.rou.xml
```

## Test result at packaging

The project tests were run with `python -m pytest -q`: **12 passed**. The dashboard health/SSE endpoints were smoke-tested, and binding to `0.0.0.0` was rejected as intended.
