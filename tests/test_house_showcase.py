import hashlib
import json
import runpy
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import numpy as np
import pytest

from pyvista_radiation import load_house

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/house_showcase"


def test_review_vtk_preserves_every_timestamp_and_selected_raw_samples():
    pv = pytest.importorskip("pyvista")
    scene = pv.read(EXAMPLE / "data/house_pulse.vtm")
    original = load_house()
    pulse = scene["pulse"]
    expected = original.pulse_ey["open"][:, ::2, ::2]
    assert pulse["Ey (V/m)"].dtype == np.float32
    assert pulse["Ey (V/m)"].shape == (2350, 143)
    np.testing.assert_array_equal(pulse["Ey (V/m)"].T.reshape(expected.shape, order="F"), expected)
    np.testing.assert_array_equal(pulse.field_data["Time (s)"], original.time_s["open"])
    x, z = np.meshgrid(original.pulse_u_m[::2], original.pulse_v_m[::2])
    np.testing.assert_array_equal(pulse.points[:, 0], x.ravel(order="F"))
    np.testing.assert_array_equal(pulse.points[:, 2], z.ravel(order="F"))
    assert np.all(pulse.points[:, 1] == 0)
    assert pulse.field_data["Field unit"][0] == "V/m"
    assert pulse.field_data["Air pulse reference (V/m)"][0] == original.metadata["pulse_reference_v_per_m"]
    recipe = original.metadata["recipe"]
    building = scene["building"]
    assert building.n_cells == len(recipe["cases"][0]["boxes"])
    assert building.find_containing_cell([.8, 0, 2.275]) == -1
    assert building.find_containing_cell([-1, 0, 2.275]) >= 0
    np.testing.assert_array_equal(scene["markers"].points,
                                  [recipe["source_xyz_m"], *recipe["receiver_xyz_m"]])


def test_review_data_provenance_and_bundle_integrity():
    directory = EXAMPLE / "data"
    manifest = json.loads((directory / "manifest.json").read_text())
    assert hashlib.sha256((ROOT / manifest["source_archive"]).read_bytes()).hexdigest() == manifest["source_sha256"]
    assert hashlib.sha256((ROOT / "simulations/export_house_showcase.py").read_bytes()).hexdigest() == manifest["exporter_sha256"]
    for name, digest in manifest["files_sha256"].items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest
    assert manifest["license"] == "CC0-1.0"
    assert "No temporal thinning" in manifest["derivation"]
    with ZipFile(ROOT / "preview/house_showcase.zip") as archive:
        assert archive.testzip() is None
        for name in archive.namelist():
            assert name.startswith("house_showcase/") and ".." not in Path(name).parts
            path = EXAMPLE / Path(name).relative_to("house_showcase")
            assert archive.read(name) == path.read_bytes()
        assert "house_showcase/data/LICENSE" in archive.namelist()
        assert "house_showcase/plot_house_pulse.py" in archive.namelist()


def test_standalone_slider_selects_actual_samples_without_replacing_scene():
    pv = pytest.importorskip("pyvista")
    with patch.object(pv, "OFF_SCREEN", True), patch.object(pv.Plotter, "show"):
        example = runpy.run_path(str(EXAMPLE / "plot_house_pulse.py"))
    plotter = example["plotter"]
    try:
        pulse = example["pulse"]
        raw = pulse["Ey (V/m)"].copy()
        identities = [[a.GetAddressAsString("") for a in renderer.actors.values()] for renderer in plotter.renderers]
        cameras = [tuple(renderer.camera.position) for renderer in plotter.renderers]
        for requested in (0, 25.1234, 54.69):
            example["set_time"](requested)
            frame = np.argmin(abs(example["seconds"] * 1e9 - requested))
            assert pulse.field_data["Displayed time (s)"][0] == example["seconds"][frame]
            np.testing.assert_array_equal(pulse["Ey / air reference"], raw[:, frame] / example["reference"])
        np.testing.assert_array_equal(pulse["Ey (V/m)"], raw)
        assert identities == [[a.GetAddressAsString("") for a in r.actors.values()] for r in plotter.renderers]
        assert cameras == [tuple(r.camera.position) for r in plotter.renderers]
    finally:
        plotter.close()
