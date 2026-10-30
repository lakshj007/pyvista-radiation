import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from pyvista_radiation import (
    FieldPlaneData,
    field_plane_mesh,
    load_field_plane,
    load_through_wall,
    save_field_plane,
)


def sample():
    x, y = np.array([0., 1., 2.]), np.array([-1., 1.])
    xx, yy = np.meshgrid(x, y)
    field = np.zeros((2, 2, 3, 3), complex)
    field[0, ..., 0] = xx + 1j * yy
    field[0, ..., 2] = 1 + 2j
    field[1] = 0.5 * field[0]
    return FieldPlaneData(x, y, 0.2, 2.4e9, field, ("air", "wall"),
                          {"source_normalization": "unit test source"})


def test_complex_plane_round_trip_and_source_units(tmp_path):
    data = sample()
    path = tmp_path / "plane.npz"
    save_field_plane(path, data)
    loaded = load_field_plane(path)
    np.testing.assert_array_equal(loaded.electric_field, data.electric_field)
    assert loaded.case_names == ("air", "wall")
    assert loaded.frequency_hz == data.frequency_hz and loaded.z_m == 0.2
    assert not loaded.electric_field.flags.writeable
    assert loaded.metadata["field_unit"] == "V/m"
    with np.load(path, allow_pickle=False) as z:
        arrays = dict(z)
    meta = json.loads(arrays["metadata_json"].item())
    meta["coordinate_unit"] = "mm"
    arrays["metadata_json"] = json.dumps(meta)
    np.savez(path, **arrays)
    with pytest.raises(ValueError, match="units"):
        load_field_plane(path)


def test_plane_rejects_bad_shape_order_and_unsupported_values():
    data = sample()
    with pytest.raises(ValueError, match="increasing"):
        FieldPlaneData(data.x_m[::-1], data.y_m, 0, 1e9, data.electric_field,
                       data.case_names, data.metadata)
    with pytest.raises(ValueError, match="real"):
        FieldPlaneData(data.x_m + 1j, data.y_m, 0, 1e9, data.electric_field,
                       data.case_names, data.metadata)
    with pytest.raises(ValueError, match="shaped"):
        FieldPlaneData(data.x_m, data.y_m, 0, 1e9, data.electric_field[..., 0],
                       data.case_names, data.metadata)
    with pytest.raises(ValueError, match="source_normalization"):
        FieldPlaneData(data.x_m, data.y_m, 0, 1e9, data.electric_field, data.case_names, {})


def test_mesh_preserves_vector_order_phase_and_shared_amplitude_reference(tmp_path):
    pv = pytest.importorskip("pyvista")
    data = sample()
    a = field_plane_mesh(data, "air", reference=10)
    b = field_plane_mesh(data, "wall", reference=10)
    for k, point in enumerate(a.points):
        ix, iy = np.flatnonzero(data.x_m == point[0])[0], np.flatnonzero(data.y_m == point[1])[0]
        np.testing.assert_array_equal(a["Electric field real (V/m)"][k], data.electric_field[0, iy, ix].real)
        np.testing.assert_array_equal(a["Electric field imaginary (V/m)"][k], data.electric_field[0, iy, ix].imag)
        assert point[2] == 0.2
    np.testing.assert_allclose(b.active_scalars - a.active_scalars, 20 * np.log10(0.5))
    at_zero = field_plane_mesh(data, mode="phase", phase_deg=0, reference=10)
    at_quarter = field_plane_mesh(data, mode="phase", phase_deg=90, reference=10)
    np.testing.assert_allclose(at_zero.active_scalars, 0.1)
    np.testing.assert_allclose(at_quarter.active_scalars, -0.2)
    a.save(tmp_path / "plane.vts")
    loaded = pv.read(tmp_path / "plane.vts")
    np.testing.assert_array_equal(loaded["Electric field imaginary (V/m)"], a["Electric field imaginary (V/m)"])


def test_actual_solver_sample_propagation_and_pec_control():
    data = load_through_wall()
    assert data.case_names == ("air", "dielectric", "metal")
    assert "openEMS" in data.metadata["provenance"]
    assert data.electric_field.shape[-1] == 3
    iy, ix = np.argmin(abs(data.y_m)), np.argmin(abs(data.x_m - 0.04))
    magnitude = np.linalg.norm(data.electric_field[:, iy, ix], axis=-1)
    assert magnitude[1] > 0.1  # field really exists inside the dielectric
    assert magnitude[2] < 1e-8  # inside a perfect conductor it is zero
    distance = data.x_m + 0.22
    far = (distance > 0.12) & (distance < 0.5)
    phase = np.unwrap(np.angle(data.electric_field[0, iy, far, 2]))
    slope = abs(np.polyfit(distance[far], phase, 1)[0])
    assert slope == pytest.approx(2 * np.pi * data.frequency_hz / 299792458, rel=0.02)
    behind = data.metadata["receivers"][1]
    assert behind["change_vs_air_db"][2] < -10
    for case in data.case_names:
        assert data.metadata["run_evidence"][case]["last_reported_energy_db"] <= -60
    sensitivity = data.metadata["sensitivity"]
    assert sensitivity["performed"]
    assert max(abs(item["difference_db"]) for item in sensitivity["receiver_checks"]) < 0.2


def test_archived_solver_evidence_matches_the_saved_sample():
    root = Path(__file__).resolve().parents[1]
    meta = load_through_wall().metadata
    for name, digest in meta["raw_sha256"].items():
        assert hashlib.sha256((root / "data/through_wall/raw" / name).read_bytes()).hexdigest() == digest
    for name, digest in meta["generator_sha256"].items():
        assert hashlib.sha256((root / "simulations" / name).read_bytes()).hexdigest() == digest


def test_wall_browser_uses_saved_fields_and_can_switch_controls():
    pytest.importorskip("pyvista")
    pytest.importorskip("trame")
    from pyvista_radiation.wall_view import create_wall_app

    server, viewer = create_wall_app(server_name="actual-wall-ui-test")
    try:
        assert viewer.mesh.n_points == len(viewer.data.x_m) * len(viewer.data.y_m)
        original = viewer.data.electric_field.copy()
        viewer.update("metal", "phase", 90)
        assert viewer.wall_actor.GetVisibility()
        mesh_id = id(viewer.mesh)
        viewer.update("air", "magnitude_db", 0)
        assert not viewer.wall_actor.GetVisibility()
        assert id(viewer.mesh) == mesh_id
        server.state.ready()
        with server.state:
            server.state.wall_case = "metal"
            server.state.wall_mode = "phase"
        assert server.state.wall_caption == "Metal wall (PEC)"
        assert viewer.actor.mapper.scalar_range == (-0.25, 0.25)
        np.testing.assert_array_equal(viewer.data.electric_field, original)
        assert "through" in server.state.trame__title.lower()
    finally:
        viewer.close()
