import asyncio
import gzip
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from pyvista_radiation import (
    CartesianPlane,
    house_slice_mesh,
    load_house,
    load_house_fields,
    save_house_fields,
)
from pyvista_radiation.house import house_config


@pytest.fixture(scope="module")
def house():
    return load_house()


def test_house_opening_and_receivers_are_air():
    recipe = house_config()
    cases = {c["key"]: c for c in recipe["cases"]}

    def contains(box, point):
        bounds = np.array(box["bounds_m"]).reshape(3, 2)
        return np.all((point >= bounds[:, 0]) & (point <= bounds[:, 1]))

    opening = np.array(recipe["stair_opening_bounds_m"]).reshape(3, 2).mean(axis=1)
    assert not any(contains(b, opening) for b in cases["open"]["boxes"])
    assert any(contains(b, opening) for b in cases["closed"]["boxes"])
    for case in cases.values():
        for point in [recipe["source_xyz_m"], *recipe["receiver_xyz_m"]]:
            assert not any(contains(b, point) for b in case["boxes"])
    assert not cases["air"]["boxes"]


def test_house_roundtrip_preserves_time_samples_and_variable_lengths(house, tmp_path):
    path = tmp_path / "house.npz"
    save_house_fields(path, house)
    loaded = load_house_fields(path)
    assert loaded.case_names == ("open", "closed", "air")
    assert len(loaded.time_s["air"]) < len(loaded.time_s["open"])
    for name in house.case_names:
        np.testing.assert_array_equal(loaded.time_s[name], house.time_s[name])
        np.testing.assert_array_equal(loaded.pulse_ey[name], house.pulse_ey[name])
        assert loaded.pulse_ey[name].dtype == np.float32
        assert not loaded.pulse_ey[name].flags.writeable
    for name in house.planes:
        np.testing.assert_array_equal(loaded.planes[name].electric_field,
                                      house.planes[name].electric_field)


def test_house_rejects_bad_time_shape_and_complex_pulse(house):
    times = dict(house.time_s, open=house.time_s["open"][::-1])
    with pytest.raises(ValueError, match="increasing"):
        replace(house, time_s=times)
    with pytest.raises(ValueError, match="shape"):
        replace(house, pulse_ey=dict(house.pulse_ey, open=house.pulse_ey["open"][:-1]))
    with pytest.raises(ValueError, match="real"):
        replace(house, pulse_ey=dict(house.pulse_ey, open=house.pulse_ey["open"].astype(complex)))
    with pytest.raises(ValueError, match="shape"):
        CartesianPlane([0, 1], [0, 1], (0, 2), 0, np.zeros((1, 2, 2, 2)))


def test_house_rejects_ambiguous_units(house, tmp_path):
    path = tmp_path / "wrong.npz"
    save_house_fields(path, house)
    with np.load(path) as z:
        arrays = dict(z)
    meta = json.loads(arrays["metadata_json"].item())
    meta["time_unit"] = "ns"
    np.savez(path, **dict(arrays, metadata_json=json.dumps(meta)))
    with pytest.raises(ValueError, match="units"):
        load_house_fields(path)


def test_mesh_keeps_global_axis_order_and_unclipped_values(house):
    pytest.importorskip("pyvista")
    pulse = house_slice_mesh(house, frame=55)
    assert np.all(pulse.points[:, 1] == 0)
    shape = (len(house.pulse_v_m), len(house.pulse_u_m))
    np.testing.assert_array_equal(pulse["Recorded Ey (V/m)"].reshape(shape, order="F"),
                                  house.pulse_ey["open"][55])
    assert pulse.field_data["Recorded time (s)"][0] == house.time_s["open"][55]
    for key, plane in house.planes.items():
        mesh = house_slice_mesh(house, plane=key, mode="magnitude_db")
        fixed = ({0, 1, 2} - set(plane.axes)).pop()
        assert np.all(mesh.points[:, fixed] == plane.fixed_m)
        reconstructed = mesh["Electric field real (V/m)"] + 1j * mesh["Electric field imaginary (V/m)"]
        np.testing.assert_array_equal(reconstructed.reshape(plane.electric_field[0].shape, order="F"),
                                      plane.electric_field[0])
    with pytest.raises(ValueError, match="vertical"):
        house_slice_mesh(house, plane="upstairs", mode="pulse")


def test_house_recordings_have_delayed_upstairs_peak_and_distinct_floor_response(house):
    assert house.metadata["frequency_hz"] == 500e6
    peaks = []
    for point in house.metadata["recipe"]["receiver_xyz_m"]:
        ix = np.argmin(abs(house.pulse_u_m - point[0]))
        iz = np.argmin(abs(house.pulse_v_m - point[2]))
        trace = house.pulse_ey["open"][:, iz, ix]
        peaks.append(house.time_s["open"][np.argmax(abs(trace))])
    assert peaks[1] - peaks[0] > 5e-9
    assert peaks[2] > peaks[1]
    assert np.all(house.pulse_ey["open"][0] == 0)
    assert not np.allclose(house.planes["upstairs"].electric_field[0],
                           house.planes["upstairs"].electric_field[1])
    assert all(e["last_reported_energy_db"] <= -60 for e in house.metadata["run_evidence"].values())
    assert "not undergone" in house.metadata["limitations"]


def test_house_raw_and_generator_evidence_integrity(house):
    root = Path(__file__).resolve().parents[1]
    for name, digest in house.metadata["raw_sha256"].items():
        raw = (root / "data/house/raw" / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        if name.endswith(".gz"):
            assert hashlib.sha256(gzip.decompress(raw)).hexdigest() == house.metadata["raw_original_hdf5_sha256"][name]
    for name, digest in house.metadata["generator_sha256"].items():
        path = root / ("src/pyvista_radiation" if name == "house.py" else "simulations") / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_house_viewer_changes_slices_without_replacing_actors(house):
    pytest.importorskip("pyvista")
    pytest.importorskip("trame")
    from pyvista_radiation.house_view import create_house_app

    server, viewer = create_house_app(house, server_name="test-house-fields")
    try:
        server.state.ready()
        identities = {k: id(a) for k, a in viewer.field_actors.items()}
        with server.state:
            server.state.house_frame = 130
            server.state.house_case = "air"
        assert server.state.house_frame == len(house.time_s["air"]) - 1
        assert "Recorded Ey" in server.state.house_scale
        with server.state:
            server.state.house_mode = "magnitude_db"
            server.state.house_plane = "upstairs"
            server.state.house_case = "closed"
        assert viewer.field_actors["upstairs"].GetVisibility()
        assert not viewer.field_actors["pulse"].GetVisibility()
        assert any(a.GetVisibility() for a, _ in viewer.case_actors["closed"])
        assert not any(a.GetVisibility() for a, _ in viewer.case_actors["open"])
        assert viewer.plotter.camera.position[2] > 3.2
        viewer.camera("house")
        camera = tuple(viewer.plotter.camera.position)
        with server.state:
            server.state.house_mode = "phase"
            server.state.house_phase = 180
        assert tuple(viewer.plotter.camera.position) == camera
        expected = house_slice_mesh(house, "closed", "upstairs", mode="phase", phase_deg=180)
        np.testing.assert_array_equal(viewer.meshes["upstairs"].active_scalars, expected.active_scalars)
        assert {k: id(a) for k, a in viewer.field_actors.items()} == identities
    finally:
        viewer.close()


def test_house_playback_can_pause_before_completion(house):
    pytest.importorskip("pyvista")
    pytest.importorskip("trame")
    from pyvista_radiation.house_view import create_house_app

    server, viewer = create_house_app(house, server_name="test-house-pause")
    server.state.ready()

    async def exercise():
        server.controller.house_play()
        await asyncio.sleep(.16)
        assert server.state.house_playing
        assert server.state.house_frame < len(house.time_s["open"]) - 1
        server.controller.house_play()
        await asyncio.sleep(.08)
        assert not server.state.house_playing
        frame = server.state.house_frame
        await asyncio.sleep(.10)
        assert server.state.house_frame == frame
        assert server._house_animation.done()

    try:
        asyncio.run(exercise())
    finally:
        viewer.close()
