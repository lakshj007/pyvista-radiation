"""Create a small, native VTK review dataset from archived openEMS samples."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pyvista as pv

from pyvista_radiation import load_house

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "examples/house_showcase/data"


def main():
    data = load_house()
    recipe = data.metadata["recipe"]
    x, z = np.meshgrid(data.pulse_u_m[::2], data.pulse_v_m[::2])
    pulse = pv.StructuredGrid(x, np.zeros_like(x), z)
    sampled = data.pulse_ey["open"][:, ::2, ::2]
    pulse["Ey (V/m)"] = sampled.reshape(len(sampled), -1, order="F").T
    pulse.field_data["Time (s)"] = data.time_s["open"]
    pulse.field_data["Air pulse reference (V/m)"] = [data.metadata["pulse_reference_v_per_m"]]
    pulse.field_data["Coordinate unit"] = ["m"]
    pulse.field_data["Field unit"] = ["V/m"]
    pulse.field_data["Time unit"] = ["s"]
    pulse.field_data["Frequency (Hz)"] = [recipe["frequency_hz"]]
    pulse.field_data["Default frame"] = [int(np.argmin(abs(data.time_s["open"] - 24e-9)))]
    pulse.field_data["Provenance JSON"] = [json.dumps(data.metadata, allow_nan=False)]
    walls = []
    for box in recipe["cases"][0]["boxes"]:
        bounds = np.array(box["bounds_m"]).reshape(3, 2)
        cell = pv.ImageData(dimensions=(2, 2, 2), origin=bounds[:, 0],
                            spacing=np.diff(bounds, axis=1).ravel())
        cell.cell_data["Material"] = [int(box["material"] == "timber")]
        walls.append(cell)
    building = pv.MultiBlock(walls).combine(merge_points=False)
    building.field_data["Material names"] = ["Assumed partition", "Wood-class slab"]
    markers = pv.PolyData(np.array([recipe["source_xyz_m"], *recipe["receiver_xyz_m"]], dtype=float))
    markers["Label"] = ["TX", "A", "B", "C"]
    scene = pv.MultiBlock(dict(pulse=pulse, building=building, markers=markers))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    scene.save(OUTPUT / "house_pulse.vtm")
    original = ROOT / "src/pyvista_radiation/data/two_floor_house.npz"
    meta = dict(
        title="Recorded openEMS pulse through a two-floor house", case="open",
        license="CC0-1.0", source_archive="src/pyvista_radiation/data/two_floor_house.npz",
        source_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
        source_raw_hdf5_sha256=data.metadata["raw_original_hdf5_sha256"]["open_25mm_pulse.h5.gz"],
        exporter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        derivation="Every second x and z sample of the recorded vertical Ey cut. All 143 original timestamps retained, with unchanged float32 fields. No temporal thinning, interpolation, quantization or recalculation.",
        field_order="point,time; point ordering is StructuredGrid/Fortran order",
        original_shape_time_z_x=list(data.pulse_ey["open"].shape),
        display_shape_time_z_x=list(sampled.shape),
        coordinate_unit="m", field_unit="V/m", time_unit="s",
        normalization=data.metadata["pulse_normalization"],
        reference_description=data.metadata["reference_description"],
        limitations=data.metadata["limitations"],
        files_sha256={str(p.relative_to(OUTPUT)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted(OUTPUT.rglob("house_pulse*")) if p.is_file()},
    )
    (OUTPUT / "manifest.json").write_text(json.dumps(meta, indent=2, allow_nan=False) + "\n")
    print(f"{len(sampled)} frames, {pulse.n_points} points; "
          f"{sum(p.stat().st_size for p in OUTPUT.rglob('*') if p.is_file()):,} bytes")


if __name__ == "__main__":
    main()
