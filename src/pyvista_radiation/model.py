"""Version 1 NPZ data contract. No solver imports or pickle deserialization."""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

CONVENTION = "theta_from_+z_phi_from_+x_toward_+y"
REQUIRED_METADATA = {
    "schema_version",
    "angle_convention",
    "angle_unit",
    "frequency_unit",
    "field_unit",
    "array_order",
    "reference_radius_m",
    "normalization",
    "provenance",
}


def _real_array(value, name):
    a = np.asarray(value)
    if a.dtype.kind not in "fiu" or not np.all(np.isfinite(a)):
        raise ValueError(f"{name} must contain finite real numbers")
    return np.array(a, dtype=float, copy=True)


@dataclass(frozen=True)
class RadiationData:
    """Physical arrays ordered (frequency, theta, phi); angles in radians.

    Fields are complex V/m at the declared reference radius. Optional directivity
    is the solver's peak linear directivity, not derived from normalized fields.
    """

    frequency_hz: np.ndarray
    theta_rad: np.ndarray
    phi_rad: np.ndarray
    e_theta: np.ndarray
    e_phi: np.ndarray
    metadata: dict
    radiated_power_w: np.ndarray | None = None
    directivity_max: np.ndarray | None = None

    def __post_init__(self):
        for name in ("frequency_hz", "theta_rad", "phi_rad"):
            a = _real_array(getattr(self, name), name)
            if a.ndim != 1 or a.size == 0 or np.any(np.diff(a) <= 0):
                raise ValueError(f"{name} must be a nonempty strictly increasing 1D array")
            object.__setattr__(self, name, a)
        if np.any(self.frequency_hz <= 0):
            raise ValueError("frequency_hz must be positive")
        if self.theta_rad[0] < 0 or self.theta_rad[-1] > np.pi:
            raise ValueError("theta_rad must be within [0, pi]")
        if self.phi_rad[0] < 0 or self.phi_rad[-1] >= 2 * np.pi:
            raise ValueError("phi_rad must be within [0, 2*pi); omit duplicate seam")
        shape = (len(self.frequency_hz), len(self.theta_rad), len(self.phi_rad))
        for name in ("e_theta", "e_phi"):
            a = np.asarray(getattr(self, name))
            if a.dtype.kind != "c" or a.shape != shape or not np.all(np.isfinite(a)):
                raise ValueError(f"{name} must be finite complex data with shape {shape}")
            object.__setattr__(self, name, np.array(a, copy=True))
        for name in ("radiated_power_w", "directivity_max"):
            if getattr(self, name) is not None:
                a = _real_array(getattr(self, name), name)
                if a.shape != (shape[0],) or np.any(a < 0):
                    raise ValueError(f"{name} must be nonnegative with shape ({shape[0]},)")
                if name == "directivity_max" and np.any(a < 1):
                    raise ValueError("directivity_max must be at least 1 (linear)")
                object.__setattr__(self, name, a)
        try:
            m = json.loads(json.dumps(self.metadata, allow_nan=False))
        except (TypeError, ValueError) as exc:
            raise ValueError("metadata must be a finite JSON object") from exc
        if not isinstance(m, dict) or REQUIRED_METADATA - m.keys():
            raise ValueError(f"metadata requires {sorted(REQUIRED_METADATA)}")
        if type(m["schema_version"]) is not int:
            raise ValueError("schema_version must be an integer")
        expected = dict(
            schema_version=1,
            angle_convention=CONVENTION,
            angle_unit="rad",
            frequency_unit="Hz",
            field_unit="V/m",
            array_order=["frequency", "theta", "phi"],
            normalization="none",
        )
        for key, value in expected.items():
            if m[key] != value:
                raise ValueError(f"unsupported {key}: expected {value!r}")
        r = m["reference_radius_m"]
        if isinstance(r, bool) or not isinstance(r, (int, float)) or r <= 0:
            raise ValueError("reference_radius_m must be positive")
        p = m["provenance"]
        if not isinstance(p, dict) or any(
            not isinstance(p.get(k), str) or not p[k].strip()
            for k in ("kind", "source", "generator", "solver_version")
        ):
            raise ValueError("provenance requires nonempty kind, source, generator, solver_version")
        if p["kind"] not in ("simulation", "analytic"):
            raise ValueError("provenance kind must be simulation or analytic")
        object.__setattr__(self, "metadata", m)
        for name in (
            "frequency_hz",
            "theta_rad",
            "phi_rad",
            "e_theta",
            "e_phi",
            "radiated_power_w",
            "directivity_max",
        ):
            if getattr(self, name) is not None:
                getattr(self, name).flags.writeable = False

    @property
    def field_magnitude(self):
        """Total field amplitude in V/m, without display normalization."""
        return np.hypot(np.abs(self.e_theta), np.abs(self.e_phi))


def save(path: str | Path, data: RadiationData):
    """Validate again before writing, including potentially edited metadata."""
    data = RadiationData(**vars(data))
    arrays = {
        name: getattr(data, name)
        for name in (
            "frequency_hz",
            "theta_rad",
            "phi_rad",
            "e_theta",
            "e_phi",
            "radiated_power_w",
            "directivity_max",
        )
        if getattr(data, name) is not None
    }
    with Path(path).open("wb") as stream:
        np.savez_compressed(
            stream, **arrays, metadata_json=np.array(json.dumps(data.metadata, allow_nan=False))
        )


def load(path: str | Path) -> RadiationData:
    """Read only numeric arrays and scalar JSON; reject unknown schema/keys."""
    required = {"frequency_hz", "theta_rad", "phi_rad", "e_theta", "e_phi", "metadata_json"}
    optional = {"radiated_power_w", "directivity_max"}
    try:
        with np.load(path, allow_pickle=False) as archive:
            keys = set(archive.files)
            if required - keys or keys - required - optional or len(keys) != len(archive.files):
                raise ValueError("NPZ has missing, duplicate, or unsupported arrays")
            raw = archive["metadata_json"]
            if raw.shape != () or raw.dtype.kind != "U":
                raise ValueError("metadata_json must be a scalar Unicode JSON string")
            metadata = json.loads(raw.item())
            return RadiationData(
                metadata=metadata, **{k: archive[k] for k in keys - {"metadata_json"}}
            )
    except (ValueError, TypeError, KeyError, OSError) as exc:
        raise ValueError(f"Invalid radiation dataset {path}: {exc}") from exc
