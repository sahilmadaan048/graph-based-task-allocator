# Component 1 — GPS-only mobility source: research basis, adaptations and limitations

**Project:** GNN-based vehicle mobility analysis  
**Component:** 1 — Replaceable GPS observation source  
**Implementation:** Rule-based vehicle simulator with optional TAPASCologne road-network and demand inputs.

## 1. Design principle: the simulator must be replaceable by reality

The simulator is a development-time substitute for a stream of GPS observations. It is **not** an additional source of information that a real vehicle or mobile phone would not expose. The public interface therefore contains only:

| Field | Meaning | Real-world availability |
|---|---|---|
| `device_id` | Pseudonymous identifier for a reporting device | Application/device identifier; must be privacy-protected |
| `timestamp` | Time at which the fix is reported | GPS/device clock |
| `latitude` | Geographic latitude in decimal degrees | GNSS/GPS fix |
| `longitude` | Geographic longitude in decimal degrees | GNSS/GPS fix |

Every observation has exactly these four fields. No speed, acceleration, direction/heading, distance, road ID, route, destination, vehicle type, parking label, garage label, simulator state, traffic-light state, local x/y coordinate, or simulator ground truth is emitted. Some phones/GNSS receivers can report speed, bearing and horizontal accuracy, but this project deliberately excludes them from the minimum common contract so downstream processing can derive movement features consistently from position and time alone.

The simulator internally requires speed, route and road-network state to move vehicles. Those are implementation internals and are never exposed through the observation stream. Aggregate run diagnostics are written separately to `run_summary.json`; they are experiment metadata, not input features for the GNN.

This boundary makes the simulator replaceable: a future phone/vehicle GPS adapter should implement `GPSObservationSource` and emit the same four-field schema. Component 2 and later components should not need to know whether a fix came from a simulator, a phone or an onboard receiver.

## 2. Dataset clarification and role

The selected reference is **TAPASCologne / KölnTrace**, not a raw taxi-only GPS dataset. It is a synthetic urban car-mobility scenario using an OpenStreetMap-derived road network and TAPAS travel demand, with SUMO used for microscopic traffic simulation and dynamic traffic assignment in the original scenario-generation process. It covers a large Cologne metropolitan study area and a full-day demand scenario.

In our architecture, TAPASCologne is an offline source of road-network topology and demand statistics. It does not supply hidden fields to the GNN, and the simulator does not simply replay its vehicle trajectories. The custom simulator samples departure intensity and OD endpoint patterns from the supplied route demand, then generates new trajectories using this project's rules and publishes only GPS-like fixes.

## 3. Research elements adopted

| Research element | TAPASCologne / literature | Our use |
|---|---|---|
| Urban road graph | OSM-derived road network | Import directed SUMO network edges, junctions, lengths and speed limits |
| Travel demand | TAPAS activity/travel demand mapped to roads | Parse route departures and route endpoints from SUMO route file |
| Time-of-day demand | Full-day departure profile | Build empirical 10-minute departure intensity bins |
| Origin/destination pattern | Trip route endpoints | Derive weighted origin/destination endpoint distributions |
| Microscopic motion | SUMO vehicle dynamics in original dataset pipeline | Generate new motion with an inspectable IDM-inspired rule engine |
| Mobility observations | Time-stamped vehicle positions | Publish only pseudonymous device ID, timestamp, latitude and longitude |

## 4. What changed from the original research scenario and why

1. **SUMO's microscopic traffic engine is not used to generate our output trajectories.** We import SUMO network/demand formats but use a custom rule-based engine. This makes movement rules controllable and lets us experiment with driver parameters and seeds. It is a methodological adaptation, not an exact reproduction of TAPASCologne.
2. **We preserve demand statistics, not individual trajectories.** Route departures inform the 10-minute arrival profile; route endpoints inform OD sampling. New routes and movement traces are generated. This avoids simply replaying the benchmark trace and creates repeatable controlled input for the GNN.
3. **We simplify route assignment.** Our engine uses shortest-free-flow-time routing, not the original Gawron dynamic user assignment. We therefore do not claim equilibrium route choice or the same congestion feedback as the original scenario.
4. **We simplify traffic controls and vehicle dynamics.** IDM-inspired car-following and stochastic intersection stops are used instead of reproducing all SUMO lane-changing, signal, junction and vehicle-type behaviour. These assumptions require calibration.
5. **We intentionally remove simulation-only output fields.** Earlier versions emitted `state`, `x_m`, `y_m`, `t_s`, `vehicle_id` and internal state counts in the trace. The public observation stream now contains only `device_id`, `timestamp`, `latitude`, and `longitude`. Speed/direction/distance are calculated by later components from successive fixes. This is essential for a fair simulator-to-real-GPS replacement boundary.
6. **We use a pseudonymous device identifier.** `device_id` is the stable-within-run source key. A real deployment should use rotating/pseudonymized IDs and appropriate consent/privacy controls.
7. **We separate source-release scaling from our experimental density multiplier.** `dataset_scale` defaults to 1.0 for the selected route file. Older TAPASCologne releases whose scenario instructions require SUMO `--scale 0.3` should be configured with `dataset_scale: 0.3`; the 0.32.0 release may have different recommended demand/network handling, so inspect its own documentation. Independently, the main experiment sets `density_multiplier: 1.3`, meaning 30% above the selected route-file baseline. The effective empirical arrival multiplier is `dataset_scale × density_multiplier`; these parameters must not be conflated.
8. **We do not add IoT/task information.** No sensor events, communication/network metrics, edge/cloud resources or task execution are generated by Component 1. Those belong to separate components if required by the final project.

## 5. Validation and interpretation

### Software-level validation

The automated tests verify deterministic same-seed streaming, temporally correlated GPS noise, one-second reporting for both driving and resting devices, opaque reproducible device IDs, non-coincident rest anchors, same-edge vehicle non-overlap, the exact four-field public schema, rejection of extra simulator-only fields, and SUMO projection/shape/turn parsing. In a controlled stationary-device test with 3 m stationary noise scale and AR(1) correlation 0.98, the one-second apparent displacement had median 0.71 m/s, 95th percentile 1.46 m/s and maximum 2.55 m/s over 9,999 differences. These are synthetic test values, not measured receiver accuracy. These tests establish software behaviour, not empirical realism.

### Required empirical validation before claiming realism

When the full TAPASCologne release is supplied, report:

- departure counts per 10-minute bin versus the source route file;
- trip distance and trip duration distributions;
- speed and stop distributions against an appropriate source trace or independent measured data;
- road-edge utilization and congestion sensitivity under multiple demand scales;
- multiple random seeds with means and variability;
- positional error sensitivity under several GPS-noise levels.

Because the current public output intentionally contains no simulator labels or speed, validation metrics must be calculated from private simulator instrumentation or an offline evaluation harness. Such instrumentation must not be exported to the GNN input stream.

## 6. Limitations

- **Dataset execution status:** the supplied project archive did not include the full TAPASCologne `.net.xml` and `.rou.xml` files. The adapter and fixture tests exist, but the included 40-minute smoke run is on the synthetic fallback network. It is not a Cologne-data result.
- **TAPASCologne is itself a synthetic benchmark:** it is research-derived and map/demand-based, not a direct collection of live GPS readings. It provides a structured scenario reference, not ground truth for all real-world driving.
- **Scenario caveats:** the SUMO scenario documentation describes limitations involving network topology, lane data, speed limits, traffic-light programs, route mapping and demand mapping. Inspect the exact downloaded release and license before use.
- **No Gawron assignment:** shortest-free-flow-time routing is simpler and does not reproduce dynamic user equilibrium.
- **Simplified vehicle behaviour:** the IDM-inspired model and driver parameter distributions are not calibrated to Cologne observations in the current delivery.
- **Simplified intersections:** stochastic stops do not reproduce real signal phase plans, right-of-way logic or coordinated traffic control.
- **Resting/parking assumptions:** parking and garage durations/probabilities are project assumptions. They are hidden from the GPS interface, but they influence the generated position/time sequences.
- **GPS noise is synthetic:** the revised receiver error is a per-device AR(1) correlated bias with configurable `noise_correlation` (default 0.98) and stationary scale `noise_std_m` (default 3 m). This reduces unrealistic one-second position jumps compared with independent white noise, but it is not a validated receiver model. Urban canyon, multipath, device differences, outages and realistic horizontal-accuracy estimates are not fully represented.
- **Observation cadence is simplified but state-neutral:** the default simulator reports every active/resting device once per second. It no longer uses a 30-second resting cadence that could reveal a hidden parking state. Real mobile operating systems may adapt sampling cadence; that behaviour is not modeled in this baseline.
- **No-fix semantics:** a device that completes its empirical trip or leaves the simulation stops reporting. Component 2 must treat the absence of a new fix after a configurable timeout as missing/stale data, not as a speed or stop label. A no-fix event is not explicitly emitted because it is not a GPS fix.
- **SUMO geometry and coordinates:** the adapter now preserves lane polylines and uses the SUMO `location` projection plus `netOffset` to inverse-project GPS coordinates. It requires a valid `projParameter`; networks with `projParameter="!"` are rejected rather than assigned an approximate fixed Cologne centre.
- **SUMO routing constraints:** passenger-inaccessible lanes/edges and passenger-disallowed connections are filtered; SUMO `<connection>` records constrain legal edge-to-edge turns when present. This is still not a complete SUMO reproduction: lane-index-specific connections, signal phases, junction internal links, turn penalties and all vehicle classes are not modeled.
- **Empirical trip semantics:** for a TAPASCologne route file, route origins are trip starts, not city-boundary gates. The simulator samples these origins and OD endpoints and ends the device trace at the sampled destination; it does not invent a return trip to a randomly selected origin or append extra synthetic trips. The route file's trip endpoints are not necessarily true physical city gates.
- **Routing performance:** routes are found with cached pure-Python Dijkstra over free-flow edge travel times. Benchmark the selected 06:00–08:00 slice before attempting a full-day run; no full-scale Cologne performance claim is made here.
- **No sensor identity guarantee:** a phone carried by a passenger may not follow the vehicle's exact location; a real mobile deployment needs a clear data-collection protocol.
- **Privacy:** location traces are sensitive. Real deployments require consent, minimization, retention limits, secure handling and pseudonymous identifiers.
- **No IoT/task layer:** this component does not generate sensor, communication or task-execution data.

## 7. References

1. S. Uppoor, O. Trullols-Cruces, M. Fiore, and J. M. Barceló-Ordinas, “Generation and Analysis of a Large-Scale Urban Vehicular Mobility Dataset,” *IEEE Transactions on Mobile Computing*, vol. 13, no. 5, pp. 1061–1075, 2014. DOI: [10.1109/TMC.2013.27](https://doi.org/10.1109/TMC.2013.27).
2. Eclipse SUMO, “TAPASCologne Scenario,” [https://sumo.dlr.de/docs/Data/Scenarios/TAPASCologne.html](https://sumo.dlr.de/docs/Data/Scenarios/TAPASCologne.html).
3. CITI Lab, “Vehicular Mobility Trace of the City of Cologne, Germany,” [https://www.citi-lab.fr/skills/opendata/](https://www.citi-lab.fr/skills/opendata/).
4. P. Álvarez López et al., “Microscopic Traffic Simulation using SUMO,” *IEEE International Conference on Intelligent Transportation Systems (ITSC)*, 2018.
5. Eclipse SUMO documentation, [https://sumo.dlr.de/docs/](https://sumo.dlr.de/docs/).

## 8. Reproducible run

```bash
pip install -r requirements.txt
pytest -q
python run_simulation.py \
  --config config/sim_config.json \
  --net /path/to/Cologne.net.xml \
  --routes /path/to/Cologne-24h.rou.xml \
  --duration 3600
```

The CSV output is GPS-only. `run_summary.json` records source provenance and aggregate diagnostics; do not pass that summary to the GNN as a sequence of observations. If the network and route arguments are omitted, the run is a synthetic software smoke test, not a TAPASCologne experiment.

## Live map visualization (engineering addition)

A browser-based live map dashboard is included as `run_dashboard.py` and `templates/index.html`. It serves a Leaflet map with OpenStreetMap basemap tiles and receives the simulator's GPS observations through a Server-Sent Events (SSE) endpoint (`/stream`). Each pseudonymous device is rendered as a moving dot; the map updates the dot using only `device_id`, `timestamp`, `latitude`, and `longitude`.

This visualization is an engineering/observability feature, not a mobility model and not a source of additional vehicle telemetry. The browser-facing stream contains only the four-field GPS contract. Device counts and fix counts shown in the dashboard are computed from received GPS observations. The UI intentionally does not show speed, route, road-edge ID, parking/garage state, or simulator ground truth. OpenStreetMap provides map tiles only; it does not validate the simulated trajectories. An internet connection is needed for the basemap tiles, while the simulator and SSE endpoint run locally.

Run from the project directory:

```bash
python run_dashboard.py --host 127.0.0.1 --port 8050
```

Then open `http://127.0.0.1:8050`. The dashboard's playback speed is configurable. The default scenario remains the synthetic radial/ring fallback unless a local TAPASCologne SUMO network and route demand are explicitly configured. The dots are simulated GPS observations, never real live vehicles.


## 8. Review-driven corrections in this revision

The following changes address the code review received after the initial handover:

| Review finding | Correction in this revision | Remaining caveat |
|---|---|---|
| Independent 3 m noise caused implausible one-second speeds | Per-device temporally correlated AR(1) GPS error (`noise_correlation=0.98`) | Must still be calibrated against a receiver dataset; Component 2 should smooth/quality-check fixes |
| 1 s driving / 30 s resting cadence exposed rest state | One-second cadence for both driving and resting observations | Real OS power-saving cadence is not modeled |
| SUMO lane shapes ignored | Interpolate along imported lane polyline geometry | Lane changes and multi-lane lateral movement are simplified |
| Fixed Cologne centre could shift the network | Inverse projection using SUMO `projParameter` and `netOffset`; map centre comes from network centroid | Requires valid projection metadata and a compatible SUMO export |
| Empirical origins treated as perimeter gates and vehicles got invented return trips | Empirical route origins are trip starts; each sampled OD trip ends at its destination and then goes silent | This custom engine does not reproduce the complete TAPAS activity chain |
| Passenger restrictions and turns ignored | Filter passenger-prohibited lanes/edges and route through SUMO connection graph when supplied | Lane-specific connection and signal details remain simplified |
| Density remained 1.0 / 0.3 confused with +30% | Main `density_multiplier=1.3`; separate `dataset_scale=1.0` | Set `dataset_scale=0.3` only for a legacy release whose instructions require 30% demand |
| Sequential IDs exposed creation order | Seeded opaque 48-bit pseudonymous IDs | IDs remain stable within one run; real deployments need privacy-preserving rotation |
| README pointed to wrong research-note path | Corrected to top-level `COMPONENT_1_RESEARCH.md` | None |
| Dashboard accepted local file paths via URL and could bind publicly | File paths are startup CLI options; server refuses non-loopback binding | This is a local development dashboard, not an authenticated production server |
| Rest-anchor and collision tests were weak | Added non-coincident anchor and same-edge non-overlap tests | Does not validate parking capacity or multi-lane collision dynamics |

Batch CSV export now writes incrementally to gzip/CSV, avoiding the previous full-trace in-memory accumulation. The `scripts/` directory was removed because it was empty. The latest automated test suite contains 12 tests. The included benchmark trace is regenerated using the revised noise, reporting and ID behaviour on the synthetic fallback network; it is still not a TAPASCologne run.
