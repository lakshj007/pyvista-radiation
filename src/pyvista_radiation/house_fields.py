"""Metric Cartesian slices and actual time samples from the two-floor solver."""

import json
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path

import numpy as np


def _axis(values, name):
    a = np.asarray(values)
    if a.dtype.kind not in "fiu" or a.ndim != 1 or a.size < 2:
        raise ValueError(f"{name} must be a real axis with at least two samples")
    a = np.array(a, dtype=float, copy=True)
    if not np.isfinite(a).all() or np.any(np.diff(a) <= 0):
        raise ValueError(f"{name} must be finite and increasing")
    a.flags.writeable = False
    return a


@dataclass(frozen=True)
class CartesianPlane:
    """A plane with in-plane u/v axes mapped to global x/y/z indices.

    Electric phasors have ordering (case, v, u, xyz component), in V/m for the
    stated source normalization. ``axes=(0,2)`` represents a vertical x-z plane.
    """

    u_m: np.ndarray
    v_m: np.ndarray
    axes: tuple
    fixed_m: float
    electric_field: np.ndarray

    def __post_init__(self):
        object.__setattr__(self, "u_m", _axis(self.u_m, "u_m"))
        object.__setattr__(self, "v_m", _axis(self.v_m, "v_m"))
        axes = tuple(self.axes)
        if axes not in ((0, 1), (0, 2), (1, 2)) or not np.isfinite(self.fixed_m):
            raise ValueError("axes must define an ordered Cartesian plane with finite position")
        object.__setattr__(self, "axes", axes)
        e = np.array(self.electric_field, dtype=complex, copy=True)
        if e.ndim != 4 or e.shape[1:] != (len(self.v_m), len(self.u_m), 3) or not np.isfinite(e).all():
            raise ValueError("electric_field must have finite shape (case,v,u,3)")
        e.flags.writeable = False
        object.__setattr__(self, "electric_field", e)


@dataclass(frozen=True)
class HouseFields:
    """Steady-state planes plus recorded vertical Ey pulse samples per case.

    Time arrays can have different lengths because a free-space control may
    finish earlier. No zero padding or temporal interpolation is performed.
    Pulse fields are the original time samples; they are not reconstructed
    from the frequency-domain fields or normalized by a single-frequency port.
    """

    case_names: tuple
    planes: dict
    pulse_u_m: np.ndarray
    pulse_v_m: np.ndarray
    time_s: dict
    pulse_ey: dict
    metadata: dict

    def __post_init__(self):
        names = tuple(self.case_names)
        if not names or len(set(names)) != len(names) or not all(isinstance(n, str) and n for n in names):
            raise ValueError("case names must be nonempty and unique")
        object.__setattr__(self, "case_names", names)
        if set(self.planes) != {"vertical", "downstairs", "upstairs"}:
            raise ValueError("house data requires vertical and two floor planes")
        if any(not isinstance(p, CartesianPlane) or len(p.electric_field) != len(names)
               for p in self.planes.values()):
            raise ValueError("plane case counts must agree")
        object.__setattr__(self, "pulse_u_m", _axis(self.pulse_u_m, "pulse_u_m"))
        object.__setattr__(self, "pulse_v_m", _axis(self.pulse_v_m, "pulse_v_m"))
        if set(self.time_s) != set(names) or set(self.pulse_ey) != set(names):
            raise ValueError("every case requires recorded pulse times and fields")
        times, pulses = {}, {}
        for name in names:
            times[name] = _axis(self.time_s[name], "pulse time")
            raw = np.asarray(self.pulse_ey[name])
            if raw.dtype.kind not in "fiu":
                raise ValueError("recorded pulse fields must be real")
            pulse = np.array(raw, copy=True)
            if pulse.shape != (len(times[name]), len(self.pulse_v_m), len(self.pulse_u_m)) or not np.isfinite(pulse).all():
                raise ValueError("pulse must have finite shape (time,v,u)")
            pulse.flags.writeable = False
            pulses[name] = pulse
        object.__setattr__(self, "time_s", times)
        object.__setattr__(self, "pulse_ey", pulses)
        if (not isinstance(self.metadata, dict) or not self.metadata.get("source_normalization")
                or not self.metadata.get("pulse_normalization")
                or not np.isfinite(self.metadata.get("frequency_hz", 0))
                or self.metadata.get("frequency_hz", 0) <= 0):
            raise ValueError("metadata must state frequency and both source normalizations")
        json.dumps(self.metadata, allow_nan=False)


def save_house_fields(path, data):
    """Save the explicit metric plane/pulse contract without pickle."""
    definitions = [dict(key=key, axes=list(p.axes), fixed_m=p.fixed_m) for key, p in data.planes.items()]
    meta = dict(data.metadata, schema_version=1, coordinate_unit="m", time_unit="s",
                frequency_unit="Hz", field_unit="V/m", plane_order="case,v,u,xyz",
                pulse_order="time,v,u", plane_definitions=definitions)
    arrays = dict(case_names=np.array(data.case_names), pulse_u_m=data.pulse_u_m, pulse_v_m=data.pulse_v_m)
    for i, p in enumerate(data.planes.values()):
        arrays.update({f"p{i}_u": p.u_m, f"p{i}_v": p.v_m, f"p{i}_e": p.electric_field})
    for i, name in enumerate(data.case_names):
        arrays.update({f"t{i}": data.time_s[name], f"ey{i}": data.pulse_ey[name]})
    with Path(path).open("wb") as stream:
        np.savez_compressed(stream, **arrays, metadata_json=json.dumps(meta, allow_nan=False))


def load_house_fields(path):
    """Load only the version-1 metric Cartesian house-slice/pulse contract."""
    with np.load(path, allow_pickle=False) as z:
        raw = z["metadata_json"]
        if raw.shape != () or raw.dtype.kind != "U":
            raise ValueError("metadata must be scalar JSON text")
        meta = json.loads(raw.item())
        if (not isinstance(meta, dict) or type(meta.get("schema_version")) is not int
                or meta["schema_version"] != 1 or meta.get("coordinate_unit") != "m"
                or meta.get("time_unit") != "s" or meta.get("frequency_unit") != "Hz"
                or meta.get("field_unit") != "V/m" or meta.get("plane_order") != "case,v,u,xyz"
                or meta.get("pulse_order") != "time,v,u"):
            raise ValueError("unsupported house schema, units or ordering")
        if z["case_names"].ndim != 1 or z["case_names"].dtype.kind != "U":
            raise ValueError("case names must be a text vector")
        names = tuple(z["case_names"])
        definitions = meta["plane_definitions"]
        expected = {"case_names", "pulse_u_m", "pulse_v_m", "metadata_json"}
        expected |= {f"p{i}_{part}" for i in range(len(definitions)) for part in ("u", "v", "e")}
        expected |= {f"{part}{i}" for i in range(len(names)) for part in ("t", "ey")}
        if set(z.files) != expected:
            raise ValueError("unsupported house archive keys")
        planes = {d["key"]: CartesianPlane(z[f"p{i}_u"], z[f"p{i}_v"], tuple(d["axes"]),
                                          d["fixed_m"], z[f"p{i}_e"]) for i, d in enumerate(definitions)}
        return HouseFields(names, planes, z["pulse_u_m"], z["pulse_v_m"],
                           {n: z[f"t{i}"] for i, n in enumerate(names)},
                           {n: z[f"ey{i}"] for i, n in enumerate(names)}, meta)


def load_house():
    """Load the bundled two-floor openEMS fields and recorded pulse."""
    with as_file(files("pyvista_radiation").joinpath("data/two_floor_house.npz")) as path:
        return load_house_fields(path)


def house_slice_mesh(data, case="open", plane="vertical", *, mode="pulse", frame=0, phase_deg=90):
    """Make a native PyVista StructuredGrid in its actual global x/y/z position.

    Pulse mode displays a recorded Ey frame on the vertical plane. Frequency
    modes preserve full complex vectors and use a shared air reference. Colors
    are normalized for display; raw point arrays remain unclipped.
    """
    import pyvista as pv

    if case not in data.case_names:
        raise ValueError("unknown house case")
    index = data.case_names.index(case)
    if mode == "pulse":
        if plane != "vertical" or isinstance(frame, bool) or not isinstance(frame, (int, np.integer)) or not 0 <= frame < len(data.time_s[case]):
            raise ValueError("pulse mode requires a recorded vertical frame")
        u, v, axes, fixed = data.pulse_u_m, data.pulse_v_m, (0, 2), 0
        raw = data.pulse_ey[case][frame]
        ref = data.metadata["pulse_reference_v_per_m"]
        values = raw / ref
    else:
        if plane not in data.planes or mode not in ("phase", "magnitude_db") or not np.isfinite(phase_deg):
            raise ValueError("unknown plane or field mode")
        p = data.planes[plane]
        u, v, axes, fixed = p.u_m, p.v_m, p.axes, p.fixed_m
        e = p.electric_field[index]
        ref = data.metadata["field_reference_v_per_m"]
        if mode == "phase":
            values = np.real(e[..., 1] * np.exp(1j * np.deg2rad(phase_deg))) / ref
        else:
            with np.errstate(divide="ignore"):
                values = np.clip(20 * np.log10(np.linalg.norm(e, axis=-1) / ref), -60, 0)
    if not np.isfinite(ref) or ref <= 0:
        raise ValueError("display reference must be positive")
    uu, vv = np.meshgrid(u, v)
    xyz = [np.full_like(uu, fixed) for _ in range(3)]
    xyz[axes[0]], xyz[axes[1]] = uu, vv
    mesh = pv.StructuredGrid(*xyz)
    if mode == "pulse":
        mesh["Recorded Ey (V/m)"] = raw.ravel(order="F")
        mesh.field_data["Recorded time (s)"] = [data.time_s[case][frame]]
    else:
        mesh["Electric field real (V/m)"] = e.real.reshape(-1, 3, order="F")
        mesh["Electric field imaginary (V/m)"] = e.imag.reshape(-1, 3, order="F")
    mesh["Displayed field"] = values.ravel(order="F")
    mesh.set_active_scalars("Displayed field")
    mesh.field_data["Frequency (Hz)"] = [data.metadata["frequency_hz"]]
    return mesh
