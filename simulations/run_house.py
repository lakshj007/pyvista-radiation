"""Run a real openEMS two-level house and retain plane/pulse recordings."""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pyvista_radiation.house import house_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--work", type=Path, help="resume an existing matching recipe")
    args = parser.parse_args()
    image = "pyvista-radiation-solver"
    if args.build:
        subprocess.run(["docker", "build", "-t", image, "-f", "simulations/Dockerfile", "."], cwd=ROOT, check=True)
    work = ROOT / args.work if args.work else ROOT / "simulations/work" / datetime.now(timezone.utc).strftime("house_%Y%m%dT%H%M%SZ")
    work.mkdir(parents=True, exist_ok=args.work is not None)
    relative = work.relative_to(ROOT)
    recipe = house_config()
    saved = work / "recipe.json"
    if saved.exists() and json.loads(saved.read_text()) != recipe:
        raise ValueError("recipe differs; use a new work directory")
    saved.write_text(json.dumps(recipe, indent=2) + "\n")
    for case in recipe["cases"]:
        label = case["key"] + "_25mm"
        log = work / (label + ".log")
        if log.exists() and "THROUGH_WALL_FINISHED" in log.read_text():
            print("Reusing " + label, flush=True)
            continue
        print(f"Running {label}; {log}", flush=True)
        with log.open("w") as stream:
            subprocess.run(["docker", "run", "--rm", "-v", f"{ROOT}:/work",
                            "-e", f"HOUSE_CONFIG=/work/{relative}/recipe.json", "-e", f"HOUSE_CASE={case['key']}",
                            "-e", "HOUSE_STEP_MM=25", "-e", f"HOUSE_OUTPUT=/work/{relative}/{label}",
                            image, "octave", "--no-gui", "--quiet", "simulations/two_floor_house.m"],
                           stdout=stream, stderr=subprocess.STDOUT, check=True)
        print("Finished " + label, flush=True)
    subprocess.run(["docker", "run", "--rm", "-v", f"{ROOT}:/work", image, "python3",
                    "simulations/export_house.py", f"/work/{relative}"], check=True)
    print("Ready: python examples/two_floor_house.py --browser", flush=True)


if __name__ == "__main__":
    main()
