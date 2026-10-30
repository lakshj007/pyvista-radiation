import gc
import subprocess
import sys

import numpy as np
import pytest

pv = pytest.importorskip("pyvista")


def test_entry_point_discovery_is_lazy_in_fresh_interpreter():
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
import pyvista as pv
assert 'pyvista_radiation._pyvista_plugin' not in sys.modules
plotter = pv.Plotter(off_screen=True)
component = plotter.radiation
assert 'pyvista_radiation._pyvista_plugin' in sys.modules
assert component is plotter.radiation
assert 'trame' not in sys.modules
plotter.close()
""",
        ],
        check=True,
    )


def test_component_uses_native_actor_keeps_scene_and_source_fields(analytic, tmp_path):
    data = analytic("dipole", ntheta=31, nphi=24)
    source = data.e_theta.copy()
    p = pv.Plotter(off_screen=True)
    try:
        other = p.add_mesh(pv.Cube(center=(3, 0, 0)), color="gray")
        component = p.radiation
        actor = component.add_pattern(
            data, index=0, normalization="global", opacity=0.6, show_scalar_bar=False,
            copy_mesh=True,
        )
        assert isinstance(actor, pv.Actor)
        p.add_mesh(pv.Sphere(center=(5,0,0)))
        gc.collect()
        assert actor.mapper.dataset.field_data["Frequency (Hz)"][0] == data.frequency_hz[0]
        p.camera_position = [(5, -5, 5), (0, 0, 0), (0, 0, 1)]
        camera = np.array(list(p.camera_position))
        original_range = actor.mapper.scalar_range
        mesh = component.set_frequency(actor, 1)
        assert isinstance(mesh, pv.PolyData)
        np.testing.assert_allclose(list(p.camera_position), camera)
        assert any(a is other for a in p.actors.values())
        assert actor.prop.opacity == pytest.approx(0.6)
        assert actor.mapper.scalar_range == original_range
        assert mesh.field_data["Frequency (Hz)"][0] == data.frequency_hz[1]
        assert np.max(mesh["Display radius"]) == pytest.approx(0.5)
        # Export and core PyVista filters work without a custom dataset subclass.
        mesh.save(tmp_path / "radiation.vtp")
        reread = pv.read(tmp_path / "radiation.vtp")
        np.testing.assert_allclose(reread["Field magnitude (V/m)"], mesh["Field magnitude (V/m)"])
        assert mesh.clip(normal="x").n_cells > 0
        np.testing.assert_array_equal(data.e_theta, source)
        before = actor.mapper.dataset
        with pytest.raises(ValueError):
            component.set_frequency(actor, 99)
        assert actor.mapper.dataset is before
        with pytest.raises(ValueError, match="not added"):
            component.set_frequency(other, 0)
        component.remove_pattern(actor)
        assert not any(a is actor for a in p.actors.values())
        assert any(a is other for a in p.actors.values())
        np.testing.assert_allclose(list(p.camera_position), camera)
        component.add_pattern(data, show_scalar_bar=False)
    finally:
        p.close()
    assert not component._patterns


def test_plugin_subplots_and_removed_actor(analytic):
    p = pv.Plotter(shape=(1, 2), off_screen=True)
    try:
        left = p.radiation.add_pattern(analytic(), show_scalar_bar=False)
        p.subplot(0, 1)
        right = p.radiation.add_pattern(
            analytic("dipole"), quantity="directivity", show_scalar_bar=False
        )
        p.radiation.set_frequency(left, 1)
        # No caller-held mesh reference: metadata must survive collection.
        gc.collect()
        assert left.mapper.dataset.field_data["Frequency (Hz)"][0] == 2e9
        assert "Directivity (dBi)" in right.mapper.dataset.point_data
        p.remove_actor(left)
        with pytest.raises(ValueError, match="no longer"):
            p.radiation.set_frequency(left, 0)
    finally:
        p.close()
