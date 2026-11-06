# Component 1 --- Implementation Notes

## 1. Role

Component 1 is a custom rule-based synthetic vehicle mobility simulator.
It uses TAPASCologne road-network and trip-demand inputs and generates
synthetic GPS observations for downstream components.

It does not replay SUMO-generated vehicle trajectories. SUMO-GUI is used
separately to inspect and run the TAPAS reference scenario.

## 2. Inputs and provenance

Dataset root: `datasets/TAPASCologne/`

  File                      Role
  ------------------------- ----------------------------
  `cologne.net.xml`         SUMO road network
  `cologne6to8.trips.xml`   TAPAS trip definitions
  `vtypes.add.xml`          Passenger-car type (`pkw`)

Inspected facts: - 71,368 directed edges. - 31,584 junctions/nodes. -
Network projection: UTM zone 32 / WGS84. - Original geographic bounds:
longitude 6.166558--7.295276; latitude 50.735925--51.840721. - 252,731
trips, all inspected as `pkw`. - First departure: 21600 seconds (06:00);
last: 28799 seconds (07:59:59).

TAPASCologne is a simulation-derived mobility scenario, not a collection
of independently measured vehicle GPS traces. Component 1 output is
synthetic.

## 3. Architecture

``` text
TAPASCologne network + trip demand
              |
              v
     Network and demand loading
              |
              v
   Custom rule-based vehicle simulator
              |
              v
      GPS observation recording
              |
              v
   GPS-only output + run summary
              |
              v
      Component 2 preprocessing
```

SUMO reference simulation and custom Python simulation are separate
workflows.

## 4. Public output contract

Exactly four output fields:

  Field         Meaning
  ------------- -------------------------------------
  `device_id`   Simulated vehicle/device identifier
  `timestamp`   Observation timestamp
  `latitude`    GPS latitude
  `longitude`   GPS longitude

Speed, heading, road/edge ID, lane ID, destination, parking state, and
simulator internals are not exposed. Component 2 may derive movement
features from consecutive GPS observations, such as displacement, speed,
acceleration, bearing, turning behaviour, and stop duration.

## 5. Movement and demand logic

The simulator uses its own rule-based movement logic over the loaded
road network. The recorded desired-speed function is:

``` python
def _desired_speed(self, v, e):
    base_speed = min(e.speed_limit, 130.0 / 3.6)
    return min(base_speed * v.v0_factor, e.speed_limit)
```

This is not a strict 130 km/h maximum: the per-vehicle factor is applied
after the nominal cap, and the final cap is the edge's configured speed
limit. Some network edges have configured limits around 299.99 km/h.

The arrival rate uses TAPAS demand in ten-minute bins, multiplied by
dataset scale and density multiplier. The recorded density multiplier is
1.3. This is a selected scaling parameter, not an independently
calibrated real-world density estimate.

The timestamp date `2026-01-01` is a synthetic reference date, not the
TAPASCologne collection date.

## 6. Geometry and coordinate handling

The implementation reads edge endpoints and shape geometry from the SUMO
network and converts local network coordinates to latitude/longitude.

Geometry handling includes usable-lane selection, edge lengths, shape
points, junction endpoints, removal of consecutive duplicate points, and
selecting geometry close to expected movement distance.

Recorded geometry audit: - Only 1 of 71,368 edges had a geometry-length
mismatch above 1%, 5%, or 10%. - Worst relative mismatch: edge
`40230543#2`, a very short/degenerate edge; edge length 1 m and geometry
length about 0.07071 m.

Where lane limits differ, speed extraction uses the maximum speed among
usable lanes. Edge length uses the maximum of mean lane lengths,
endpoint Euclidean distance, and a 1 m floor. These are implementation
choices.

## 7. Demand profile

Recorded ten-minute demand counts:

``` text
[11514, 13827, 19320, 22948, 22997, 23768,
 24677, 24468, 26053, 26887, 20187, 16085]
```

The custom simulator uses these ten-minute bins with dataset scale and
density multiplier 1.3.

## 8. Validation entry point and recorded run

Known master command:

``` bash
python scripts/run_full_validation.py
```

Recorded result: 13/13 tests passed in 1.61 seconds.

Recorded 600-second custom simulation:

  Measure                        Result
  -------------------- ----------------
  Simulated duration        600 seconds
  GPS records                 4,023,356
  Observed devices               13,853
  Vehicles spawned               13,963
  Vehicles exited                 1,356
  Wall-clock runtime     888.56 seconds

Recorded output files:

``` text
data/tapas_gps_600.0s.csv.gz
data/tapas_run_summary_600.0s.json
data/tapas_spawn_events_600.0s.json
```

## 9. GPS quality audit

-   Exactly four expected output fields.
-   Zero invalid records.
-   Zero duplicate `(device_id, timestamp)` pairs.
-   Zero sampling intervals above 1.01 seconds.
-   4,009,503 derived speed samples.
-   Median derived speed: 4.61 m/s (16.60 km/h).
-   95th percentile: 14.54 m/s (52.34 km/h).
-   Maximum: 42.12 m/s (151.63 km/h).

These speeds are derived from GPS point differences, not emitted speed
fields.

## 10. Spatial validation

### Starting-position distribution

  Measure                                 Result
  ------------------------------------- --------
  TAPAS first-bin trips                   11,514
  Missing origin geometries                    0
  Vehicles with first GPS observation     13,853
  TAPAS origin grid cells                    334
  GPS starting grid cells                    328
  Common cells                               312
  Pearson correlation                     0.9576
  Spearman correlation                    0.9526
  Top-20 overlap                           13/20

### Broader spatial occupancy comparison

  Measure                  Result
  ---------------------- --------
  Compared grid cells         410
  Pearson correlation      0.8161
  Spearman correlation     0.8273
  Top-20 overlap            11/20

This uses all-cell GPS occupancy/unique-vehicle counts against TAPAS
origins. It is not the same comparison as starting-position
distribution.

### Coverage

-   GPS occupied cells: 406.
-   TAPAS origin cells: 334.
-   Shared cells: 330.
-   Reported coverage: 98.8%.

Coverage is not a distribution-similarity score.

## 11. Temporal validation status

For the first ten-minute bin: - TAPAS departures: 11,514. - Density
multiplier: 1.3. - Expected scaled entries: 14,968. - Actual successful
first entries: 13,853. - Count agreement: 92.55%.

This is one ten-minute bin only. Full 12-bin temporal-profile validation
over 06:00--08:00 was pending. Do not report a full-period temporal
correlation.

## 12. High-speed audit

There were 67 transitions above 40 m/s (144 km/h).

Road-limit matching results:

  Status                                   Count
  -------------------------------------- -------
  Within all matched configured limits        65
  Ambiguous nearby limits                      1
  Above all matched limits                     1

Many matched edges have configured limits around 299.99 km/h. These are
SUMO configuration values, not verified legal speed limits. One
transition above all matched limits remained unresolved. This audit does
not prove that all high speeds are realistic.

## 13. Assumptions, choices, and limitations

  -----------------------------------------------------------------------
  Item                                Caveat
  ----------------------------------- -----------------------------------
  TAPASCologne demand                 Scenario reference, not measured
                                      GPS ground truth

  Density multiplier 1.3              Selected scaling parameter, not
                                      independently calibrated

  Ten-minute bins                     Demand aggregation used by
                                      simulator

  Timestamp date 2026-01-01           Synthetic reference date

  Lane speed selection                Maximum usable-lane speed when lane
                                      limits differ

  Edge length                         Lane/endpoint-derived value with 1
                                      m floor

  Sampling                            Recorded intervals no greater than
                                      1.01 seconds

  Road speed limits                   SUMO configured values; some
                                      unusually high

  Spatial validation                  TAPAS-derived comparison, not
                                      independent GPS

  Temporal validation                 First-bin agreement available; full
                                      12-bin profile pending

  Traffic lights                      Detector warnings observed for some
                                      actuated logic
  -----------------------------------------------------------------------

Pending or incomplete: 1. Independent validation against measured real
GPS has not been performed. 2. Full 12-bin temporal-profile validation
was pending. 3. Two exceptional high-speed transitions remained
unresolved (one ambiguous and one above all matched configured limits).
4. Exact final random seed/configuration snapshot should be recorded. 5.
The recorded 600-second custom run took 888.56 seconds wall-clock. 6.
SUMO reference simulation must not be presented as the custom Python
simulator.

## 14. Defensible project description

"Component 1 is a custom rule-based synthetic vehicle mobility simulator
using the TAPASCologne road network and trip-demand scenario as
reference inputs. It generates GPS-only vehicle observations and is
evaluated using structural, sampling, and TAPAS-derived spatial/demand
comparisons."

Do not claim that the generated GPS is measured real-world GPS, that the
custom simulator reproduces SUMO trajectories, that the simulator is
fully calibrated to real traffic, or that all configured SUMO speed
limits are legal limits.
