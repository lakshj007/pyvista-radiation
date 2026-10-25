import numpy as np
import pytest

from pyvista_radiation import amplitude_db, directivity, load_patch, power_db, principal_cut


def test_decibel_conventions():
    assert amplitude_db(0.5) == pytest.approx(-6.020599913)
    assert power_db(0.5) == pytest.approx(-3.010299956)
    np.testing.assert_allclose(amplitude_db([0, 1e-20, 1]), [-40, -40, 0])
    assert amplitude_db(2) == pytest.approx(6.020599913)


@pytest.mark.parametrize(
    "values,reference,floor",
    [
        ([-1], 1, -40),
        ([np.nan], 1, -40),
        ([1], 0, -40),
        ([1], np.inf, -40),
        ([1], 1, 0),
        ([1], 1, np.nan),
    ],
)
def test_invalid_db(values, reference, floor):
    with pytest.raises(ValueError):
        amplitude_db(values, reference, floor)
    with pytest.raises(ValueError):
        power_db(values, reference, floor)


def test_isotropic_and_dipole_directivity(analytic):
    np.testing.assert_allclose(directivity(analytic(), 0), 1, rtol=0.00011)
    d = analytic("dipole")
    np.testing.assert_allclose(
        directivity(d, 0),
        1.5 * np.sin(d.theta_rad[:, None]) ** 2 * np.ones((1, len(d.phi_rad))),
        atol=3e-7,
    )
    with pytest.raises(ValueError, match="zero"):
        directivity(analytic("zero"), 0)


def test_cut_orientation(analytic):
    d = analytic("asymmetric")
    theta, cut = principal_cut(d, 0, "xz")
    # x = sin(signed theta), so +90 and -90 differ by a factor of three.
    assert cut[np.argmin(abs(theta - 90))] == pytest.approx(0)
    assert cut[np.argmin(abs(theta + 90))] == pytest.approx(20 * np.log10(1 / 3))
    assert (theta[0], theta[-1]) == (-180, 180)
    with pytest.raises(ValueError):
        principal_cut(d, 0, "xy")


def test_solver_directivity_matches_angular_integral():
    d = load_patch()
    for i in range(3):
        # Saved 5° fields use angular quadrature; the solver uses its own
        # radiated-power integral. Bound their discretization difference to 1%.
        assert directivity(d, i).max() == pytest.approx(d.directivity_max[i], rel=0.01)


def test_packaged_sample_matches_repository():
    from pathlib import Path

    from pyvista_radiation import load

    d = load_patch()
    r = load(Path(__file__).resolve().parents[1] / "data/patch_reference.npz")
    np.testing.assert_array_equal(d.e_theta, r.e_theta)
    assert d.metadata == r.metadata
