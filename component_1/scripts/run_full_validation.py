
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

DURATION = "600"

AUDITS = [
    "gps_quality_audit.py",
    "spatial_coverage_audit.py",
    "compare_tapas_origins.py",
    "spatial_distribution_metrics.py",
    "compare_starting_distribution.py",
    "compare_spawn_temporal.py",
]


def run_command(name, command):
    print(f"\n[STARTED] {name}")

    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True
    )

    return name, result.returncode, result.stdout, result.stderr


def main():
    log_dir = ROOT / "data" / "validation_600s"
    log_dir.mkdir(parents=True, exist_ok=True)

    # STEP 1: Tests
    print("\n========== STEP 1: PYTEST ==========")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-v"],
        cwd=ROOT
    )

    if result.returncode != 0:
        print("Tests failed. Stopping validation.")
        sys.exit(result.returncode)

    # STEP 2: Fresh simulation
    print("\n========== STEP 2: FRESH TAPAS SIMULATION ==========")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "run_tapas_simulation.py"),
            "--duration", DURATION,
            "--seed", "7",
            "--density", "1.3",
            "--dataset-scale", "1.0",
        ],
        cwd=ROOT
    )

    if result.returncode != 0:
        print("Simulation failed. Audits will not run.")
        sys.exit(result.returncode)

    # STEP 3: Run independent audits concurrently
    print("\n========== STEP 3: PARALLEL VALIDATION ==========")

    for script in AUDITS:
        if not (SCRIPTS / script).exists():
            print(f"Missing audit script: {script}")
            sys.exit(1)

    results = []

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(
                run_command,
                script,
                [sys.executable, str(SCRIPTS / script)]
            ): script
            for script in AUDITS
        }

        for future in as_completed(futures):
            results.append(future.result())

    # STEP 4: Save each audit's output
    print("\n========== STEP 4: RESULTS ==========")

    failures = []

    for name, code, stdout, stderr in sorted(results):
        log_file = log_dir / f"{Path(name).stem}.txt"

        log_file.write_text(
            stdout + ("\nERRORS:\n" + stderr if stderr else ""),
            encoding="utf-8"
        )

        print(f"\n--- {name} ---")
        print(stdout)

        if code != 0:
            failures.append(name)
            print("FAILED:", stderr)

    print("\n========== VALIDATION COMPLETE ==========")
    print("Results folder:", log_dir)

    if failures:
        print("Failed audits:", ", ".join(failures))
        sys.exit(1)

    print("All tests and audits completed successfully.")


if __name__ == "__main__":
    main()
