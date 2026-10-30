"""Numerical transformations independent of PyVista and the solver."""

import operator

import numpy as np


def frequency_index(data, index):
    """Validate an explicit integer index; never silently truncate a frequency."""
    try:
        if isinstance(index, (bool, np.bool_)):
            raise TypeError
        index = operator.index(index)
    except TypeError as exc:
        raise ValueError("frequency index must be an integer") from exc
    if not 0 <= index < len(data.frequency_hz):
        raise ValueError("frequency index is out of range")
    return index


def amplitude_db(amplitude, reference=1.0, floor_db=-40.0):
    """20 log10(amplitude/reference), floored only in the returned display array."""
    return _decibels(amplitude, reference, floor_db, 20)


def power_db(power, reference=1.0, floor_db=-40.0):
    """10 log10(power/reference), floored only in the returned display array."""
    return _decibels(power, reference, floor_db, 10)


def _decibels(values, reference, floor_db, factor):
    values = np.asarray(values)
    if values.dtype.kind not in "fiu" or np.any(values < 0) or not np.isfinite(values).all():
        raise ValueError("values must be finite, real and nonnegative")
    if not np.isscalar(reference) or not np.isfinite(reference) or reference <= 0:
        raise ValueError("reference must be a positive finite scalar")
    if not np.isfinite(floor_db) or floor_db >= 0:
        raise ValueError("floor_db must be finite and negative")
    with np.errstate(divide="ignore"):
        result = factor * (np.log10(values) - np.log10(reference))
    return np.maximum(result, floor_db)


def reference_amplitude(data, index, normalization="per_frequency"):
    """Select the sampled peak at one frequency, or across the whole dataset.

    A zero dataset uses reference 1 V/m so division stays defined and zeros stay
    zero. Global normalization compares raw solver amplitudes, not antenna gain.
    """
    index = frequency_index(data, index)
    amplitude = data.field_magnitude
    if normalization == "per_frequency":
        peak = amplitude[index].max()
    elif normalization == "global":
        peak = amplitude.max()
    else:
        raise ValueError("normalization must be per_frequency or global")
    return float(peak) if peak else 1.0


def spherical_directions(theta, phi):
    """Unit vectors on a (theta, phi) grid, with +z polar and +x azimuth origins."""
    t, p = np.meshgrid(theta, phi, indexing="ij")
    return np.stack([np.sin(t) * np.cos(p), np.sin(t) * np.sin(p), np.cos(t)], axis=-1)


def require_full_sphere(data):
    """Mesh/integration support: full theta range and uniform periodic azimuth."""
    t, p = data.theta_rad, data.phi_rad
    if len(t) < 3 or len(p) < 3 or not np.allclose([t[0], t[-1]], [0, np.pi], atol=1e-12, rtol=0):
        raise ValueError("requires full theta coverage [0, pi] and at least three samples per axis")
    if not np.allclose(
        np.diff(np.r_[p, p[0] + 2 * np.pi]), 2 * np.pi / len(p), atol=1e-10, rtol=1e-7
    ):
        raise ValueError("requires uniform full-circle phi coverage without a duplicate seam")


def directivity(data, index):
    """Linear directivity from angular power integration on a full sphere.

    Uses ``abs(E_theta)**2 + abs(E_phi)**2`` at a constant radius in a homogeneous medium.
    This is angular directivity, not gain or efficiency. No absolute power
    calibration is inferred. Trapezoidal theta quadrature needs adequate sampling.
    """
    require_full_sphere(data)
    index = frequency_index(data, index)
    amplitude = data.field_magnitude[index]
    peak = amplitude.max()
    if not peak:
        raise ValueError("directivity is undefined for a zero field")
    intensity = (amplitude / peak) ** 2
    integrand = intensity.mean(axis=1) * np.sin(data.theta_rad)
    trapezoid = getattr(np, "trapezoid", None)
    if trapezoid is None:
        trapezoid = np.trapz
    integral = 2 * np.pi * trapezoid(integrand, data.theta_rad)
    if integral <= 0:
        raise ValueError("angular sampling does not resolve nonzero radiated power")
    return 4 * np.pi * intensity / integral


def principal_cut(data, index, plane="xz", normalization="per_frequency", floor_db=-40):
    """Return signed theta degrees and relative field dB at sampled xz/yz planes.

    Extracts grid values without interpolation. Rejects grids lacking the exact
    requested azimuths. Negative theta uses the opposite azimuth; magnitudes
    remain valid when the spherical component basis changes sign.
    """
    index = frequency_index(data, index)
    if plane not in ("xz", "yz"):
        raise ValueError("plane must be xz or yz")
    base = 0 if plane == "xz" else np.pi / 2
    indices = []
    for angle in (base, base + np.pi):
        matches = np.flatnonzero(np.isclose(data.phi_rad, angle, atol=1e-10, rtol=0))
        if not len(matches):
            raise ValueError(f"grid does not contain azimuth {angle} rad for {plane} cut")
        indices.append(matches[0])
    amplitude = data.field_magnitude[index]
    values = np.r_[amplitude[:0:-1, indices[1]], amplitude[:, indices[0]]]
    angles = np.rad2deg(np.r_[-data.theta_rad[:0:-1], data.theta_rad])
    return angles, amplitude_db(values, reference_amplitude(data, index, normalization), floor_db)
