"""Magnitude-only antenna pattern comparisons; no gain calibration is inferred."""

import numpy as np

from .numerics import frequency_index, principal_cut


def half_power_beamwidth(theta_deg, field_db):
    """Find the -3.0103 dB crossings surrounding a sampled main-lobe maximum.

    Returns angles and width in degrees, or None when a null/omnidirectional
    cut has no bounded half-power lobe. Interpolates dB between samples. A
    complete 360-degree cut is treated periodically, including a seam peak.
    Tied maxima select the angle closest to zero. Independent of display floor.
    """
    theta = np.asarray(theta_deg, dtype=float)
    db = np.asarray(field_db, dtype=float)
    if (
        theta.ndim != 1
        or theta.shape != db.shape
        or len(theta) < 3
        or not np.isfinite(theta).all()
        or not np.isfinite(db).all()
        or np.any(np.diff(theta) <= 0)
    ):
        raise ValueError("beamwidth needs matching finite increasing 1D angle and dB arrays")
    if np.ptp(db) < 1e-12:
        return None
    candidates = np.flatnonzero(np.isclose(db, db.max(), rtol=0, atol=1e-10))
    peak = int(candidates[np.argmin(np.abs(theta[candidates]))])
    peak_angle = float(theta[peak])
    threshold = float(db[peak] - 10 * np.log10(2))
    if np.isclose(theta[-1] - theta[0], 360):
        if peak == len(theta) - 1:
            peak = 0
        base = theta[:-1]
        values = db[:-1]
        theta = np.r_[base - 360, base, base + 360]
        db = np.tile(values, 3)
        peak += len(base)
    left = peak
    while left > 0 and db[left] >= threshold:
        left -= 1
    right = peak
    while right < len(db) - 1 and db[right] >= threshold:
        right += 1
    if db[left] >= threshold or db[right] >= threshold:
        return None
    low = float(np.interp(threshold, [db[left], db[left + 1]], [theta[left], theta[left + 1]]))
    high = float(np.interp(threshold, [db[right], db[right - 1]], [theta[right], theta[right - 1]]))
    if high - low >= 360:
        return None
    return dict(width_deg=high - low, left_deg=low, right_deg=high, peak_angle_deg=peak_angle)


def beamwidth(data, index, plane="xz"):
    """Half-power main-lobe width in a sampled principal plane, in degrees."""
    index = frequency_index(data, index)
    if not data.field_magnitude[index].max():
        return None
    return half_power_beamwidth(*principal_cut(data, index, plane, floor_db=-300))


def pattern_difference(data, left, right, *, normalization="per_frequency", floor_db=-40):
    """B minus A in field dB, after applying the same stated display floor.

    Positive means B is stronger in that direction. Per-frequency normalization
    compares shapes; global normalization includes amplitude differences. Both
    nulls at the floor yield zero, not an undefined logarithmic ratio.
    """
    from .numerics import amplitude_db, reference_amplitude

    left = frequency_index(data, left)
    right = frequency_index(data, right)
    a = amplitude_db(
        data.field_magnitude[left], reference_amplitude(data, left, normalization), floor_db
    )
    b = amplitude_db(
        data.field_magnitude[right], reference_amplitude(data, right, normalization), floor_db
    )
    return b - a
