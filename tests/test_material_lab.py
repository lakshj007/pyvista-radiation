import hashlib
from pathlib import Path

import numpy as np
import pytest

from pyvista_radiation import field_plane_mesh, load_material_lab, load_through_wall
from pyvista_radiation.materials import material_lab_config


def test_larger_recipe_and_documented_material_parameters():
    recipe = material_lab_config()
    original = load_through_wall().metadata["domain_bounds_m"]
    new_volume = np.prod(np.diff(np.reshape(recipe["domain_bounds_m"], (3, 2)), axis=1))
    old_volume = np.prod(np.diff(np.reshape(original, (3, 2)), axis=1))
    assert new_volume / old_volume == pytest.approx(20)
    assert recipe["frequency_hz"] == 1e9
    cases = {item["key"]: item for item in recipe["cases"]}
    assert len(cases) == 8
    for name, epsilon, conductivity in (("wood", 1.99, .0047), ("glass", 6.31, .0036),
                                       ("brick", 3.91, .0238), ("concrete", 5.24, .0462)):
        assert cases[name]["relative_permittivity"] == epsilon
        assert cases[name]["conductivity_s_per_m"] == conductivity
    sheet = cases["sheet"]
    assert 1 / (sheet["conductivity_s_per_m"] * sheet["thickness_m"]) == 1
    assert sheet["bounds_m"][0] == sheet["bounds_m"][1]
    assert cases["layered_glass"]["layers_m"] == [[0, .02], [.10, .12]]


def test_saved_material_fields_have_valid_controls_and_distinct_responses():
    data = load_material_lab()
    assert data.case_names == ("air", "wood", "glass", "brick", "concrete", "layered_glass", "sheet", "metal")
    assert data.frequency_hz == 1e9
    assert np.ptp(data.x_m) == pytest.approx(2.1)
    assert np.ptp(data.y_m) == pytest.approx(1.3)
    iy, ix = np.argmin(abs(data.y_m)), np.argmin(abs(data.x_m - .06))
    amplitudes = np.linalg.norm(data.electric_field[:, iy, ix], axis=-1)
    assert amplitudes[-1] < 1e-8
    assert np.all(amplitudes[1:5] > 1e-4)
    for i in range(1, len(data.case_names)):
        assert not np.allclose(data.electric_field[i], data.electric_field[0])
    for item in data.metadata["run_evidence"].values():
        assert item["last_reported_energy_db"] <= -60
    for receiver in data.metadata["receivers"]:
        assert receiver["change_vs_air_db"][0] == 0
        assert len(receiver["change_vs_air_db"]) == 8
    sensitivity = data.metadata["sensitivity"]
    assert sensitivity["performed"] and sensitivity["material"] == "concrete"
    assert max(abs(item["difference_db"]) for item in sensitivity["receiver_checks"]) < 0.1


def test_material_reference_and_raw_evidence_integrity():
    root = Path(__file__).resolve().parents[1]
    meta = load_material_lab().metadata
    assert "P.2040-4" in meta["material_reference"]
    for name, digest in meta["raw_sha256"].items():
        assert hashlib.sha256((root / "data/material_lab/raw" / name).read_bytes()).hexdigest() == digest
    for name, digest in meta["generator_sha256"].items():
        path = root / "simulations" / name
        if not path.exists():
            path = root / "src/pyvista_radiation" / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_larger_viewer_uses_actual_layer_and_sheet_geometry_and_preserves_camera():
    pytest.importorskip("pyvista")
    pytest.importorskip("trame")
    from pyvista_radiation.wall_view import case_bounds, create_wall_app

    data = load_material_lab()
    server, viewer = create_wall_app(data, server_name="larger-material-lab-test")
    try:
        server.state.ready()
        mesh_id = id(viewer.mesh)
        camera = tuple(viewer.plotter.camera.position)
        with server.state:
            server.state.wall_case = "layered_glass"
            server.state.wall_mode = "phase"
            server.state.wall_phase = 90
        assert server.state.wall_caption == "Glass / air / glass"
        assert len(viewer.case_actors["layered_glass"]) == 2
        assert all(a.GetVisibility() for a in viewer.case_actors["layered_glass"])
        assert not any(a.GetVisibility() for a in viewer.case_actors["concrete"])
        assert case_bounds(data, "layered_glass") == [[0, .02, -.5, .5, -.3, .3], [.1, .12, -.5, .5, -.3, .3]]
        with server.state:
            server.state.wall_case = "sheet"
        assert len(viewer.case_actors["sheet"]) == 1
        assert case_bounds(data, "sheet")[0][0] == case_bounds(data, "sheet")[0][1]
        assert "sheet resistance 1" in server.state.wall_material_note
        assert id(viewer.mesh) == mesh_id
        assert tuple(viewer.plotter.camera.position) == camera
        mesh = field_plane_mesh(data, "sheet", mode="phase", phase_deg=90)
        np.testing.assert_array_equal(viewer.mesh["Displayed field"], mesh.active_scalars)
    finally:
        viewer.close()
