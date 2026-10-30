"""Export real Cartesian planes and time samples from the two-floor solver."""

import gzip
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import h5py
import numpy as np
from export_through_wall import run_evidence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pyvista_radiation.house_fields import CartesianPlane, HouseFields, save_house_fields


def frequency_plane(path, definition, incident):
    axes = definition["axes"]
    with h5py.File(path) as f:
        coordinates = [f[f"Mesh/{a}"][:].ravel() for a in "xyz"]
        fixed = definition["fixed_axis"]
        if len(coordinates[fixed]) != 1 or not np.isclose(coordinates[fixed][0], definition["fixed_m"], atol=1e-6):
            raise ValueError("recorded plane location differs from recipe")
        real = f["FieldData/FD/f0_real"][:].astype(float)
        imaginary = f["FieldData/FD/f0_imag"][:].astype(float)
        field = real + 1j * imaginary
        if axes == [0, 2]:
            e = np.moveaxis(field[:, :, 0, :], 0, -1)
        elif axes == [0, 1]:
            e = np.moveaxis(field[:, 0, :, :], 0, -1)
        else:
            raise ValueError("unsupported house recording plane")
        frequency = float(np.asarray(f["FieldData/FD/f0_real"].attrs["frequency"]).item())
        return coordinates[axes[0]], coordinates[axes[1]], e / incident, frequency


def pulse_plane(path):
    with h5py.File(path) as f:
        u, v = f["Mesh/x"][:], f["Mesh/z"][:]
        if len(f["Mesh/y"]) != 1 or not np.isclose(f["Mesh/y"][0], 0):
            raise ValueError("pulse recording must be the vertical y=0 cut")
        group = f["FieldData/TD"]
        keys = sorted(group, key=int)
        times = np.array([float(np.asarray(group[k].attrs["time"]).item()) for k in keys])
        # Keep the exact float32 recorded Ey values and timestamps, with no
        # temporal interpolation, spectral reconstruction or rescaling.
        ey = np.stack([group[k][1, :, 0, :] for k in keys])
    return u, v, times, ey


def main():
    work = Path(sys.argv[1])
    recipe = json.loads((work / "recipe.json").read_text())
    names = tuple(case["key"] for case in recipe["cases"])
    planes, times, pulses, evidence = {}, {}, {}, {}
    for i, case in enumerate(names):
        directory = work / f"{case}_25mm"
        evidence[case] = run_evidence(work / f"{case}_25mm.log")
        p = np.loadtxt(directory / "port.csv", delimiter=",")
        incident = complex(p[1], p[2])
        if abs(incident) < 1e-20:
            raise ValueError("incident port spectrum is too small")
        evidence[case]["incident_voltage_spectrum_v_seconds"] = [incident.real, incident.imag]
        for definition in recipe["slices"]:
            key = definition["key"]
            u, v, e, frequency = frequency_plane(directory / f"{key}.h5", definition, incident)
            if frequency != recipe["frequency_hz"]:
                raise ValueError("frequency differs from recipe")
            if i == 0:
                planes[key] = dict(u=u, v=v, fields=[], definition=definition)
            np.testing.assert_array_equal(u, planes[key]["u"])
            np.testing.assert_array_equal(v, planes[key]["v"])
            planes[key]["fields"].append(e)
        pu, pv, time, ey = pulse_plane(directory / "pulse.h5")
        if i == 0:
            pulse_axes = pu, pv
        else:
            np.testing.assert_array_equal(pu, pulse_axes[0])
            np.testing.assert_array_equal(pv, pulse_axes[1])
        times[case], pulses[case] = time, ey
    source = np.array(recipe["source_xyz_m"])
    baseline = names.index("air")
    references = []
    final_planes = {}
    for key, p in planes.items():
        d = p["definition"]
        final_planes[key] = CartesianPlane(p["u"], p["v"], tuple(d["axes"]), d["fixed_m"], np.array(p["fields"]))
        uu, vv = np.meshgrid(p["u"], p["v"])
        xyz = [np.full_like(uu, d["fixed_m"]) for _ in range(3)]
        xyz[d["axes"][0]], xyz[d["axes"][1]] = uu, vv
        distance = np.linalg.norm(np.stack(xyz, axis=-1) - source, axis=-1)
        references.append(np.linalg.norm(p["fields"][baseline], axis=-1)[distance >= .2].max())
    field_reference = float(max(references))
    uu, vv = np.meshgrid(*pulse_axes)
    away = np.hypot(uu - source[0], vv - source[2]) >= .2
    pulse_reference = float(abs(pulses["air"][:, away]).max())
    if min(field_reference, pulse_reference) <= 0:
        raise ValueError("zero reference field")
    probes = []
    vertical = final_planes["vertical"]
    for label, point in zip(recipe["receiver_names"], recipe["receiver_xyz_m"]):
        ix, iz = np.argmin(abs(vertical.u_m - point[0])), np.argmin(abs(vertical.v_m - point[2]))
        magnitude = np.linalg.norm(vertical.electric_field[:, iz, ix], axis=-1)
        pu, pz = np.argmin(abs(pulse_axes[0] - point[0])), np.argmin(abs(pulse_axes[1] - point[2]))
        traces = {case: dict(peak_abs_ey_v_per_m=float(abs(pulses[case][:, pz, pu]).max()),
                             peak_time_s=float(times[case][np.argmax(abs(pulses[case][:, pz, pu]))]))
                  for case in names}
        probes.append(dict(name=label, xyz_m=point, field_v_per_m=magnitude.tolist(),
                           change_vs_air_db=(20 * np.log10(magnitude / magnitude[baseline])).tolist(),
                           pulse=traces))
    raw = ROOT / "data/house/raw"
    raw.mkdir(parents=True, exist_ok=True)
    uncompressed = {}
    for case in names:
        label = case + "_25mm"
        directory = work / label
        for name in ("vertical.h5", "downstairs.h5", "upstairs.h5", "pulse.h5"):
            original = directory / name
            key = f"{label}_{name}.gz"
            uncompressed[key] = hashlib.sha256(original.read_bytes()).hexdigest()
            # Lossless transport compression of the original HDF5, not rewritten
            # or quantized data. Original-byte hashes are retained independently.
            with original.open("rb") as src, (raw / key).open("wb") as target:
                with gzip.GzipFile(filename="", mode="wb", fileobj=target, mtime=0) as compressed:
                    shutil.copyfileobj(src, compressed)
        for name in ("geometry.xml", "et", "port.csv"):
            shutil.copy2(directory / name, raw / f"{label}_{name}")
        shutil.copy2(work / f"{label}.log", raw / f"{label}.log")
    meta = dict(
        title=recipe["title"], frequency_hz=recipe["frequency_hz"], recipe=recipe,
        provenance="Actual openEMS 3D FDTD two-level house; FD planes and directly recorded TD fields",
        solver_version=subprocess.check_output(["dpkg-query", "-W", "-f=${Version}", "openems"], text=True),
        source_normalization="FD electric phasors divided by the complex incident-voltage spectrum; V/m for a 1 V incident feed wave at 500 MHz, not radiated-power normalization.",
        pulse_normalization="Unchanged recorded Ey(t) in V/m for the common unit Gaussian lumped-port drive; no division by a single-frequency spectrum. No temporal interpolation, padding or phase reconstruction.",
        field_reference_v_per_m=field_reference, pulse_reference_v_per_m=pulse_reference,
        reference_description="Shared air reference outside a 0.2 m source radius; FD and TD use separate physical normalizations and references.",
        receivers=probes, run_evidence=evidence,
        time_recording_description="Vertical y=0 plane only, spatial step 50 mm, global OverSampling=2; recording stops at 55 ns or earlier solver termination. Per-case timestamps are retained.",
        limitations=recipe["assumptions"] + " Only recorded slices are available. The 25 mm grid has not undergone a house-specific mesh convergence study; energy decay is not convergence validation. Ey is tangential to the inter-floor slab; normal field components at dielectric interfaces are affected by node interpolation. No claim of deployment or hardware accuracy.",
        generator_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                          (ROOT / "simulations/two_floor_house.m", Path(__file__), ROOT / "src/pyvista_radiation/house.py")},
        raw_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(raw.iterdir())},
        raw_original_hdf5_sha256=uncompressed, license="CC0-1.0 numerical outputs",
    )
    data = HouseFields(names, final_planes, *pulse_axes, times, pulses, meta)
    save_house_fields(ROOT / "src/pyvista_radiation/data/two_floor_house.npz", data)
    (ROOT / "data/house/metadata.json").write_text(json.dumps(meta, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(receivers=probes, pulse_frames={n: len(t) for n, t in times.items()}), indent=2))


if __name__ == "__main__":
    main()
