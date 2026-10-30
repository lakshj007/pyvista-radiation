import numpy as np
import pytest

pv = pytest.importorskip("pyvista")
from pyvista_radiation import compare_patterns


def test_frequency_updates_preserve_camera_and_shared_reference(analytic):
    d = analytic()
    v = compare_patterns(d, off_screen=True, normalization="global")
    try:
        v.plotter.camera.azimuth = 42
        before = np.array(list(v.plotter.camera_position))
        actors = list(v.actors)
        v.set_frequency(0, 1)
        np.testing.assert_allclose(list(v.plotter.camera_position), before)
        assert v.actors == actors
        np.testing.assert_allclose(v.actors[0].mapper.dataset["Display radius"], 0.5)
        v.configure(mode="sphere", floor_db=-30)
        np.testing.assert_allclose(list(v.plotter.camera_position), before)
        assert all(a.mapper.scalar_range == (-30, 0) for a in v.actors)
        assert v.actors[0].mapper.dataset.n_open_edges == 0
        with pytest.raises(ValueError):
            v.set_frequency(8, 0)
        with pytest.raises(ValueError):
            v.configure(floor_db=0)
        assert v.options["floor_db"] == -30
    finally:
        v.close()


def test_camera_presets(analytic):
    v = compare_patterns(analytic(), off_screen=True)
    try:
        v.camera_preset("back")
        np.testing.assert_allclose(v.plotter.camera.position, [0, 0, -5])
        v.set_frequency(0, 1)
        np.testing.assert_allclose(v.plotter.camera.position, [0, 0, -5])
        v.camera_preset("front")
        np.testing.assert_allclose(v.plotter.camera.position, [0, 0, 5])
        with pytest.raises(ValueError):
            v.camera_preset("invalid")
    finally:
        v.close()
