# Component 1: Rule-Based Vehicle Mobility Simulator
## Technical Documentation, Experimental Benchmarks, Results, Findings, Assumptions and Research References

**Project:** GNN-Based Task Allocation
**Component:** Component 1 — Vehicle Mobility Simulation and GPS Data Generation  
**Documentation status:** Based on the implementation and validation results recorded up to 6 November 2026  
**Study area:** Cologne, Germany  
**Primary reference dataset:** TAPASCologne  
**Simulation framework used for reference and network processing:** SUMO  
**Implementation language:** Python  

---

# 1. Executive Summary

Component 1 develops a custom rule-based vehicle mobility simulator using the TAPASCologne road network and travel-demand information.

The purpose of this component is to generate synthetic vehicle GPS trajectories that can later be supplied to Component 2, the Graph Neural Network (GNN) component.

The implementation uses:

- The TAPASCologne road network as its geographical and road-network foundation.
- TAPASCologne trip demand as a reference for vehicle origin-destination demand and departure-time distribution.
- A custom rule-based vehicle movement simulator to generate new vehicle movement.
- Geographic coordinate conversion to produce latitude and longitude.
- A GPS-only output interface for downstream processing.

**Important distinction:** The simulator does not replay the original SUMO vehicle trajectories. It uses the TAPASCologne scenario as a reference and generates new vehicle movement using custom rules. Therefore, the generated trajectories are synthetic simulation outputs, not real vehicle GPS measurements.

A 600-second simulation run produced:

- 4,023,356 GPS records.
- 13,853 observed vehicle IDs.
- 13,963 vehicles spawned, according to the run summary.
- 1,356 vehicles exited.
- Zero invalid GPS records in the quality audit.
- Zero duplicate vehicle-timestamp pairs.
- Zero time intervals greater than 1.01 seconds.
- 13 out of 13 automated tests passed.

Spatial comparisons also showed a strong relationship between the TAPASCologne origin distribution and the simulator's starting-position distribution. However, this is evidence of similarity to the reference demand distribution, not proof that the generated trajectories reproduce real-world traffic.

The main unresolved validation areas are full temporal-distribution validation across the complete two-hour demand period, investigation of two exceptional high-speed transitions, and independent comparison against real vehicle GPS observations.

---

# 2. Problem Statement

A vehicle mobility dataset is needed for the subsequent GNN component. The downstream component requires vehicle locations over time so that movement characteristics can be derived from consecutive GPS observations.

However, a simulator-generated dataset must not be treated as realistic merely because it contains many GPS points or because vehicle dots move smoothly on a map.

The simulator therefore has two main responsibilities:

1. Generate vehicle movement over a geographical road network using a controlled rule-based approach.
2. Produce a consistent GPS data stream that can be checked statistically and used by the downstream GNN component.

The work also needs to establish how closely the generated data follows the reference demand distribution and what limitations remain.

## 2.1 Objectives

The objectives of Component 1 are:

1. Integrate the TAPASCologne road network.
2. Extract and use TAPASCologne vehicle trip demand.
3. Implement custom rule-based vehicle movement.
4. Generate synthetic vehicle GPS observations.
5. Convert simulated road-network coordinates into geographic coordinates.
6. Maintain a fixed GPS output contract.
7. Validate the generated output for structural and temporal quality.
8. Compare generated vehicle distributions with TAPASCologne demand.
9. Inspect high-speed transitions and road-speed consistency.
10. Produce a documented data-generation component for Component 2.

---

# 3. Research and Dataset Foundation

## 3.1 TAPASCologne

TAPASCologne is a traffic simulation scenario for the city of Cologne, Germany.

According to the official SUMO documentation, its original travel demand comes from TAPAS, an agent-based travel-demand model. The scenario combines road-network information imported from OpenStreetMap with TAPAS-derived travel demand and SUMO-related scenario data.

The official scenario documentation describes the dataset as simulation-oriented data rather than direct observations of real vehicles. It also explicitly documents limitations in road-network quality, junction topology, lane information, speed information, traffic-light information, and trip mapping.

Official source:

https://sumo.dlr.de/docs/Data/Scenarios/TAPASCologne.html

## 3.2 Dataset components used

The implementation uses the following TAPASCologne files:

| File | Purpose |
|---|---|
| `cologne.net.xml` | Road-network structure and road attributes |
| `cologne6to8.trips.xml` | Vehicle trip demand for the 06:00–08:00 period |
| `vtypes.add.xml` | Vehicle-type definitions |

The scenario contains other files and configuration information, but the above files are the principal inputs recorded for this implementation.

## 3.3 Dataset inspection results

The following values were obtained from inspection of the local dataset:

| Property | Observed result |
|---|---:|
| Directed road edges | 71,368 |
| Junctions / nodes | 31,584 |
| Total trips in the 06:00–08:00 trip file | 252,731 |
| First departure time | 21,600 seconds |
| Last departure time | 28,799 seconds |
| Vehicle type in inspected trips | `pkw` |
| Trips with missing origin edges | 0 |
| Trips with missing destination edges | 0 |

The departure times correspond to 06:00:00 through 07:59:59 when interpreted as seconds from midnight.

The trip file therefore represents a two-hour morning period, not a complete day of observed GPS traces.

## 3.4 Geographic reference

The inspected network contains the following geographic metadata:

| Property | Value |
|---|---|
| Projection | UTM zone 32 |
| Ellipsoid / datum | WGS84 |
| Geographic longitude minimum | 6.166558 |
| Geographic latitude minimum | 50.735925 |
| Geographic longitude maximum | 7.295276 |
| Geographic latitude maximum | 51.840721 |

The local network coordinates are transformed into geographic coordinates for GPS output.

A conversion check was performed using a SUMO coordinate example:

- Input local coordinate: x = 24615.68, y = 1792.97
- Converted latitude: approximately 50.830383
- Converted longitude: approximately 7.113024

This confirms that the coordinate-conversion path produced a plausible geographic coordinate for the tested point. It is not a complete independent geospatial accuracy assessment of every network coordinate.

---

# 4. System Architecture

## 4.1 Overall workflow

The implemented workflow can be represented as:

1. Load TAPASCologne road-network data.
2. Parse vehicle trip demand.
3. Build the internal road-network representation.
4. Initialize the custom vehicle simulation.
5. Generate vehicle entries using the demand profile.
6. Move vehicles using the custom movement rules.
7. Convert vehicle positions to geographic coordinates.
8. Record GPS observations.
9. Save the generated dataset and run summary.
10. Perform automated and statistical validation.

## 4.2 Architecture diagram

```text
                 TAPASCologne Dataset
                         |
             +-----------+-----------+
             |                       |
        Road Network             Trip Demand
        cologne.net.xml          cologne6to8.trips.xml
             |                       |
             v                       v
       Road Network             Demand Parser
       Loader                        |
             |                       |
             +-----------+-----------+
                         |
                         v
              Internal Road Network
                         |
                         v
             Custom Rule-Based Vehicle
                    Simulator
                         |
             +-----------+-----------+
             |                       |
       Vehicle Movement       Vehicle Departure
       and Road Progression   / Entry Logic
             |                       |
             +-----------+-----------+
                         |
                         v
              Geographic Conversion
                         |
                         v
                 GPS Record Output
                         |
                         v
              Validation and Auditing
                         |
                         v
                Component 2 Input
```

## 4.3 Custom simulator versus SUMO

SUMO is used as a reference traffic-simulation framework and provides the source road-network and scenario information.

However, the final custom simulator is not simply a SUMO trajectory exporter.

The custom implementation generates new vehicle movement using its own rule-based logic. It uses the road-network and demand information as inputs, but does not claim to reproduce the exact individual trajectories produced by SUMO.

This distinction matters when interpreting the results:

- TAPASCologne supplies reference demand and network information.
- The custom simulator generates new synthetic vehicle trajectories.
- Similarity to TAPASCologne distributions is a validation comparison.
- It is not a comparison against real measured vehicle trajectories.

---

# 5. Road-Network Processing

## 5.1 Network loading

The SUMO network is loaded and converted into an internal road-network representation.

The network contains:

- Directed road edges.
- Junction nodes.
- Edge lengths.
- Speed-limit attributes.
- Lane information.
- Road geometry.

The internal network representation uses lists for the edge and node collections.

The network loader used in the implementation returns the loaded network and an edge-ID-to-index mapping.

## 5.2 Road geometry processing

The road geometry processing was improved during implementation.

The recorded improvements include:

1. Using usable lane geometry.
2. Reading lane speed and length information.
3. Converting the network geometry into a centered local coordinate frame.
4. Adding network junction endpoints to the geometry where needed.
5. Removing consecutive duplicate geometry points.
6. Computing the complete geometry length.
7. Selecting lane geometry based on its closeness to the expected movement distance.

These changes were intended to make the internal road representation more consistent for vehicle movement and coordinate conversion.

## 5.3 Geometry consistency audit

A geometry-length comparison was performed across the network.

| Metric | Result |
|---|---:|
| Total inspected directed edges | 71,368 |
| Edges with more than 1% mismatch | 1 |
| Edges with more than 5% mismatch | 1 |
| Edges with more than 10% mismatch | 1 |

The largest mismatch was associated with:

- Edge ID: `40230543#2`
- Edge length: approximately 1.0 metre
- Geometry length: approximately 0.07071 metre
- Absolute difference: approximately 0.9293 metre

This was a very short, degenerate edge. The audit therefore found no widespread large-edge geometry mismatch in the inspected network.

**Interpretation:** This is an internal geometry-consistency result. It does not prove that every road shape in the source network matches the actual physical road.

---

# 6. Demand Processing and Vehicle Entry

## 6.1 Trip-demand parsing

The demand parser reads TAPASCologne trip information and extracts origin, destination, and departure-time information.

The inspected trip file contained 252,731 trips.

All inspected trips were identified as passenger-car trips (`pkw`), and no missing origin or destination edges were found in that file.

## 6.2 Departure-time distribution

The demand profile is grouped into ten-minute time bins.

The first ten-minute bin corresponds to 06:00–06:09:59.

The first twelve bins inspected were:

| Time interval | TAPAS departures |
|---|---:|
| 06:00–06:09 | 11,514 |
| 06:10–06:19 | 13,827 |
| 06:20–06:29 | 19,320 |
| 06:30–06:39 | 22,948 |
| 06:40–06:49 | 22,997 |
| 06:50–06:59 | 23,768 |
| 07:00–07:09 | 24,677 |
| 07:10–07:19 | 24,468 |
| 07:20–07:29 | 26,053 |
| 07:30–07:39 | 26,887 |
| 07:40–07:49 | 20,187 |
| 07:50–07:59 | 16,085 |

These values describe the demand distribution in the inspected TAPASCologne trip file.

They are not counts of real-world vehicles observed on Cologne roads.

## 6.3 Arrival-rate logic

The simulator uses the empirical departure profile to determine vehicle entry rates.

The recorded implementation selects a ten-minute demand slot based on the simulation clock and applies the dataset scale and density multiplier.

Conceptually:

\[
\text{Entry demand}
=
\text{TAPAS demand for time slot}
\times
\text{dataset scale}
\times
\text{density multiplier}
\]

The final implementation uses:

| Parameter | Value |
|---|---:|
| Dataset scale | 1.0 |
| Density multiplier | 1.3 |
| Demand-bin duration | 10 minutes |

The density multiplier of 1.3 means that the simulator targets 30% more demand than the unscaled reference count.

This is a chosen simulation parameter. It is not a value established by real-world calibration.

## 6.4 First ten-minute entry comparison

For the first ten-minute interval:

\[
11,514 \times 1.3 = 14,968.2
\]

The expected scaled entry count is therefore approximately 14,968.

The actual successful first-entry count recorded by the simulator was 13,853.

The agreement was calculated as:

\[
\text{Count agreement}
=
\frac{13,853}{14,968.2}\times100
\]

\[
\approx 92.55\%
\]

| Metric | Result |
|---|---:|
| TAPAS departures | 11,514 |
| Density multiplier | 1.3 |
| Expected scaled entries | 14,968 |
| Actual successful first entries | 13,853 |
| Count agreement | 92.55% |
| Difference | Approximately 1,115 |

This comparison covers the first ten-minute bin only.

It must not be presented as a full temporal-profile correlation or as proof that the complete two-hour temporal distribution has been validated.

---

# 7. Rule-Based Vehicle Movement

## 7.1 Purpose

The custom vehicle simulator is responsible for generating new vehicle movement over the loaded road network.

Each vehicle has an individual simulation identity and movement state.

The simulator maintains vehicle information internally and produces GPS observations from vehicle positions.

## 7.2 Speed model

The final recorded desired-speed function is:

```python
def _desired_speed(self, v, e):
    base_speed = min(e.speed_limit, 130.0 / 3.6)
    return min(base_speed * v.v0_factor, e.speed_limit)
```

The function uses:

- The edge speed limit.
- A nominal speed ceiling of 130 km/h before applying the vehicle factor.
- A per-vehicle speed factor, `v.v0_factor`.
- A final cap at the road edge's configured speed limit.

An important technical detail is that this is **not a strict 130 km/h maximum speed limit**.

If an edge has a configured speed limit of approximately 300 km/h, the vehicle factor can raise the desired speed above 130 km/h, because the final cap is the edge speed limit.

The maximum observed speed in the 600-second run was approximately 151.64 km/h.

Therefore, the documentation must not describe the current implementation as enforcing a hard 130 km/h maximum.

## 7.3 Vehicle spawning

The vehicle entry logic attempts to place vehicles onto available road lanes.

The initial speed is set using the lower of:

- 8.0 m/s.
- The vehicle's calculated desired speed.

The simulator records successful first-entry events. A vehicle is marked as having entered the city so that later re-entry events are not counted as new first entries.

## 7.4 GPS error

The implementation includes a GPS-error component.

The precise error distribution, parameter values, and empirical calibration against a real GPS receiver have not been established in the validation results documented here.

Therefore, the existence of a GPS-error mechanism can be documented, but its realism or accuracy must not be claimed without further measurement.

---

# 8. GPS Output Contract

## 8.1 Public output schema

The simulator exposes exactly four public fields:

| Field | Meaning |
|---|---|
| `device_id` | Identifier of the simulated vehicle |
| `timestamp` | Time associated with the GPS observation |
| `latitude` | Geographic latitude |
| `longitude` | Geographic longitude |

The output contract is:

```text
device_id
timestamp
latitude
longitude
```

## 8.2 Internal information versus public output

The simulator may internally maintain information required for movement, such as:

- Vehicle speed.
- Vehicle state.
- Road edge.
- Lane information.
- Destination or movement state.
- Vehicle-specific parameters.

These are internal simulation details and are not part of the public GPS output contract.

The downstream GNN component is expected to derive movement-related features from successive GPS observations.

For example, speed can be estimated from the distance between two consecutive geographic positions and the time difference between their timestamps.

## 8.3 Timestamp interpretation

The generated run uses synthetic reference timestamps.

The date `2026-01-01` in the output is a synthetic simulation timestamp. It is not the date on which the TAPASCologne data was collected, and it must not be presented as an actual historical date of vehicle movement.

---

# 9. Experimental Setup

## 9.1 Software environment

The recorded development environment was:

| Component | Version |
|---|---|
| Operating system | Windows 10 |
| Python | 3.13.5 |
| SUMO | 1.28.0 |
| Shell | Git Bash / MINGW64 |
| Python environment | Project `.venv` |

The project root was:

```text
D:/7th semester/gnn final year project/implement
```

The active Component 1 environment is under:

```text
component_1/.venv
```

## 9.2 Automated test execution

The recorded test command was:

```bash
python -m pytest -v
```

The master validation script was:

```bash
python scripts/run_full_validation.py
```

The final recorded automated test result was:

<badge color="success">13 / 13 tests passed</badge>

Total test execution time was approximately 1.61 seconds.

The result establishes that the tested software checks passed. It does not establish that the simulator reproduces real-world vehicle behaviour.

## 9.3 SUMO smoke tests

Short SUMO tests were also performed.

Recorded results include:

- A five-second SUMO test completed successfully.
- A one-minute SUMO test completed successfully.
- The short test reported 81 vehicles inserted and 3,516 vehicles loaded.

Traffic-light warnings were observed during the one-minute test. In particular, some actuated traffic lights did not have the controlling detectors expected by the configuration.

This means the test confirms that the scenario could be executed, but it does not establish realistic detector-driven adaptive traffic-light behaviour.

---

# 10. Main 600-Second Simulation Results

The final recorded 600-second custom simulation produced the following results.

| Metric | Result |
|---|---:|
| Simulation duration | 600 seconds |
| GPS records | 4,023,356 |
| Observed unique vehicles | 13,853 |
| Vehicles spawned | 13,963 |
| Vehicles exited | 1,356 |
| Wall-clock execution time | 888.56 seconds |
| GPS output file | `data/tapas_gps_600.0s.csv.gz` |
| Run summary | `data/tapas_run_summary_600.0s.json` |
| Spawn-event log | `data/tapas_spawn_events_600.0s.json` |

The difference between 13,963 spawned vehicles and 13,853 observed unique vehicles is 110.

The current recorded results do not establish the precise reason for every one of these 110 vehicles not appearing as an observed unique GPS device. This difference should not be silently attributed to a specific failure cause.

The 600-second simulation took approximately 888.56 seconds of wall-clock time. Thus, the simulation ran slower than real time on the tested environment.

---

# 11. GPS Data Quality Validation

A GPS quality audit was performed on:

```text
data/tapas_gps_600.0s.csv.gz
```

## 11.1 Schema validation

Expected schema:

```text
device_id
timestamp
latitude
longitude
```

Observed schema:

```text
['device_id', 'timestamp', 'latitude', 'longitude']
```

<badge color="success">Schema correct</badge>

## 11.2 Data-quality results

| Check | Result |
|---|---:|
| Total records | 4,023,356 |
| Unique devices | 13,853 |
| Invalid records | 0 |
| Duplicate device/timestamp pairs | 0 |
| Time intervals greater than 1.01 seconds | 0 |

These results show that the inspected output satisfied the tested structural, coordinate-validity, duplicate-key, and timestamp-continuity checks.

They do not prove that every coordinate is physically accurate relative to a real vehicle's position.

## 11.3 Derived speed statistics

Speed was derived from successive GPS positions for the same vehicle.

The audit produced:

| Statistic | Speed (m/s) | Speed (km/h) |
|---|---:|---:|
| Median | 4.61 | 16.60 |
| 95th percentile | 14.54 | 52.34 |
| Maximum | 42.12 | 151.63 |

The number of transitions above selected thresholds was:

| Threshold | Number of transitions |
|---|---:|
| Above 40 m/s (144 km/h) | 67 |
| Above 55 m/s (198 km/h) | 0 |

The maximum speed is derived from consecutive GPS positions, not from a direct real-vehicle speed measurement.

The 67 transitions above 40 m/s were investigated further.

---

# 12. High-Speed Transition and Road-Limit Audit

## 12.1 Initial transition inspection

A separate script inspected high-speed transitions and produced:

```text
data/high_speed_transitions.csv
```

The 67 transitions above 40 m/s were found to be concentrated in a relatively small number of vehicle IDs.

The highest recorded speeds were approximately 144–151.64 km/h.

Repeated high-speed transitions in the same vehicles suggested sustained high movement speeds rather than only isolated single-point GPS jumps.

However, that observation alone cannot establish whether the speeds are realistic.

## 12.2 Road-limit matching

A road-speed audit was then performed by matching the high-speed GPS transitions against nearby road geometries and configured edge speed limits.

The audit reported:

| Classification | Count |
|---|---:|
| Within all matched configured limits | 65 |
| Ambiguous nearby limits | 1 |
| Above all matched limits | 1 |
| Total checked | 67 |

The audit inspected start, midpoint, and end positions against nearby road geometry.

## 12.3 Interpretation

The result means that 65 of the 67 high-speed transitions were within all the matched speed limits stored in the SUMO network.

It does **not** mean that 65 transitions were confirmed to be legal or realistic road speeds.

A large number of inspected edges had configured speed values around 299.99 km/h. Such values are not suitable evidence of actual legal road speed limits.

The two exceptional transitions remain unresolved:

1. One transition was ambiguous because nearby matched road limits differed.
2. One transition was above all matched configured limits.

The audit file was:

```text
data/high_speed_road_limit_check.csv
```

**Conclusion:** The road-limit audit is a network-consistency check, not a real-world speed validation.

---

# 13. Spatial Distribution Validation

Two related spatial comparisons were performed. They must be kept separate because they use different sets of GPS observations.

## 13.1 Starting-position distribution comparison

This comparison uses the first GPS position of each observed vehicle and compares it with TAPASCologne trip-origin locations.

Results:

| Metric | Result |
|---|---:|
| TAPAS trips in first ten-minute interval | 11,514 |
| Missing origin geometries | 0 |
| Vehicles with a first GPS observation | 13,853 |
| TAPAS origin grid cells | 334 |
| GPS starting-position grid cells | 328 |
| Common grid cells | 312 |
| Pearson correlation | 0.9576 |
| Spearman correlation | 0.9526 |
| Top-20 overlap | 13 / 20 |

The high Pearson and Spearman values indicate a strong positive relationship between the compared starting-position cell counts.

The top-20 overlap of 13 out of 20 indicates that most, but not all, of the most frequent origin cells were shared between the two distributions.

## 13.2 Spatial coverage comparison

A second comparison considered all GPS-occupied grid cells rather than only the first position of each vehicle.

Results:

| Metric | Result |
|---|---:|
| GPS occupied grid cells | 406 |
| TAPAS origin grid cells | 334 |
| Cells appearing in both | 330 |
| TAPAS origin-cell coverage | 98.8% |

The 98.8% value is a coverage measure:

\[
\text{Coverage}
=
\frac{\text{TAPAS origin cells also occupied by GPS}}
{\text{TAPAS origin cells}}
\times 100
\]

It does not measure equality of the two distributions.

A cell being occupied by at least one GPS observation does not mean its vehicle count matches the TAPAS demand count.

## 13.3 Broader spatial-distribution comparison

A further spatial comparison produced:

| Metric | Result |
|---|---:|
| Compared grid cells | 410 |
| Pearson correlation | 0.8161 |
| Spearman correlation | 0.8273 |
| Top-20 overlap | 11 / 20 |

This comparison uses all-cell GPS occupancy or unique-vehicle counts against TAPAS origin counts, rather than comparing only first GPS positions.

It is therefore a different comparison from Section 13.1 and should not be treated as a contradictory result.

## 13.4 Spatial coverage bounds

The 600-second GPS output occupied the following geographic bounds:

| Coordinate | Minimum | Maximum |
|---|---:|---:|
| Latitude | 50.829254 | 51.089189 |
| Longitude | 6.811168 | 7.114496 |

The spatial coverage audit reported 406 occupied 1-kilometre grid cells.

## 13.5 Spatial validation conclusion

The strongest spatial result is the starting-position comparison:

- Pearson correlation: 0.9576.
- Spearman correlation: 0.9526.
- Top-20 overlap: 13/20.

This supports the claim that the simulator's starting-position distribution is strongly aligned with the TAPASCologne origin distribution in the inspected first ten-minute interval.

It does not establish that the full movement trajectories, road choices, speeds, or traffic congestion patterns match real-world traffic.

---

# 14. Temporal Validation Status

The simulator uses ten-minute demand bins.

A first-bin count comparison was completed and produced 92.55% agreement between the scaled TAPAS demand and actual successful first entries.

However, a full temporal-distribution validation across all twelve ten-minute bins of the 06:00–08:00 period has not been completed in the results documented here.

A previous minute-by-minute comparison was not retained as a valid validation result because the simulator uses ten-minute demand bins, while the compared minute-level quantities did not represent equivalent measurements.

Therefore:

**Temporal validation status: Partial.**

The appropriate next validation is to compare successful first-entry counts against the scaled TAPAS demand separately for each ten-minute interval over a longer run that covers the complete two-hour demand window.

A single ten-minute count agreement must not be described as full temporal validation.

---

# 15. Consolidated Benchmark and Results Table

The following table summarises the measured checks completed so far.

| Validation area | Benchmark / metric | Measured result | Status |
|---|---|---:|---|
| Network loading | Directed edges | 71,368 | Completed |
| Network loading | Junctions | 31,584 | Completed |
| Demand loading | Parsed trips | 252,731 | Completed |
| Demand integrity | Missing origin edges | 0 | Passed |
| Demand integrity | Missing destination edges | 0 | Passed |
| Automated tests | Tests passed | 13 / 13 | Passed |
| GPS schema | Required fields | 4 / 4 | Passed |
| GPS quality | Invalid records | 0 | Passed |
| GPS quality | Duplicate device/timestamp pairs | 0 | Passed |
| GPS quality | Gaps greater than 1.01 seconds | 0 | Passed |
| Spatial starting distribution | Pearson correlation | 0.9576 | Strong similarity |
| Spatial starting distribution | Spearman correlation | 0.9526 | Strong similarity |
| Spatial starting distribution | Top-20 overlap | 13 / 20 | Partial overlap |
| Spatial coverage | TAPAS origin-cell coverage | 98.8% | Coverage achieved |
| Broader spatial comparison | Pearson correlation | 0.8161 | Positive similarity |
| Broader spatial comparison | Spearman correlation | 0.8273 | Positive similarity |
| First-bin demand count | Scaled count agreement | 92.55% | Partial temporal evidence |
| Road-speed consistency | Within all matched limits | 65 / 67 | Network consistency |
| Road-speed consistency | Ambiguous | 1 / 67 | Unresolved |
| Road-speed consistency | Above all matched limits | 1 / 67 | Unresolved |
| Full temporal profile | All 12 demand bins | Not yet reported | Pending |
| Real GPS validation | Independent measured GPS | Not performed | Pending |

## 15.1 What these benchmarks establish

The completed benchmarks establish that:

- The network and demand inputs can be loaded.
- The custom simulator can produce a large GPS dataset.
- The public GPS output schema is consistent.
- The inspected GPS records pass the implemented structural and continuity checks.
- The simulator's starting-position distribution has a strong statistical relationship with TAPASCologne origin counts.
- Most inspected high-speed transitions were within the configured limits of their matched network edges.

## 15.2 What these benchmarks do not establish

They do not establish that:

- The generated GPS data is equivalent to real measured GPS data.
- The simulator reproduces actual Cologne traffic speeds.
- The simulator reproduces real congestion.
- Every route choice is realistic.
- Every road speed limit in the source network is correct.
- Traffic-light behaviour is calibrated to Cologne.
- The full two-hour temporal distribution has been validated.
- The custom simulator is more accurate than SUMO or another simulator.

---

# 16. Assumptions, Design Choices and Unverified Conditions

This section is especially important for the research paper. A design choice must not be presented as an experimentally established fact.

| Item | Current implementation / observation | Classification | What can safely be claimed |
|---|---|---|---|
| TAPASCologne as reference | Uses TAPAS-derived demand and OSM-based road network | Dataset choice | TAPASCologne is the selected reference scenario |
| Synthetic vehicle movement | Custom rules generate new movement | Design choice | The output is custom-generated synthetic movement |
| Density multiplier | 1.3 | Parameter choice | Demand is scaled to 1.3 times the reference count |
| Dataset scale | 1.0 | Parameter choice | No additional dataset scaling is applied |
| Demand bins | 10 minutes | Implementation choice | Entry rates use ten-minute demand bins |
| Simulation date | 2026-01-01 | Synthetic timestamp choice | The timestamp is a simulation reference date |
| GPS sampling | Approximately one-second intervals | Implementation behaviour | The audit found no interval greater than 1.01 seconds |
| Vehicle type | `pkw` in inspected trip data | Dataset property | The inspected trip file represents passenger cars |
| Speed variation | Per-vehicle `v0_factor` | Model choice | Vehicle desired speed varies by a vehicle-specific factor |
| Nominal speed value | 130 km/h before applying vehicle factor | Model parameter | This is not a strict final speed cap |
| Edge speed limits | Read from SUMO network | Input dependency | The simulator uses configured network speed values |
| GPS error | Error mechanism exists | Model choice | A GPS-error mechanism is implemented |
| GPS error calibration | No independent receiver comparison documented | Unverified | Do not claim realistic GPS-error calibration |
| Random seed | Reproducible seed support recorded | Implementation feature | Seed control is supported; the exact final-run seed should be recorded |
| Traffic lights | SUMO smoke tests produced detector warnings | Limitation | Detector-based adaptive signal realism is not established |
| Road-network quality | Official TAPASCologne documentation lists known issues | Dataset limitation | The source network is not ground truth |
| Route realism | No independent route-level validation reported | Unverified | Do not claim route-level real-world fidelity |
| Density multiplier calibration | No independent traffic-count calibration reported | Unverified | 1.3 is a chosen parameter, not a measured optimum |
| Real GPS comparison | Not performed | Validation gap | Real-world trajectory accuracy remains unknown |

## 16.1 Important dataset limitations

The official TAPASCologne documentation itself identifies limitations in:

- Junction topology.
- Lane-number information.
- Maximum-speed information.
- Traffic-light positions and programs.
- Other traffic-management information.
- Road closures and road works.
- Trip mapping to the OpenStreetMap network.
- Verification of routes.

The official documentation also cautions that the scenario requires further work to improve network quality and verify route mapping.

These are source-dataset limitations, not issues that can be assumed to have been corrected by the custom simulator.

## 16.2 Important model limitations

The custom simulator uses simplified movement rules.

The current evidence does not establish that it models all real driving behaviours, including:

- Human driver reaction.
- Detailed car-following behaviour.
- Lane-changing behaviour calibrated to observed data.
- Real traffic-signal timing.
- Real-world traffic congestion.
- Vehicle-specific acceleration and braking distributions.
- Driver heterogeneity calibrated from naturalistic driving data.

These behaviours should not be claimed unless the implementation and validation explicitly support them.

---

# 17. Main Findings

## Finding 1: The TAPASCologne network and demand can be loaded

The implementation successfully processed 71,368 directed road edges, 31,584 junctions, and 252,731 trips in the inspected 06:00–08:00 file.

No missing origin or destination edges were found in the inspected trip file.

## Finding 2: The custom simulator can generate a large GPS dataset

The 600-second run generated more than four million GPS observations for 13,853 observed vehicle IDs.

The output is suitable as a synthetic mobility-data source for downstream development, subject to the limitations documented in this report.

## Finding 3: GPS output quality checks passed

The inspected dataset had:

- Correct four-field schema.
- Zero invalid records.
- Zero duplicate device-timestamp pairs.
- No gaps greater than 1.01 seconds.

This establishes structural consistency for the tested output.

## Finding 4: Starting-position distribution is strongly aligned with TAPAS demand

The first-position comparison produced Pearson correlation 0.9576 and Spearman correlation 0.9526.

This is evidence that the custom simulator's starting positions follow the spatial distribution of the reference trip origins closely in the tested interval.

## Finding 5: Broader spatial occupancy is also positively related to TAPAS origins

The broader comparison produced Pearson correlation 0.8161 and Spearman correlation 0.8273.

This is a separate metric from the starting-position comparison and should be reported separately.

## Finding 6: The first ten-minute entry count is reasonably close to scaled demand

The actual successful first entries were 92.55% of the expected scaled count.

The result is encouraging for the first ten-minute interval but does not replace a complete two-hour temporal-profile comparison.

## Finding 7: High-speed transitions require careful interpretation

There were 67 transitions above 40 m/s.

Of these, 65 were within all matched configured road limits, one was ambiguous, and one exceeded all matched limits.

Because some network speed values are approximately 299.99 km/h, this audit cannot establish that the high speeds are legally or behaviourally realistic.

## Finding 8: The reference dataset has documented limitations

The official TAPASCologne documentation explicitly identifies network, traffic-management, and demand-mapping issues.

These limitations need to be included in any research paper that uses this scenario.

---

# 18. Limitations and Threats to Validity

The following limitations should be acknowledged in the final research paper.

### 18.1 No independent real-world GPS validation

No independent measured GPS dataset has yet been used to compare the generated trajectories.

Consequently, the simulator's real-world trajectory accuracy is not established.

### 18.2 Simulation-derived reference data

TAPASCologne is itself a simulation scenario built using TAPAS demand, OpenStreetMap network data, and SUMO-related tools.

A comparison against TAPASCologne is therefore a comparison against another simulation-derived reference, not against direct ground-truth GPS measurements.

### 18.3 Limited temporal validation

Only the first ten-minute demand-bin count agreement is currently documented as a completed quantitative temporal comparison.

The full twelve-bin profile requires a longer simulation and a consistent bin-by-bin comparison.

### 18.4 Network speed-limit quality

The SUMO network contains high configured speed values, including values around 299.99 km/h.

These values weaken the interpretation of the road-limit audit as a realism check.

### 18.5 Traffic-light limitations

The SUMO smoke test reported actuated traffic-light warnings involving missing controlling detectors.

The current results do not establish realistic adaptive traffic-signal behaviour.

### 18.6 Simplified movement model

The custom rule-based simulator is not documented as a fully calibrated human-driver model.

The generated movement should therefore be described as rule-based synthetic mobility rather than a fully validated reproduction of human driving.

### 18.7 Simulation performance

The 600-second simulation required approximately 888.56 seconds of wall-clock time.

This is a measured performance result for the recorded environment and run. It should not be generalized to other machines or configurations.

---

# 19. Recommended Additional Validation

The following work would strengthen the research claims.

| Priority | Additional experiment | Purpose |
|---|---|---|
| High | Run the complete 06:00–08:00 period | Cover all twelve demand bins |
| High | Compare all twelve ten-minute entry counts | Establish temporal-profile agreement |
| High | Inspect the two exceptional high-speed transitions | Determine whether they are mapping or movement anomalies |
| High | Record the exact random seed and final configuration | Improve reproducibility |
| High | Compare with independent measured GPS traces | Establish real-world trajectory similarity |
| Medium | Compare road-level vehicle counts | Assess distribution across road segments |
| Medium | Compare speed distributions against measured traffic data | Assess speed realism |
| Medium | Compare travel-time distributions | Assess movement-time realism |
| Medium | Evaluate acceleration and jerk distributions | Assess vehicle-kinematic realism |
| Medium | Inspect signal and junction behaviour | Assess traffic-control realism |

The most important missing experiment is an independent real-world GPS comparison.

A strong spatial correlation with TAPASCologne is useful, but it cannot substitute for comparison against measured vehicle trajectories.

---

# 20. Reproducibility and Output Files

The recorded outputs from the final 600-second run include:

| File | Purpose |
|---|---|
| `data/tapas_gps_600.0s.csv.gz` | Generated GPS dataset |
| `data/tapas_run_summary_600.0s.json` | Simulation summary |
| `data/tapas_spawn_events_600.0s.json` | Successful first-entry events |
| `data/high_speed_transitions.csv` | High-speed transition inspection |
| `data/high_speed_road_limit_check.csv` | Road-limit matching audit |

Relevant scripts include:

| Script | Purpose |
|---|---|
| `scripts/run_tapas_simulation.py` | Run custom TAPAS-based simulation |
| `scripts/run_full_validation.py` | Run the master validation process |
| `scripts/gps_quality_audit.py` | Validate GPS schema and record quality |
| `scripts/compare_starting_distribution.py` | Compare starting-position distributions |
| `scripts/compare_tapas_origins.py` | Compare TAPAS origin coverage |
| `scripts/spatial_coverage_audit.py` | Inspect spatial coverage |
| `scripts/spatial_distribution_metrics.py` | Calculate spatial distribution metrics |
| `scripts/compare_spawn_temporal.py` | Compare demand and successful entries |
| `scripts/inspect_high_speed_transitions.py` | Inspect high-speed GPS transitions |
| `scripts/check_high_speed_road_limits.py` | Compare high-speed transitions with road limits |

The exact final random seed and complete configuration snapshot should be retained with the experiment outputs before publication.

---

# 21. Research References

The following references are relevant to the dataset, simulation framework, and validation methodology. They should be cited for the concepts and source materials they actually support; they are not evidence that the custom simulator has achieved the same results as those studies.

## 21.1 TAPASCologne scenario and data source

**[1] Eclipse SUMO Documentation.** “TAPAS Cologne Scenario.”

Official documentation describing the scenario, its road-network and demand sources, contents, and known quality limitations.

https://sumo.dlr.de/docs/Data/Scenarios/TAPASCologne.html

**Why this reference matters:** This is the primary source for explaining what TAPASCologne contains and for acknowledging its known limitations. It should be cited whenever describing the dataset's origin and constraints.

## 21.2 TAPAS travel-demand model

**[2] Heinrichs, M., Krajzewicz, D., Cyganski, R., and von Schmidt, A. (2017).** “Introduction of car sharing into existing car fleets in microscopic travel demand modelling.” *Personal and Ubiquitous Computing.*

DOI: https://doi.org/10.1007/s00779-017-1031-3

**Why this reference matters:** It provides research background for the TAPAS travel-demand modelling framework. It is relevant when describing the demand-model foundation, not as direct validation of our custom movement simulator.

## 21.3 SUMO traffic simulation framework

**[3] Alvarez Lopez, P., Behrisch, M., Bieker-Walz, L., Erdmann, J., Flötteröd, Y., Hilbrich, R., Lücken, L., Rummel, J., Wagner, P., and Wießner, E. (2018).** “Microscopic Traffic Simulation using SUMO.” *2018 21st International Conference on Intelligent Transportation Systems (ITSC)*, pp. 2575–2582.

DOI: https://doi.org/10.1109/ITSC.2018.8569938

**Why this reference matters:** This is the recommended general SUMO reference. It supports the description of SUMO as a microscopic traffic-simulation framework.

## 21.4 Vehicle trajectory-level validation

**[4] Xyntarakis, M., Alexiadis, V., Punzo, V., Campbell, R., Skabardonis, A., and colleagues (2017).** “A Framework for Validating Traffic Simulation Models at the Vehicle Trajectory Level.” Federal Highway Administration research report.

Official report page:

https://its.berkeley.edu/publications/framework-validating-traffic-simulation-models-vehicle-trajectory-level

Report:

https://rosap.ntl.bts.gov/view/dot/34271

**Why this reference matters:** This is particularly relevant to Component 1. It explains why trajectory-level validation should include vehicle kinematics, safety, comfort, and traffic-flow measures rather than relying only on aggregate traffic counts.

## 21.5 Trajectory reconstruction and simulation validation

**[5] “Trajectory data reconstruction and simulation-based validation against macroscopic traffic patterns.” (2015).** *Transportation Research Part B: Methodological*, Volume 80, pp. 82–106.

DOI: https://doi.org/10.1016/j.trb.2015.06.010

**Why this reference matters:** It discusses trajectory quality and validation at both individual-trajectory and macroscopic traffic-pattern levels. It supports the decision to evaluate both GPS-level quality and spatial/aggregate distributions.

## 21.6 Large-scale traffic simulation calibration and validation

**[6] “Calibration and validation of large-scale traffic simulation networks: a case study.” (2018).** *Procedia Computer Science*, Volume 130, pp. 844–849.

DOI: https://doi.org/10.1016/j.procs.2018.04.076

**Why this reference matters:** It discusses the role of multiple real-world data sources in calibration and validation of large-scale traffic simulation networks. It is relevant to the need for independent measured data.

## 21.7 Traffic simulation uncertainty

**[7] Bayarri, M. J., Berger, J. O., Molina, G., Rouphail, N. M., and Sacks, J. (2004).** “Assessing Uncertainties in Traffic Simulation: A Key Component in Model Calibration and Validation.” *Transportation Research Record*, Volume 1876.

DOI: https://doi.org/10.3141/1876-04

**Why this reference matters:** It explains that simulation results are affected by input uncertainty, parameter uncertainty, stochasticity, and model discrepancy. It is useful when discussing the limitations of claims based on one simulation run.

## 21.8 Additional trajectory-quality research

**[8] Zhang, T. T., Jin, P. J., Piccoli, B., and Sartipi, M. (2024).** “Deep spatial-temporal embedding for vehicle trajectory validation and refinement.” *Computer-Aided Civil and Infrastructure Engineering*, Volume 39, Issue 11, pp. 1597–1615.

DOI: https://doi.org/10.1111/mice.13160

**Why this reference matters:** It discusses trajectory validation and refinement, including the importance of checking position, speed, car-following, lane-changing, consistency, and jerk-related properties.

---

# 22. How to Position Component 1 in the Research Paper

The following is a defensible way to describe the contribution.

Component 1 implements a custom rule-based vehicle mobility simulator using the TAPASCologne road network and travel-demand distribution as reference inputs. The system generates synthetic vehicle GPS observations through custom movement rules and exports a standardized four-field GPS interface consisting of vehicle identifier, timestamp, latitude, and longitude.

The generated dataset is evaluated through automated software tests, GPS-record quality checks, spatial-distribution comparisons, departure-count comparisons, and road-speed consistency checks. In a 600-second experiment, the simulator generated 4,023,356 GPS records for 13,853 observed vehicle identifiers. The GPS quality audit found no invalid records, duplicate vehicle-timestamp pairs, or intervals exceeding 1.01 seconds. The comparison of vehicle starting positions against TAPASCologne trip origins produced Pearson and Spearman correlations of 0.9576 and 0.9526, respectively.

These results indicate that the implementation can generate a structurally consistent synthetic GPS dataset with a starting-position distribution that is strongly aligned with the selected TAPASCologne demand reference. However, because TAPASCologne is itself simulation-derived and no independent real-world GPS validation has yet been performed, the results should not be interpreted as proof of real-world trajectory accuracy. Full temporal-profile validation and investigation of two exceptional high-speed transitions remain outstanding.

---

# 23. Final Completion Assessment

| Area | Assessment |
|---|---|
| TAPASCologne network integration | Completed |
| TAPAS trip-demand integration | Completed |
| Custom rule-based movement | Implemented |
| Geographic coordinate conversion | Implemented and spot-checked |
| GPS-only output contract | Completed |
| Reproducible seed support | Implemented; final seed should be recorded |
| Automated tests | 13/13 passed |
| GPS quality audit | Passed recorded checks |
| Starting-position spatial comparison | Completed |
| Broader spatial comparison | Completed |
| First ten-minute demand comparison | Completed |
| Full two-hour temporal comparison | Pending |
| High-speed transition inspection | Completed |
| Two exceptional transition investigations | Pending |
| Independent real-world GPS validation | Not performed |
| Final configuration snapshot | Should be archived |
| Component 2 integration | Separate next-stage task |

## Final conclusion

Component 1 has reached a functional implementation and has passed the recorded software and GPS-quality checks. Its strongest quantitative validation result is the high correlation between the generated starting-position distribution and the TAPASCologne trip-origin distribution.

The results support using Component 1 as a synthetic GPS-data generation component for the next stage of the project. They do not yet support a claim that the generated trajectories are a validated reproduction of real-world Cologne vehicle movement.

For the research paper, the most accurate description is:

**A custom rule-based synthetic vehicle mobility simulator, driven by TAPASCologne reference demand and road-network information, with demonstrated output consistency and spatial starting-distribution similarity, but without completed independent real-world GPS validation.**