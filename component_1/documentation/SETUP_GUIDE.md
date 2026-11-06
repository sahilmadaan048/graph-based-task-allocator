# Component 1 --- Setup Guide

## Purpose

Component 1 is a custom rule-based vehicle mobility simulator using the
TAPASCologne road network and trip-demand data. It generates synthetic
GPS observations. It does not replay SUMO vehicle trajectories.

## Tested environment

-   Windows 10
-   Python 3.13.5
-   Eclipse SUMO 1.28.0
-   Git Bash / MINGW64
-   Project virtual environment: `component_1/.venv`

The ZIP should include the project's dependency file, if one exists. Do
not rely on copying a virtual environment from one Windows machine to
another.

## Expected paths

Run commands from the `implement/` directory.

``` text
implement/
├── component_1/.venv/
├── datasets/TAPASCologne/
│   ├── cologne.net.xml
│   ├── cologne6to8.trips.xml
│   └── vtypes.add.xml
├── data/
├── scripts/run_full_validation.py
└── ...
```

## Activate Python environment

``` bash
cd "/d/7th semester/gnn final year project/implement"
source component_1/.venv/Scripts/activate
```

If the environment is not included, create a fresh one and install from
the dependency file included in the project.

## Check SUMO installation

``` bash
which sumo
which sumo-gui
which duarouter
```

The tested machine located SUMO-GUI at:

``` text
/c/Program Files (x86)/SUMO/bin/sumo-gui
```

If necessary, invoke it directly:

``` bash
"/c/Program Files (x86)/SUMO/bin/sumo-gui.exe" --version
```

## Check TAPASCologne inputs

``` bash
ls -lh datasets/TAPASCologne/cologne.net.xml
ls -lh datasets/TAPASCologne/cologne6to8.trips.xml
ls -lh datasets/TAPASCologne/vtypes.add.xml
```

The inspected two-hour trip file contains 252,731 passenger-car trips,
departing from 06:00 through 07:59:59 (simulation seconds 21600--28799).

## Run Component 1 validation

``` bash
python scripts/run_full_validation.py
```

The recorded validation run passed 13/13 tests. The recorded 600-second
custom simulation took 888.56 seconds of wall-clock time, so long runs
may be expensive. Check the script and its configuration before starting
a new long run.

## Open the road network only

``` bash
sumo-gui -n datasets/TAPASCologne/cologne.net.xml
```

This displays roads and junctions but no moving vehicles. That is
expected: the network file does not contain trip routes.

## Generate SUMO routes from TAPAS trips

``` bash
duarouter \
  -n datasets/TAPASCologne/cologne.net.xml \
  -r datasets/TAPASCologne/cologne6to8.trips.xml \
  -o datasets/TAPASCologne/cologne6to8.rou.xml
```

In the recorded successful run this generated a route file containing
252,731 `<vehicle>` entries (about 161 MB).

Verify:

``` bash
grep -c '<vehicle ' datasets/TAPASCologne/cologne6to8.rou.xml
head -n 10 datasets/TAPASCologne/cologne6to8.rou.xml
tail -n 10 datasets/TAPASCologne/cologne6to8.rou.xml
```

Expected vehicle count: `252731`; the file should close with
`</routes>`.

**Vehicle-type note:** The successful route-generation command did not
pass `vtypes.add.xml` using `-a`. An earlier attempt to load it that way
produced a duplicate `pkw` type error. The resulting route file was then
successfully loaded by SUMO-GUI without separately loading
`vtypes.add.xml`.

## Run the full two-hour SUMO-GUI simulation

``` bash
sumo-gui \
  -n datasets/TAPASCologne/cologne.net.xml \
  -r datasets/TAPASCologne/cologne6to8.rou.xml \
  --begin 21600 \
  --end 28800 \
  --delay 50
```

This visualizes the SUMO TAPAS reference scenario from 06:00 to 08:00.
`--delay 50` changes GUI animation pacing, not the simulated time
interval. This is not the custom Python simulator.

## Troubleshooting

### Roads show, but no vehicles

You loaded only the network. Generate routes and launch SUMO-GUI with
both `-n` and `-r`.

### Duplicate vehicle type `pkw`

Do not load the same vehicle type definition twice. Follow the tested
route-generation and GUI commands above.

### Unknown vehicle type `pkw`

Check the exact command and inputs. Do not delete or edit original TAPAS
files. The recorded successful workflow generated routes without passing
the additional file and then opened the route file without separately
loading it.

### Simulation starts and ends immediately at time 0

Check that the GUI command includes the `.rou.xml` file and that it
contains vehicle entries.

### Actuated traffic-light detector warnings

Warnings about actuated phases or links without controlling detectors
were observed. Document these as scenario limitations; do not claim
complete detector-driven adaptive signal control.

## Reproducibility and data handling

-   Preserve original inputs in `datasets/TAPASCologne/`.
-   Keep generated files in their documented relative locations.
-   Record the random seed and configuration for every new custom run.
-   Generated GPS is synthetic, not measured GPS.
-   The output timestamp date `2026-01-01` is a synthetic reference
    date, not TAPASCologne's collection date.
