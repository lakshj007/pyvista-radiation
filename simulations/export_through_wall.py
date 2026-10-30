"""Archive actual legacy openEMS field dumps, source calibration and run evidence."""

import hashlib
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pyvista_radiation.nearfield import FieldPlaneData, save_field_plane


def read_case(directory):
    """Legacy openEMS FD storage: (component,z,y,x); explicit z=0 plane."""
    with h5py.File(directory / "electric.h5") as f:
        x, y, z = (np.asarray(f[f"Mesh/{axis}"]).ravel() for axis in "xyz")
        if len(z) != 1 or not np.isclose(z[0], 0, atol=1e-10):
            raise ValueError("expected a single horizontal z=0 field plane")
        group = f["FieldData/FD"]
        field = group["f0_real"][:] + 1j * group["f0_imag"][:]
        frequency = float(np.asarray(group["f0_real"].attrs["frequency"]).item())
        if field.shape != (3, 1, len(y), len(x)) or not np.isfinite(field).all():
            raise ValueError(f"unexpected legacy field layout: {field.shape}")
    port = np.loadtxt(directory / "port.csv", delimiter=",")
    spectrum = complex(port[1], port[2])
    if abs(spectrum) < 1e-20:
        raise ValueError("source spectrum too small for calibration")
    # Mesh axes in openEMS HDF5 dumps are already physical metres.
    return x, y, frequency, np.moveaxis(field[:, 0], 0, -1) / spectrum, spectrum


def run_evidence(log):
    text = log.read_text()
    if "THROUGH_WALL_FINISHED" not in text or "Max. number of timesteps was reached" in text:
        raise ValueError(f"incomplete solver log: {log}")
    energy = re.findall(r"Energy:.*?\(\s*([+-]?[\d.]+)dB\)", text)
    if not energy or float(energy[-1]) > -60:
        raise ValueError(f"field decay target was not reached: {log}")
    grid = ET.parse(log.with_suffix("") / "geometry.xml").find(".//RectilinearGrid")
    delta = float(grid.attrib["DeltaUnit"])
    axes = [np.fromstring(grid.find(axis + "Lines").text, sep=",") * delta for axis in "XYZ"]
    sizes = np.concatenate([np.diff(axis) for axis in axes])
    return {"last_reported_energy_db": float(energy[-1]),
            "mesh_nodes_xyz": [len(axis) for axis in axes],
            "min_cell_m": float(sizes.min()), "max_cell_m": float(sizes.max()),
            "mesh_warnings": [line for line in text.splitlines() if "ratio" in line],
            "termination": [line for line in text.splitlines()
                            if any(word in line.lower() for word in
                                   ("timesteps", "energy", "runtime", "finished"))][-8:]}


def main():
    work = Path(sys.argv[1])
    raw = ROOT / "data/through_wall/raw"
    raw.mkdir(parents=True, exist_ok=True)
    names = ("air", "dielectric", "metal")
    fields, evidence = [], {}
    axes = None
    for name in names:
        directory = work / f"{name}_5mm"
        x, y, frequency, field, spectrum = read_case(directory)
        if axes is not None:
            np.testing.assert_allclose(x, axes[0])
            np.testing.assert_allclose(y, axes[1])
        axes = (x, y)
        fields.append(field)
        evidence[name] = run_evidence(work / f"{name}_5mm.log")
        evidence[name]["incident_voltage_spectrum_v_seconds"] = [spectrum.real, spectrum.imag]
    fields = np.array(fields)
    xx, yy = np.meshgrid(*axes)
    outside_source = np.hypot(xx + 0.22, yy) >= 0.03
    reference = float(np.linalg.norm(fields[0], axis=-1)[outside_source].max())
    probes = []
    for label, px in (("Before wall", -0.12), ("Behind wall", 0.2)):
        ix, iy = int(np.argmin(abs(x - px))), int(np.argmin(abs(y)))
        amplitude = np.linalg.norm(fields[:, iy, ix], axis=-1)
        probes.append(dict(name=label, xyz_m=[float(x[ix]), float(y[iy]), 0],
                           field_v_per_m=amplitude.tolist(),
                           change_vs_air_db=(20 * np.log10(amplitude / amplitude[0])).tolist()))
    sensitivity = {"performed": False}
    if (work / "air_4mm").is_dir() and (work / "dielectric_4mm").is_dir():
        fine = [read_case(work / f"{name}_4mm") for name in names[:2]]
        checks = []
        for probe in probes:
            values = []
            for fx, fy, _, e, _ in fine:
                ix, iy = np.argmin(abs(fx - probe["xyz_m"][0])), np.argmin(abs(fy))
                values.append(np.linalg.norm(e[iy, ix]))
            ratio_db = float(20 * np.log10(values[1] / values[0]))
            checks.append(dict(receiver=probe["name"], fine_change_db=ratio_db,
                               difference_db=ratio_db - probe["change_vs_air_db"][1]))
        sensitivity = dict(performed=True, coarse_spacing_m=0.005, fine_spacing_m=0.004,
                           receiver_checks=checks, interpretation="Two-grid sensitivity with locally refined antenna edges; not full convergence or measurement validation")
        for name in names[:2]:
            evidence[name + "_4mm"] = run_evidence(work / f"{name}_4mm.log")
    meta = dict(
        provenance="Actual openEMS full-wave FDTD; independently authored small-wall example",
        solver_version=subprocess.check_output(["dpkg-query", "-W", "-f=${Version}", "openems"], text=True),
        source_normalization="Complex E-field divided by the complex incident-voltage spectrum from calcPort; V/m for a 1 V incident voltage wave at the 50-ohm dipole feed. Not normalized to radiated power or a commercial transmitter.",
        domain_bounds_m=[-0.4, 0.4, -0.3, 0.3, -0.2, 0.2],
        wall_bounds_m=[0, 0.08, -0.2, 0.2, -0.12, 0.12],
        material=dict(relative_permittivity=4, conductivity_s_per_m=0.03,
                      description="Illustrative lossy dielectric; not measured concrete"),
        source_xyz_m=[-0.22, 0, 0], source_length_m=0.05,
        antenna="50 mm PEC fat dipole, 10 mm square arms, 10 mm feed gap, 50-ohm lumped port",
        receivers=probes, grid_spacing_m=0.005, boundaries="PML_8 on all six faces",
        end_criterion=1e-6, max_timesteps=12000, run_evidence=evidence,
        display_reference_v_per_m=reference,
        display_reference="Peak air-case |E| on the saved plane at least 30 mm from the source",
        sensitivity=sensitivity,
        limitations="Finite wall: total field includes through-wall transmission, reflection and edge diffraction; receiver ratios do not isolate material penetration loss. A horizontal slice of a 3D simulation. Numerical dipole and assumed material, no calibrated received dBm, no city-scale or hardware validation.",
        generator_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                          (ROOT / "simulations/through_wall.m", Path(__file__))},
        license="CC0-1.0 numerical outputs",
    )
    for path in sorted(work.glob("*")):
        if path.is_dir():
            for name in ("electric.h5", "geometry.xml", "et", "port.csv"):
                shutil.copy2(path / name, raw / f"{path.name}_{name}")
        elif path.suffix == ".log":
            shutil.copy2(path, raw / path.name)
    meta["raw_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(raw.iterdir())}
    data = FieldPlaneData(x, y, 0, frequency, fields, names, meta)
    save_field_plane(ROOT / "src/pyvista_radiation/data/through_wall.npz", data)
    (ROOT / "data/through_wall/metadata.json").write_text(json.dumps(meta, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(receivers=probes, sensitivity=sensitivity), indent=2))


if __name__ == "__main__":
    main()
