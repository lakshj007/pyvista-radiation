"""Saved complex Cartesian field planes, independent of angular far-field data."""

import json
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class FieldPlaneData:
    """Electric phasors ordered (case, y, x, xyz component) on a constant-z plane.

    Coordinates use metres, frequency uses Hz, and fields use V/m for the stated
    source normalization. A field value is not received power or antenna gain.
    """

    x_m: np.ndarray
    y_m: np.ndarray
    z_m: float
    frequency_hz: float
    electric_field: np.ndarray
    case_names: tuple
    metadata: dict

    def __post_init__(self):
        for name in ("x_m", "y_m"):
            raw = np.asarray(getattr(self, name))
            if raw.dtype.kind not in "fiu":
                raise ValueError(f"{name} must contain real coordinates")
            a = np.array(raw, dtype=float, copy=True)
            if a.ndim != 1 or a.size < 2 or not np.isfinite(a).all() or np.any(np.diff(a) <= 0):
                raise ValueError(f"{name} must be a finite increasing metric axis")
            a.flags.writeable = False
            object.__setattr__(self, name, a)
        if not np.isfinite([self.z_m, self.frequency_hz]).all() or self.frequency_hz <= 0:
            raise ValueError("plane elevation must be finite and frequency positive")
        names = tuple(self.case_names)
        if (not names or len(set(names)) != len(names)
                or not all(isinstance(name, str) and name.strip() for name in names)):
            raise ValueError("case names must be nonempty and unique")
        object.__setattr__(self, "case_names", names)
        e = np.array(self.electric_field, dtype=complex, copy=True)
        if e.shape != (len(names), len(self.y_m), len(self.x_m), 3) or not np.isfinite(e).all():
            raise ValueError("electric_field must be finite complex data shaped (case,y,x,3)")
        e.flags.writeable = False
        object.__setattr__(self, "electric_field", e)
        if not isinstance(self.metadata, dict) or not self.metadata.get("source_normalization"):
            raise ValueError("metadata must state source_normalization")
        json.dumps(self.metadata, allow_nan=False)


def save_field_plane(path, data):
    """Save complex fields and explicit units without pickle."""
    metadata = dict(data.metadata, schema_version=1, coordinate_unit="m", frequency_unit="Hz",
                    field_unit="V/m", array_order=["case", "y", "x", "component_xyz"])
    with Path(path).open("wb") as stream:
        np.savez_compressed(stream, x_m=data.x_m, y_m=data.y_m, z_m=data.z_m,
                            frequency_hz=data.frequency_hz, electric_field=data.electric_field,
                            case_names=np.array(data.case_names),
                            metadata_json=json.dumps(metadata, allow_nan=False))


def load_field_plane(path):
    """Read the version-1 metric plane contract, rejecting unknown units/order."""
    with np.load(path, allow_pickle=False) as saved:
        if set(saved.files) != {"x_m", "y_m", "z_m", "frequency_hz", "electric_field",
                                "case_names", "metadata_json"}:
            raise ValueError("unsupported field-plane archive keys")
        raw = saved["metadata_json"]
        if raw.shape != () or raw.dtype.kind != "U":
            raise ValueError("field metadata must be scalar JSON text")
        meta = json.loads(raw.item())
        if (not isinstance(meta, dict) or type(meta.get("schema_version")) is not int
                or meta["schema_version"] != 1 or meta.get("coordinate_unit") != "m"
                or meta.get("frequency_unit") != "Hz" or meta.get("field_unit") != "V/m"
                or meta.get("array_order") != ["case", "y", "x", "component_xyz"]):
            raise ValueError("unsupported field-plane schema, units or ordering")
        if saved["z_m"].shape != () or saved["frequency_hz"].shape != ():
            raise ValueError("plane elevation and frequency must be scalars")
        if saved["case_names"].ndim != 1 or saved["case_names"].dtype.kind != "U":
            raise ValueError("case_names must be a text vector")
        return FieldPlaneData(saved["x_m"], saved["y_m"], float(saved["z_m"]),
                              float(saved["frequency_hz"]), saved["electric_field"],
                              tuple(saved["case_names"]), meta)


def load_through_wall():
    """Load the bundled, actual openEMS small-wall experiment."""
    with as_file(files("pyvista_radiation").joinpath("data/through_wall.npz")) as path:
        return load_field_plane(path)


def field_plane_mesh(data, case=0, *, mode="magnitude_db", phase_deg=0, reference=None):
    """Return an ordinary PyVista StructuredGrid with preserved vector phasors.

    Magnitude is ``20 log10(|E| / reference)``, clipped only for display to [-50,0]
    dB. Phase mode is Re(Ez exp(j phase)) / reference, a steady-state cycle,
    not a simulation of a pulse arriving. Raw real/imaginary vector arrays stay
    unclipped. One shared reference must be used when comparing multiple cases.
    """
    import pyvista as pv

    if isinstance(case, str):
        case = data.case_names.index(case)
    if isinstance(case, bool) or not isinstance(case, (int, np.integer)) or not 0 <= case < len(data.case_names):
        raise ValueError("case must name an available field plane")
    if not np.isfinite(phase_deg):
        raise ValueError("phase must be finite")
    ref = data.metadata.get("display_reference_v_per_m") if reference is None else reference
    if ref is None:
        ref = np.max(np.linalg.norm(data.electric_field, axis=-1))
    if not np.isscalar(ref) or not np.isfinite(ref) or ref <= 0:
        raise ValueError("reference must be positive and finite")
    xx, yy = np.meshgrid(data.x_m, data.y_m)
    mesh = pv.StructuredGrid(xx, yy, np.full_like(xx, data.z_m))
    e = data.electric_field[case]
    mesh["Electric field real (V/m)"] = e.real.reshape(-1, 3, order="F")
    mesh["Electric field imaginary (V/m)"] = e.imag.reshape(-1, 3, order="F")
    if mode == "magnitude_db":
        with np.errstate(divide="ignore"):
            values = np.clip(20 * np.log10(np.linalg.norm(e, axis=-1) / ref), -50, 0)
        name = "Relative electric field (dB)"
    elif mode == "phase":
        values = np.real(e[..., 2] * np.exp(1j * np.deg2rad(phase_deg))) / ref
        name = "Instantaneous Ez / shared reference"
    else:
        raise ValueError("mode must be magnitude_db or phase")
    mesh[name] = values.ravel(order="F")
    mesh.set_active_scalars(name)
    mesh.field_data["Frequency (Hz)"] = [data.frequency_hz]
    mesh.field_data["Plane z (m)"] = [data.z_m]
    mesh.field_data["Display reference (V/m)"] = [ref]
    return mesh
