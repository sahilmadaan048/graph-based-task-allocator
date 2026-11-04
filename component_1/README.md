# Component 1 — GPS Observation Source (Rule-Based Vehicle Simulator)

## Purpose and boundary

Component 1 is a **replaceable source of GPS observations**, not a source of privileged simulation truth. Its downstream interface is deliberately identical to the minimal data that a vehicle GPS unit or a mobile phone can provide:

```text
device_id,timestamp,latitude,longitude
```

No vehicle speed, acceleration, heading, route, road-edge ID, destination, parking/garage label, simulator state, local x/y coordinate, or traffic-light state is sent to the next component. The downstream movement-feature component must derive speed, direction, distance and temporal changes from consecutive GPS fixes. This means a real GPS feed can replace the simulator without changing downstream components, provided it is mapped to this schema.

`device_id` is a pseudonymous source identifier. In a real deployment it should be a rotating or appropriately protected identifier, not a phone number, registration plate or account identity.

## Dataset / research input

TAPASCologne is used as an **offline scenario input** for road topology and travel-demand patterns, not as a runtime sensor and not as the GNN input schema. The adapter reads SUMO `.net.xml` and `.rou.xml` files. The rule-based engine generates new paths and GPS observations; it does not replay the original trajectories. See `COMPONENT_1_RESEARCH.md` for research lineage, changes and limitations.

Download the scenario from [the official SUMO scenario folder](https://sourceforge.net/projects/sumo/files/traffic_data/scenarios/TAPASCologne/), extract the network and 24-hour route files, then run:

```bash
pip install -r requirements.txt
python run_simulation.py \
  --config config/sim_config.json \
  --net /path/to/Cologne.net.xml \
  --routes /path/to/Cologne.rou.xml \
  --duration 3600
```

Without `--net` and `--routes`, the simulator uses the synthetic radial/ring fallback for demonstrations and software tests. Such a run must not be described as a TAPASCologne-driven run.

## Streaming contract

`VehicleSimulation.stream(duration_s)` yields `(simulation_clock_seconds, list[GPSObservation])`. Each observation has exactly four keys: `device_id`, `timestamp`, `latitude`, and `longitude`. The clock value is orchestration metadata; it is not part of an individual GPS observation. `src/gps_contract.py` defines and validates the contract. Implement any real-device adapter against `GPSObservationSource` and `validate_observation`.

The simulator may internally use road edges, speed, route, vehicle state and local metric coordinates to advance motion. Those internals are intentionally hidden at the public boundary. Run summaries contain experiment diagnostics, but they are not passed as observations to the GNN.

## Output

- `data/vehicle_positions_gps_only.csv.gz`: GPS-only observations with the four columns above.
- `data/gps_only_run_summary.json`: experiment provenance and aggregate simulator diagnostics; do not feed this file to the GNN as per-device observations.

## Reproducibility

Set `seed` in `config/sim_config.json`. Identical configuration, source data and seed should reproduce the same GPS stream. Coordinates include configurable synthetic GPS noise. They are simulated measurements, not real-world measurements or proof of realism.

## Tests

```bash
python -m pytest -q
```

Tests cover same-seed repeatability, correlated stationary GPS error, equal reporting cadence, opaque IDs, non-overlapping rest anchors and same-edge vehicles, the exact public GPS schema, rejection of simulator-only fields, and SUMO projection/shape/turn parsing.

## Live map dashboard

Start the interactive map from the project root:

```bash
pip install -r requirements.txt
python run_dashboard.py --host 127.0.0.1 --port 8050
```

For the TAPASCologne map, configure the files at server startup:

```bash
python run_dashboard.py --host 127.0.0.1 --port 8050 --net /path/to/Cologne.net.xml --routes /path/to/Cologne.rou.xml
```

The dashboard refuses non-loopback bind addresses. Do not expose this development server to a public network.

Open `http://127.0.0.1:8050` in a browser. The map uses OpenStreetMap tiles and displays one moving dot per pseudonymous GPS device. Controls support start, stop, pause/resume of the *view*, and playback speed (0.5x–10x). The default view is centred on the synthetic Bologna-area fallback network. For TAPASCologne, pass `--net` and `--routes` as startup arguments; dataset file paths are never accepted from browser URLs. The dashboard binds only to loopback addresses.

The dashboard stream is Server-Sent Events (SSE). Every observation sent to the browser contains only `device_id`, `timestamp`, `latitude`, and `longitude`. It does not send internal simulator speed, route, road-edge IDs, parking/garage state, or ground-truth positions. The displayed device/fix counters are derived from GPS observations; no hidden vehicle state is exposed. Browser map tiles require an internet connection; the GPS stream itself is local.

The displayed dots are simulated observations, not real live vehicles. OpenStreetMap supplies the basemap only.
