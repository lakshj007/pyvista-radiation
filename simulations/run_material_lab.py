"""Run eight real openEMS material cases; preserve the original wall experiment."""

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pyvista_radiation.materials import material_lab_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--refine", action="store_true", help="also run 8 mm air/concrete sensitivity pair")
    parser.add_argument("--work", type=Path, help="existing work directory, resume completed cases")
    args = parser.parse_args()
    image = "pyvista-radiation-solver"
    if args.build:
        subprocess.run(["docker", "build", "-t", image, "-f", "simulations/Dockerfile", "."], cwd=ROOT, check=True)
    work = (ROOT / args.work if args.work else ROOT / "simulations/work" /
            datetime.now(timezone.utc).strftime("material_lab_%Y%m%dT%H%M%SZ"))
    work.mkdir(parents=True, exist_ok=args.work is not None)
    relative = work.relative_to(ROOT)
    config = material_lab_config()
    manifest = work / "recipe.json"
    if manifest.exists() and json.loads(manifest.read_text()) != config:
        raise ValueError("saved recipe differs; start a new run")
    manifest.write_text(json.dumps(config, indent=2) + "\n")

    def run(case, step):
        label = f"{case}_{step}mm"
        log = work / f"{label}.log"
        if log.exists() and "THROUGH_WALL_FINISHED" in log.read_text():
            print(f"Reusing {label}", flush=True)
            return
        print(f"Running {label}; {log}", flush=True)
        with log.open("w") as stream:
            subprocess.run(["docker", "run", "--rm", "-v", f"{ROOT}:/work",
                            "-e", f"MATERIAL_LAB_CONFIG=/work/{relative}/recipe.json",
                            "-e", f"MATERIAL_LAB_CASE={case}", "-e", f"MATERIAL_LAB_STEP_MM={step}",
                            "-e", f"MATERIAL_LAB_OUTPUT=/work/{relative}/{label}", image,
                            "octave", "--no-gui", "--quiet", "simulations/material_lab.m"],
                           stdout=stream, stderr=subprocess.STDOUT, check=True)
        print(f"Finished {label}", flush=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda case: run(case["key"], 10), config["cases"]))
    if args.refine:
        # Larger meshes run sequentially to keep memory usage bounded.
        for key in ("air", "concrete"):
            run(key, 8)
    subprocess.run(["docker", "run", "--rm", "-v", f"{ROOT}:/work", image, "python3",
                    "simulations/export_material_lab.py", f"/work/{relative}"], check=True)
    print("Ready: python examples/through_wall.py --materials --browser", flush=True)


if __name__ == "__main__":
    main()
