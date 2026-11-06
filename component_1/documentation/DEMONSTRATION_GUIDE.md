# Component 1 --- Demonstration Guide

## Goal

Demonstrate the TAPASCologne road network, the SUMO reference
simulation, the custom Python simulator output, and the validation
evidence. Keep the SUMO simulation and custom Python simulator clearly
distinguished.

## Suggested 5--8 minute walkthrough

### 1. Show the input files

Show:

``` text
datasets/TAPASCologne/cologne.net.xml
datasets/TAPASCologne/cologne6to8.trips.xml
datasets/TAPASCologne/vtypes.add.xml
```

Explain: - `cologne.net.xml`: road network. - `cologne6to8.trips.xml`:
trip demand. - `vtypes.add.xml`: passenger-car type definition
(`pkw`). - The two-hour trip file contains 252,731 trips from 06:00 to
just before 08:00.

### 2. Show the road network

``` bash
sumo-gui -n datasets/TAPASCologne/cologne.net.xml
```

Explain that this opens the network only. No vehicles are expected yet.

### 3. Generate routes (skip if a verified route file is included)

``` bash
duarouter \
  -n datasets/TAPASCologne/cologne.net.xml \
  -r datasets/TAPASCologne/cologne6to8.trips.xml \
  -o datasets/TAPASCologne/cologne6to8.rou.xml
```

Verify:

``` bash
grep -c '<vehicle ' datasets/TAPASCologne/cologne6to8.rou.xml
```

Expected count from the recorded run: `252731`.

### 4. Show moving vehicles in SUMO-GUI

``` bash
sumo-gui \
  -n datasets/TAPASCologne/cologne.net.xml \
  -r datasets/TAPASCologne/cologne6to8.rou.xml \
  --begin 21600 \
  --end 28800 \
  --delay 50
```

During the demo: 1. Press Run/Play. 2. Zoom into a junction or busy
area. 3. Pause and resume to inspect positions. 4. Point out the
06:00--08:00 simulation period.

Say explicitly: "This is the SUMO simulation of TAPASCologne trip
demand. Our custom Python simulator is a separate implementation. It
uses the network and demand context but generates vehicle movement using
our own rules."

### 5. Show custom simulator outputs

Show these recorded files:

``` text
data/tapas_gps_600.0s.csv.gz
data/tapas_run_summary_600.0s.json
data/tapas_spawn_events_600.0s.json
```

The public GPS output schema has exactly four fields: - `device_id` -
`timestamp` - `latitude` - `longitude`

Internal fields such as speed, heading, edge ID, lane ID, destination,
and parking state are not exposed. Component 2 can derive movement
features from successive GPS points.

The known master validation entry point is:

``` bash
python scripts/run_full_validation.py
```

The recorded validation run passed 13/13 tests. Prefer showing
precomputed results during a short presentation: the recorded 600-second
custom run took 888.56 seconds of wall-clock time.

### 6. Present validation evidence

Recorded results: - 13/13 tests passed. - 600-second custom run:
4,023,356 GPS records and 13,853 observed devices. - Four-field GPS
schema; zero invalid records. - Zero duplicate `(device_id, timestamp)`
pairs. - Zero sampling intervals above 1.01 seconds. - Starting-position
grid comparison: Pearson 0.9576, Spearman 0.9526. - Broader spatial
occupancy comparison: Pearson 0.8161, Spearman 0.8273. - First
ten-minute demand-bin count agreement: 92.55%, after applying the 1.3
density multiplier.

Caveat: these are comparisons against TAPAS-derived reference data, not
independent validation against measured real-world GPS traces.

## Suggested explanation

"Component 1 is our synthetic vehicle-mobility data generator. We use
the TAPASCologne road network and trip-demand information as the
scenario reference. We first inspect the reference scenario in SUMO-GUI.
Separately, our rule-based Python simulator generates synthetic GPS
observations. Its external output is limited to device ID, timestamp,
latitude, and longitude. We evaluate output structure, sampling
intervals, and spatial/demand patterns against TAPAS-derived references.
We document the limitations, including the lack of independent real-GPS
validation and incomplete full-period temporal validation."

## Demonstration checklist

-   [ ] ZIP extracted and project opened from `implement/`.
-   [ ] Python environment activated.
-   [ ] SUMO, SUMO-GUI, and duarouter available.
-   [ ] TAPASCologne inputs present.
-   [ ] Route file present or generated and verified.
-   [ ] SUMO-GUI displays moving vehicles.
-   [ ] Custom GPS output and summary files present.
-   [ ] Validation evidence ready.
-   [ ] Difference between SUMO reference simulation and custom
    simulator explained.
-   [ ] Synthetic-data limitations stated honestly.

## Backup plan

Use precomputed GPS and validation outputs if a fresh custom simulation
is too slow. If allowed by dataset/project packaging rules, include the
verified generated route file in the ZIP; it was approximately 161 MB.
Test the extracted ZIP on a clean folder before the presentation.
