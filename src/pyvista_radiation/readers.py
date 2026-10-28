"""Solver-independent adapters into the physical complex-field data contract."""

import csv
from pathlib import Path

import numpy as np

from .model import CONVENTION, RadiationData, _real_array


def from_arrays(
    frequency_hz,
    theta,
    phi,
    e_theta,
    e_phi=None,
    *,
    reference_radius_m,
    source,
    angle_unit="rad",
    kind="simulation",
    solver_version="unspecified",
    radiated_power_w=None,
    directivity_max=None,
):
    """Build validated radiation data without writing schema metadata by hand.

    ``theta`` is polar angle from +z; ``phi`` is azimuth from +x toward +y.
    ``angle_unit`` is 'rad' or 'deg'. Frequencies are Hz, fields are unnormalized
    complex V/m at ``reference_radius_m``, ordered (frequency, theta, phi).
    A scalar frequency and a 2D field are accepted for a single frequency.
    Omitting ``e_phi`` explicitly assumes that component is zero. Real arrays
    are rejected: cast to complex explicitly only if zero phase is intended.
    No phase, gain, normalization, angle convention or field units are inferred.

    A duplicate phi endpoint at 0/360 degrees (0/2pi radians) is removed only
    when both complex components agree there. Otherwise it raises ValueError.
    Other malformed, partial or unsorted axes are passed to the data model's
    validation; full-sphere coverage is required later for mesh conversion.
    """
    if angle_unit not in ("rad", "deg"):
        raise ValueError("angle_unit must be rad or deg")
    frequency = np.atleast_1d(_real_array(frequency_hz, "frequency_hz"))
    theta = _real_array(theta, "theta")
    phi = _real_array(phi, "phi")
    if angle_unit == "deg":
        theta, phi = np.deg2rad(theta), np.deg2rad(phi)
    et = np.asarray(e_theta)
    ep = np.zeros_like(et) if e_phi is None else np.asarray(e_phi)
    if len(frequency) == 1:
        et = et[None, ...] if et.ndim == 2 else et
        ep = ep[None, ...] if ep.ndim == 2 else ep
    if any(a.dtype.kind != "c" or not np.isfinite(a).all() for a in (et, ep)):
        raise ValueError("fields must contain finite complex V/m samples; phase is never inferred")
    removed = False
    if (
        phi.ndim == 1
        and len(phi) >= 2
        and phi[0] == 0
        and np.isclose(phi[-1], 2 * np.pi, rtol=0, atol=1e-12)
    ):
        expected = (len(frequency), theta.size, len(phi))
        if et.shape != expected or ep.shape != expected:
            raise ValueError(f"fields must have shape {expected} before removing the phi seam")
        if not all(np.allclose(a[..., 0], a[..., -1], rtol=1e-7, atol=1e-12) for a in (et, ep)):
            raise ValueError("duplicate phi endpoints must agree in both complex components")
        phi, et, ep = phi[:-1], et[..., :-1], ep[..., :-1]
        removed = True
    metadata = dict(
        schema_version=1,
        angle_convention=CONVENTION,
        angle_unit="rad",
        frequency_unit="Hz",
        field_unit="V/m",
        array_order=["frequency", "theta", "phi"],
        reference_radius_m=reference_radius_m,
        normalization="none",
        provenance=dict(
            kind=kind,
            source=source,
            generator="pyvista_radiation.from_arrays",
            solver_version=solver_version,
            input_angle_unit=angle_unit,
            duplicate_phi_endpoint_removed=removed,
        ),
    )
    return RadiationData(
        frequency,
        theta,
        phi,
        et,
        ep,
        metadata,
        radiated_power_w=radiated_power_w,
        directivity_max=directivity_max,
    )


def load_csv(
    path,
    *,
    reference_radius_m,
    source=None,
    angle_unit="deg",
    kind="simulation",
    solver_version="unspecified",
):
    """Load a complete rectangular long-form complex-field CSV (arbitrary row order).

    Required columns: frequency_hz, theta_deg, phi_deg, e_theta_real_v_m,
    e_theta_imag_v_m, e_phi_real_v_m, e_phi_imag_v_m. With angle_unit='rad',
    the angle columns are theta_rad and phi_rad instead. Extra, duplicate or
    missing columns, duplicate samples, nonfinite values and missing grid cells
    raise ValueError. Reference radius is supplied explicitly, never inferred.
    This is an exchange format, not a vendor-specific solver parser.
    """
    if angle_unit not in ("rad", "deg"):
        raise ValueError("angle_unit must be rad or deg")
    columns = [
        "frequency_hz",
        f"theta_{angle_unit}",
        f"phi_{angle_unit}",
        "e_theta_real_v_m",
        "e_theta_imag_v_m",
        "e_phi_real_v_m",
        "e_phi_imag_v_m",
    ]
    try:
        with Path(path).open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames is None or sorted(reader.fieldnames) != sorted(columns):
                raise ValueError(f"CSV requires exactly these columns: {', '.join(columns)}")
            rows = []
            for line, row in enumerate(reader, start=2):
                if None in row or any(row.get(c) is None for c in columns):
                    raise ValueError(f"CSV row {line} has missing or extra values")
                try:
                    rows.append([float(row[c]) for c in columns])
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"CSV row {line} must contain numeric values") from exc
    except OSError as exc:
        raise ValueError(f"Cannot read radiation CSV {path}: {exc}") from exc
    if not rows or not np.isfinite(rows).all():
        raise ValueError("CSV must contain finite numeric samples")
    values = np.array(rows)
    axes = [np.unique(values[:, i]) for i in range(3)]
    shape = tuple(len(a) for a in axes)
    if len(values) != int(np.prod(shape)):
        raise ValueError("CSV requires a complete rectangular frequency/theta/phi grid")
    indices = tuple(np.searchsorted(a, values[:, i]) for i, a in enumerate(axes))
    flat = np.ravel_multi_index(indices, shape)
    if len(np.unique(flat)) != len(flat):
        raise ValueError("CSV contains duplicate frequency/theta/phi samples")
    et, ep = np.empty(shape, complex), np.empty(shape, complex)
    et[indices], ep[indices] = values[:, 3] + 1j * values[:, 4], values[:, 5] + 1j * values[:, 6]
    data = from_arrays(
        *axes,
        et,
        ep,
        reference_radius_m=reference_radius_m,
        source=str(path) if source is None else source,
        angle_unit=angle_unit,
        kind=kind,
        solver_version=solver_version,
    )
    data.metadata["provenance"]["generator"] = "pyvista_radiation.load_csv"
    return data
