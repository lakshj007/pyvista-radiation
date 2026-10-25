import numpy as np
import pytest

from pyvista_radiation import RadiationData, load, save
from pyvista_radiation.display import field_db
from pyvista_radiation.model import CONVENTION


@pytest.fixture
def sample():
    m = dict(
        schema_version=1,
        angle_convention=CONVENTION,
        angle_unit="rad",
        frequency_unit="Hz",
        field_unit="V/m",
        array_order=["frequency", "theta", "phi"],
        reference_radius_m=1,
        normalization="none",
        provenance=dict(
            kind="analytic",
            source="test dipole",
            generator="pytest",
            solver_version="not applicable",
        ),
    )
    t = np.linspace(0, np.pi, 7)
    p = np.arange(8) * np.pi / 4
    e = np.broadcast_to(np.sin(t)[None, :, None], (2, 7, 8)).astype(complex)
    return dict(
        frequency_hz=np.array([1e9, 2e9]),
        theta_rad=t,
        phi_rad=p,
        e_theta=e,
        e_phi=np.zeros_like(e),
        metadata=m,
    )


def test_roundtrip(tmp_path, sample):
    d = RadiationData(**sample)
    save(tmp_path / "x.npz", d)
    actual = load(tmp_path / "x.npz")
    for key in sample.keys() - {"metadata"}:
        np.testing.assert_array_equal(getattr(d, key), getattr(actual, key))
    assert actual.metadata == d.metadata
    assert not actual.e_theta.flags.writeable


@pytest.mark.parametrize(
    "key,value",
    [
        ("frequency_hz", [0, 1]),
        ("frequency_hz", [2, 1]),
        ("frequency_hz", [[1, 2]]),
        ("theta_rad", [-1, 0, 1]),
        ("phi_rad", [0, 2 * np.pi]),
        ("e_theta", np.zeros((2, 8, 7), complex)),
        ("e_phi", np.zeros((2, 7, 8))),
        ("e_theta", np.full((2, 7, 8), np.nan + 1j)),
        ("radiated_power_w", [-1, 1]),
        ("directivity_max", [0.5, 1]),
        ("radiated_power_w", [1]),
    ],
)
def test_bad_arrays(sample, key, value):
    sample[key] = value
    with pytest.raises(ValueError):
        RadiationData(**sample)


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", 2),
        ("schema_version", True),
        ("field_unit", "arbitrary"),
        ("normalization", "peak"),
        ("array_order", ["theta", "phi", "frequency"]),
        ("angle_unit", "deg"),
        ("reference_radius_m", 0),
        ("reference_radius_m", True),
        ("provenance", {}),
    ],
)
def test_bad_metadata(sample, key, value):
    sample["metadata"][key] = value
    with pytest.raises(ValueError):
        RadiationData(**sample)


def test_display_does_not_change_fields(sample):
    sample["e_theta"][0] = 0
    d = RadiationData(**sample)
    original = d.e_theta.copy()
    assert np.all(field_db(d, 0) == -40)
    assert field_db(d, 1).max() == 0
    np.testing.assert_array_equal(d.e_theta, original)


def test_field_amplitude_db(sample):
    sample["e_theta"][0] = 0.5
    sample["e_theta"][0, 0, 0] = 1
    d = RadiationData(**sample)
    assert field_db(d, 0)[1, 1] == pytest.approx(-6.020599913)


def test_reject_object_pickle(tmp_path):
    np.savez(tmp_path / "bad.npz", metadata_json=np.array({"bad": 1}, dtype=object))
    with pytest.raises(ValueError):
        load(tmp_path / "bad.npz")


def test_missing_metadata(sample):
    del sample["metadata"]["provenance"]
    with pytest.raises(ValueError):
        RadiationData(**sample)


def test_invalid_json(tmp_path, sample):
    sample.pop("metadata")
    np.savez(tmp_path / "bad.npz", **sample, metadata_json="not json")
    with pytest.raises(ValueError):
        load(tmp_path / "bad.npz")
