"""Run real openEMS wall controls in Docker, then export the small field sample."""

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="build the existing solver image first")
    parser.add_argument("--no-refinement", action="store_true", help="skip the 4 mm sensitivity pair")
    parser.add_argument("--refinement-work", type=Path,
                        help="add only the refinement pair to an existing run directory")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    image = "pyvista-radiation-solver"
    if args.build:
        subprocess.run(["docker", "build", "-t", image, "-f", "simulations/Dockerfile", "."],
                       cwd=root, check=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    work = args.refinement_work or Path("simulations/work") / f"through_wall_{stamp}"
    if work.is_absolute():
        work = work.relative_to(root)
    (root / work).mkdir(parents=True, exist_ok=args.refinement_work is not None)
    cases = [] if args.refinement_work else [("air", 5), ("dielectric", 5), ("metal", 5)]
    if args.refinement_work or not args.no_refinement:
        cases += [("air", 4), ("dielectric", 4)]
    for kind, step in cases:
        name = f"{kind}_{step}mm"
        log = root / work / f"{name}.log"
        print(f"Running openEMS: {name}; log: {log}", flush=True)
        with log.open("w") as stream:
            subprocess.run(
                ["docker", "run", "--rm", "-v", f"{root}:/work",
                 "-e", f"WALL_CASE={kind}", "-e", f"WALL_GRID_MM={step}",
                 "-e", f"WALL_OUTPUT=/work/{work}/{name}", image,
                 "octave", "--no-gui", "--quiet", "simulations/through_wall.m"],
                stdout=stream, stderr=subprocess.STDOUT, check=True,
            )
        if f"THROUGH_WALL_FINISHED {kind}" not in log.read_text():
            raise RuntimeError(f"Solver did not finish: {log}")
    print("Exporting saved solver fields", flush=True)
    subprocess.run(
        ["docker", "run", "--rm", "-v", f"{root}:/work", image, "python3",
         "simulations/export_through_wall.py", f"/work/{work}"], check=True,
    )
    print("Ready: python examples/through_wall.py --browser", flush=True)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(f"Solver command failed ({exc.returncode}). Inspect the named run log.")
