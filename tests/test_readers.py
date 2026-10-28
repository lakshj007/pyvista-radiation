import csv
import subprocess
import sys

import numpy as np
import pytest

from pyvista_radiation import from_arrays, load, load_csv, save


def test_array_constructor_degrees_single_frequency_and_phase(analytic):
    original = analytic("dipole", ntheta=7, nphi=8, scale=(1,))
    et = original.e_theta[0] * np.exp(0.7j)
    data = from_arrays(
        2.4e9,
        np.rad2deg(original.theta_rad),
        np.rad2deg(original.phi_rad),
        et,
        reference_radius_m=2,
        source="external solver output",
        angle_unit="deg",
    )
    np.testing.assert_allclose(data.theta_rad, original.theta_rad)
    np.testing.assert_allclose(data.e_theta[0], et)
    assert data.metadata["reference_radius_m"] == 2
    assert data.metadata["provenance"]["source"] == "external solver output"
    assert np.all(data.e_phi == 0) and not data.e_theta.flags.writeable
    assert data.e_theta.shape == (1, 7, 8)


def test_array_duplicate_seam_checks_complex_values(analytic):
    d = analytic("dipole", ntheta=7, nphi=8)
    theta = d.theta_rad
    phi = np.r_[d.phi_rad, 2 * np.pi]
    et = np.concatenate([d.e_theta, d.e_theta[..., :1]], axis=2)
    data = from_arrays(d.frequency_hz, theta, phi, et, reference_radius_m=1, source="seam test")
    np.testing.assert_allclose(data.e_theta, d.e_theta)
    assert data.metadata["provenance"]["duplicate_phi_endpoint_removed"]
    et[0, 3, -1] *= 1j  # same magnitude, different phase must not be silently discarded
    with pytest.raises(ValueError, match="complex components"):
        from_arrays(d.frequency_hz, theta, phi, et, reference_radius_m=1, source="bad seam")


def test_array_rejects_ambiguous_units_phase_and_shape(analytic):
    d = analytic("dipole", ntheta=7, nphi=8)
    args = (d.frequency_hz, d.theta_rad, d.phi_rad)
    for fields, options in (
        (d.e_theta.real, {}),
        (d.e_theta, {"angle_unit": "grads"}),
        (d.e_theta.transpose(1, 0, 2), {}),
        (d.e_theta, {"reference_radius_m": 0}),
    ):
        with pytest.raises(ValueError):
            from_arrays(*args, fields, **{"source": "invalid", "reference_radius_m": 1, **options})


def write_csv(path, d, *, radians=False):
    convert = (lambda a: a) if radians else np.rad2deg
    rows = []
    for k, frequency in enumerate(d.frequency_hz):
        for i, theta in enumerate(convert(d.theta_rad)):
            for j, phi in enumerate(convert(d.phi_rad)):
                et, ep = d.e_theta[k, i, j], d.e_phi[k, i, j]
                rows.append([frequency, theta, phi, et.real, et.imag, ep.real, ep.imag])
    np.random.default_rng(4).shuffle(rows)
    unit = "rad" if radians else "deg"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "frequency_hz",
                f"theta_{unit}",
                f"phi_{unit}",
                "e_theta_real_v_m",
                "e_theta_imag_v_m",
                "e_phi_real_v_m",
                "e_phi_imag_v_m",
            ]
        )
        writer.writerows(rows)


@pytest.mark.parametrize("unit", ["deg", "rad"])
def test_csv_reorders_rows_preserves_complex_fields_and_npz_roundtrip(tmp_path, analytic, unit):
    d = analytic("asymmetric", ntheta=7, nphi=8)
    # Give both components distinct phase; neither magnitude-only nor conjugate
    # reconstruction can pass this independent import/export check.
    d = from_arrays(
        d.frequency_hz,
        d.theta_rad,
        d.phi_rad,
        d.e_theta * np.exp(0.4j),
        d.e_theta * np.exp(-0.9j),
        reference_radius_m=3,
        source="CSV fixture",
        kind="analytic",
    )
    path = tmp_path / "fields.csv"
    write_csv(path, d, radians=unit == "rad")
    actual = load_csv(path, reference_radius_m=3, angle_unit=unit, kind="analytic")
    np.testing.assert_allclose(actual.e_theta, d.e_theta)
    np.testing.assert_allclose(actual.e_phi, d.e_phi)
    np.testing.assert_allclose(actual.phi_rad, d.phi_rad)
    save(tmp_path / "imported.npz", actual)
    reloaded = load(tmp_path / "imported.npz")
    np.testing.assert_array_equal(reloaded.e_theta, actual.e_theta)
    assert reloaded.metadata["provenance"]["generator"] == "pyvista_radiation.load_csv"


@pytest.mark.parametrize("problem", ["missing", "duplicate", "nan", "header", "extra"])
def test_csv_rejects_incomplete_ambiguous_and_nonfinite_samples(tmp_path, analytic, problem):
    path = tmp_path / "bad.csv"
    write_csv(path, analytic(ntheta=5, nphi=4))
    lines = path.read_text().splitlines()
    if problem == "missing":
        lines.pop()
    elif problem == "duplicate":
        lines[-1] = lines[1]
    elif problem == "nan":
        cells = lines[1].split(",")
        cells[3] = "nan"
        lines[1] = ",".join(cells)
    elif problem == "header":
        lines[0] = lines[0].replace("theta_deg", "theta")
    else:
        lines[1] += ",100"
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError):
        load_csv(path, reference_radius_m=1)


def test_core_import_stays_independent_of_plotting_and_browser_packages():
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import pyvista_radiation; "
            "assert 'pyvista' not in sys.modules; assert 'trame' not in sys.modules; "
            "assert 'pyvista_radiation._pyvista_plugin' not in sys.modules",
        ],
        check=True,
    )
