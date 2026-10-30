import numpy as np
import pytest

from pyvista_radiation import beamwidth, difference_mesh, half_power_beamwidth, pattern_difference


def test_dipole_beamwidth(analytic):
    result = beamwidth(analytic("dipole", ntheta=181), 0)
    assert result["width_deg"] == pytest.approx(90, abs=0.02)
    assert beamwidth(analytic("isotropic"), 0) is None
    assert beamwidth(analytic("zero"), 0) is None


def test_seam_peak_beamwidth():
    theta = np.linspace(-180, 180, 721)
    a = np.abs(np.cos(np.deg2rad(theta) / 2 - np.pi / 2))
    db = 20 * np.log10(np.maximum(a, 1e-15))
    assert half_power_beamwidth(theta, db)["width_deg"] == pytest.approx(180, abs=0.02)


def test_difference_sign_and_normalization(analytic):
    d = analytic()
    np.testing.assert_allclose(pattern_difference(d, 0, 1), 0)
    np.testing.assert_allclose(pattern_difference(d, 0, 1, normalization="global"), -6.020599913)
    np.testing.assert_allclose(pattern_difference(d, 1, 0, normalization="global"), 6.020599913)
    np.testing.assert_allclose(pattern_difference(analytic("zero"), 0, 1), 0)


def test_difference_mesh_is_sphere(analytic):
    pytest.importorskip("pyvista")
    m = difference_mesh(analytic(), 0, 1, normalization="global")
    np.testing.assert_allclose(np.linalg.norm(m.points, axis=1), 1)
    np.testing.assert_allclose(m["B - A (dB)"], -6.020599913)
    assert m.n_open_edges == 0


def test_bad_beamwidth_input():
    with pytest.raises(ValueError):
        half_power_beamwidth([0, 0, 1], [0, -1, -2])


def test_difference_validates_both_poles(analytic):
    from dataclasses import replace

    pytest.importorskip("pyvista")
    d = analytic()
    e = d.e_theta.copy()
    e[1, 0, 0] *= 2
    with pytest.raises(ValueError, match="pole"):
        difference_mesh(replace(d, e_theta=e), 0, 1)
