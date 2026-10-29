"""Archive the larger actual openEMS material comparison and its controls."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from export_through_wall import read_case, run_evidence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pyvista_radiation.nearfield import FieldPlaneData, save_field_plane


def main():
    work = Path(sys.argv[1])
    recipe = json.loads((work / "recipe.json").read_text())
    names = tuple(case["key"] for case in recipe["cases"])
    arrays, evidence = [], {}
    axes = None
    for name in names:
        x, y, freq, field, spectrum = read_case(work / f"{name}_10mm")
        if axes is not None:
            np.testing.assert_array_equal(x, axes[0])
            np.testing.assert_array_equal(y, axes[1])
        if freq != recipe["frequency_hz"]:
            raise ValueError("unexpected recording frequency")
        axes = x, y
        arrays.append(field)
        evidence[name] = run_evidence(work / f"{name}_10mm.log")
        evidence[name]["incident_voltage_spectrum_v_seconds"] = [spectrum.real, spectrum.imag]
    fields = np.array(arrays)
    xx, yy = np.meshgrid(*axes)
    source = recipe["source_xyz_m"]
    mask = np.hypot(xx - source[0], yy - source[1]) >= 0.08
    reference = float(np.linalg.norm(fields[0], axis=-1)[mask].max())
    probes = []
    for label, xyz in zip(recipe["receiver_names"], recipe["receiver_xyz_m"]):
        ix, iy = int(np.argmin(abs(x - xyz[0]))), int(np.argmin(abs(y - xyz[1])))
        e = np.linalg.norm(fields[:, iy, ix], axis=-1)
        probes.append(dict(name=label, xyz_m=[float(x[ix]), float(y[iy]), 0],
                           field_v_per_m=e.tolist(), change_vs_air_db=(20 * np.log10(e / e[0])).tolist()))
    sensitivity = dict(performed=False)
    if (work / "concrete_8mm/electric.h5").exists():
        fine = [read_case(work / f"{name}_8mm") for name in ("air", "concrete")]
        checks = []
        for probe in probes:
            values = []
            for fx, fy, _, e, _ in fine:
                ix, iy = np.argmin(abs(fx - probe["xyz_m"][0])), np.argmin(abs(fy - probe["xyz_m"][1]))
                values.append(np.linalg.norm(e[iy, ix]))
            change = float(20 * np.log10(values[1] / values[0]))
            checks.append(dict(receiver=probe["name"], fine_change_db=change,
                               difference_db=change - probe["change_vs_air_db"][names.index("concrete")]))
        for name in ("air", "concrete"):
            evidence[name + "_8mm"] = run_evidence(work / f"{name}_8mm.log")
        sensitivity = dict(performed=True, material="concrete", coarse_max_cell_m=0.01,
                           fine_requested_max_cell_m=0.008, receiver_checks=checks,
                           interpretation="Two-grid air/concrete sensitivity only; other materials have not been refined. Not full convergence or measurement validation.")
    raw = ROOT / "data/material_lab/raw"
    raw.mkdir(parents=True, exist_ok=True)
    # Archive only checked, accepted runs; stale or failed directories cannot leak in.
    labels = [f"{name}_10mm" for name in names]
    if sensitivity["performed"]:
        labels += ["air_8mm", "concrete_8mm"]
    for label in labels:
        for file in ("electric.h5", "geometry.xml", "et", "port.csv"):
            shutil.copy2(work / label / file, raw / f"{label}_{file}")
        shutil.copy2(work / f"{label}.log", raw / f"{label}.log")
    meta = dict(
        title=recipe["title"], experiment="material_lab", provenance="Actual openEMS full-wave FDTD material comparison",
        source_normalization="Complex E-field divided by the complex incident-voltage spectrum from calcPort; V/m for a 1 V incident wave at the 50-ohm dipole feed, not radiated-power normalization.",
        solver_version=subprocess.check_output(["dpkg-query", "-W", "-f=${Version}", "openems"], text=True),
        domain_bounds_m=recipe["domain_bounds_m"], wall_bounds_m=recipe["wall_bounds_m"],
        source_xyz_m=source, source_length_m=recipe["source_length_m"],
        antenna="120 mm PEC fat dipole, 20 mm square arms and gap, 50-ohm lumped feed",
        case_definitions=recipe["cases"], receivers=probes, run_evidence=evidence,
        material_reference=recipe["material_reference"],
        material_assumptions="P.2040-4 Table 3 class examples evaluated at 1 GHz, held constant over the pulse band; no broadband Debye/Lorentz dispersion or measured-product validation. Equal 120 mm bulk slabs; layer and thin-sheet cases have different material volumes.",
        grid_spacing_m=0.01, end_criterion=recipe["end_criterion"], max_timesteps=recipe["max_timesteps"],
        boundaries="PML_8 on all six faces", display_reference_v_per_m=reference,
        display_reference="Peak air-case |E| outside an 80 mm source radius; one reference for all cases",
        sensitivity=sensitivity,
        limitations="Total field includes transmission, reflection and finite-edge diffraction. Receiver change versus air is not isolated material penetration loss or calibrated received dBm. A horizontal z=0 slice of a 3D simulation; not a complete room or city simulation.",
        generator_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                          (ROOT / "simulations/material_lab.m", Path(__file__),
                           ROOT / "src/pyvista_radiation/materials.py")},
        raw_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(raw.iterdir())},
        license="CC0-1.0 numerical outputs",
    )
    data = FieldPlaneData(x, y, 0, freq, fields, names, meta)
    save_field_plane(ROOT / "src/pyvista_radiation/data/material_lab.npz", data)
    (ROOT / "data/material_lab/metadata.json").write_text(json.dumps(meta, indent=2, allow_nan=False) + "\n")
    (ROOT / "data/material_lab/recipe.json").write_text(json.dumps(recipe, indent=2) + "\n")
    print(json.dumps(dict(receivers=probes, sensitivity=sensitivity), indent=2))


if __name__ == "__main__":
    main()
