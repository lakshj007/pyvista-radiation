"""Metric terrain grids and first-order terrain-aware radio link estimates.

Only NumPy is required. This is not a complete ITU terrain prediction method:
free-space loss plus the P.526 single-knife-edge approximation at the most
significant sampled obstacle. It omits multiple-edge interactions, reflections,
rock/building penetration, foliage, fading, atmospheric absorption and noise.
Optional building boxes contribute roof obstruction; this is not an urban
ray tracer or a street-canyon multipath model.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .numerics import directivity, frequency_index, require_full_sphere

C0 = 299792458.0


@dataclass(frozen=True)
class Building:
    """Axis-aligned opaque box in local metres, with absolute base/roof elevations."""

    xmin: float
    xmax: float
    ymin: float
    ymax: float
    base_m: float
    roof_m: float

    def __post_init__(self):
        if not np.isfinite(list(asdict(self).values())).all():
            raise ValueError("building coordinates must be finite")
        if self.xmin >= self.xmax or self.ymin >= self.ymax or self.base_m >= self.roof_m:
            raise ValueError("building bounds and base/roof must increase")

    def contains(self, x, y):
        return (x >= self.xmin) & (x <= self.xmax) & (y >= self.ymin) & (y <= self.ymax)

    def interval(self, start, end):
        """Exact segment/footprint intersection as fractions of horizontal length."""
        lo, hi = 0.0, 1.0
        for a, b, lower, upper in zip(start, end, (self.xmin, self.ymin), (self.xmax, self.ymax)):
            delta = b - a
            if delta == 0:
                if not lower <= a <= upper:
                    return None
            else:
                u, v = sorted(((lower - a) / delta, (upper - a) / delta))
                lo, hi = max(lo, u), min(hi, v)
                if lo > hi:
                    return None
        return lo, hi


def _positive(value, name):
    if (
        isinstance(value, (bool, np.bool_))
        or not np.isscalar(value)
        or not np.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{name} must be positive and finite")
    return float(value)


@dataclass(frozen=True)
class TerrainGrid:
    """Local horizontal x/y and ground elevation in metres; z ordering is (y,x).

    All elevations share one local vertical datum. Geographic degrees and nodata
    are unsupported; project a DEM into local metric coordinates first.
    """

    x_m: np.ndarray
    y_m: np.ndarray
    elevation_m: np.ndarray
    source: str = "User-provided local metric terrain"

    def __post_init__(self):
        for name in ("x_m", "y_m", "elevation_m"):
            value = np.asarray(getattr(self, name))
            if value.dtype.kind not in "fiu" or not np.isfinite(value).all():
                raise ValueError(f"{name} must be finite real data; remove nodata first")
            value = np.array(value, dtype=float, copy=True)
            value.flags.writeable = False
            object.__setattr__(self, name, value)
        for name in ("x_m", "y_m"):
            a = getattr(self, name)
            if a.ndim != 1 or len(a) < 2 or np.any(np.diff(a) <= 0):
                raise ValueError(
                    f"{name} must be a strictly increasing 1D axis with at least two samples"
                )
        if self.elevation_m.shape != (len(self.y_m), len(self.x_m)):
            raise ValueError("elevation_m must have shape (len(y_m), len(x_m))")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a nonempty string")

    def sample(self, x, y):
        """Bilinear elevation at in-bounds local coordinates; reject extrapolation."""
        x, y = np.broadcast_arrays(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
        if (
            not np.isfinite(x).all()
            or not np.isfinite(y).all()
            or np.any(
                (x < self.x_m[0]) | (x > self.x_m[-1]) | (y < self.y_m[0]) | (y > self.y_m[-1])
            )
        ):
            raise ValueError("coordinates must be finite and inside the terrain grid")
        i = np.clip(np.searchsorted(self.x_m, x, side="right") - 1, 0, len(self.x_m) - 2)
        j = np.clip(np.searchsorted(self.y_m, y, side="right") - 1, 0, len(self.y_m) - 2)
        u = (x - self.x_m[i]) / (self.x_m[i + 1] - self.x_m[i])
        v = (y - self.y_m[j]) / (self.y_m[j + 1] - self.y_m[j])
        z = self.elevation_m
        return (
            (1 - u) * (1 - v) * z[j, i]
            + u * (1 - v) * z[j, i + 1]
            + (1 - u) * v * z[j + 1, i]
            + u * v * z[j + 1, i + 1]
        )


def synthetic_terrain(kind="ridge", nx=81, ny=61):
    """Deterministic illustrative landscape, not a geographic or measured DEM."""
    if not isinstance(nx, int) or not isinstance(ny, int) or min(nx, ny) < 3:
        raise ValueError("nx and ny must be integers at least 3")
    x = np.linspace(-3000, 3000, nx)
    y = np.linspace(-2250, 2250, ny)
    xx, yy = np.meshgrid(x / 3, y / 3)
    if kind == "flat":
        z = np.zeros_like(xx)
    elif kind == "ridge":
        z = 150 * np.exp(-((xx / 110) ** 2)) * (0.8 + 0.2 * np.cos(yy / 300) ** 2)
    elif kind == "mountains":
        z = (
            210 * np.exp(-(((xx + 90) / 170) ** 2) - ((yy - 80) / 380) ** 2)
            + 125 * np.exp(-(((xx - 390) / 140) ** 2) - ((yy + 260) / 220) ** 2)
            + 45 * np.exp(-(((xx + 520) / 220) ** 2) - ((yy - 400) / 170) ** 2)
        )
    elif kind == "valley":
        center = 200 * np.sin(xx / 400)
        z = 290 * (1 - np.exp(-((yy - center) / 270) ** 2))
        z += 35 * (1 + np.sin(xx / 170)) * (1 - np.exp(-((yy - center) / 350) ** 2))
    elif kind == "rugged":
        rng = np.random.default_rng(42)
        z = np.zeros_like(xx)
        for _ in range(20):
            cx, cy = rng.uniform(-900, 900), rng.uniform(-650, 650)
            wx, wy = rng.uniform(90, 230, 2)
            z += rng.uniform(50, 160) * np.exp(-((xx - cx) / wx) ** 2 - ((yy - cy) / wy) ** 2)
    else:
        raise ValueError("terrain kind must be flat, ridge, mountains, valley or rugged")
    return TerrainGrid(x, y, z, f"Synthetic {kind} landscape (illustrative; metres)")


def save_terrain(path, terrain):
    """Write metric elevation arrays and provenance without pickle."""
    with Path(path).open("wb") as stream:
        np.savez_compressed(
            stream,
            x_m=terrain.x_m,
            y_m=terrain.y_m,
            elevation_m=terrain.elevation_m,
            metadata_json=json.dumps(
                dict(
                    schema_version=1, horizontal_unit="m", vertical_unit="m", source=terrain.source
                )
            ),
        )


def load_terrain(path):
    """Load this module's NPZ terrain contract, rejecting unknown units/keys."""
    with np.load(path, allow_pickle=False) as z:
        if set(z.files) != {"x_m", "y_m", "elevation_m", "metadata_json"}:
            raise ValueError("terrain archive requires x_m, y_m, elevation_m, metadata_json")
        raw = z["metadata_json"]
        if raw.shape != () or raw.dtype.kind != "U":
            raise ValueError("terrain metadata must be scalar JSON text")
        m = json.loads(raw.item())
        if (
            not isinstance(m, dict)
            or type(m.get("schema_version")) is not int
            or m["schema_version"] != 1
            or m.get("horizontal_unit") != "m"
            or m.get("vertical_unit") != "m"
        ):
            raise ValueError("unsupported terrain schema or units; local metric metres required")
        return TerrainGrid(z["x_m"], z["y_m"], z["elevation_m"], m.get("source", ""))


def free_space_loss(distance_m, frequency_hz):
    """ITU-R P.525, 20 log10(4 pi d f / c), in dB; d and f must be positive."""
    frequency_hz = _positive(frequency_hz, "frequency_hz")
    d = np.asarray(distance_m, dtype=float)
    if not np.isfinite(d).all() or np.any(d <= 0):
        raise ValueError("distance must be positive and finite")
    return 20 * np.log10(4 * np.pi * d * frequency_hz / C0)


def knife_edge_loss(v):
    """P.526-16 Eq.31 single-edge loss in dB; zero for v <= -0.78.

    This smooth approximation gives about 6.03 dB at a grazing edge (v=0).
    It does not implement the complete P.526 general-terrain method.
    """
    v = np.asarray(v, dtype=float)
    if not np.isfinite(v).all():
        raise ValueError("diffraction parameter must be finite")
    # asinh avoids cancellation for large negative v; identity log(sqrt(x²+1)+x).
    return np.where(v <= -0.78, 0, np.maximum(0, 6.9 + 20 / np.log(10) * np.arcsinh(v - 0.1)))


@dataclass(frozen=True)
class PathProfile:
    distance_m: np.ndarray
    terrain_m: np.ndarray
    effective_terrain_m: np.ndarray
    sightline_m: np.ndarray
    v: np.ndarray
    dominant_index: int
    diffraction_db: float
    line_of_sight: bool
    diffraction_angle_deg: float
    obstruction_m: np.ndarray


def path_profile(
    terrain,
    tx_xyz,
    rx_xyz,
    frequency_hz,
    *,
    sample_spacing_m=None,
    effective_earth_radius_m=8500000.0,
    buildings=(),
):
    """Trace a sampled vertical profile and evaluate its dominant knife edge.

    Heights are absolute elevations in the terrain's local datum. Profiles use
    half the smallest terrain cell as default spacing, never extrapolate, and
    include an effective-Earth bulge. Radius=None disables curvature. Low-angle
    terrestrial geometry is assumed; large-angle paths are flagged in results.
    """
    frequency_hz = _positive(frequency_hz, "frequency_hz")
    tx = np.asarray(tx_xyz, dtype=float)
    rx = np.asarray(rx_xyz, dtype=float)
    if tx.shape != (3,) or rx.shape != (3,) or not np.isfinite([tx, rx]).all():
        raise ValueError("tx and rx must be finite xyz points")
    if tx[2] <= terrain.sample(*tx[:2]) or rx[2] <= terrain.sample(*rx[:2]):
        raise ValueError("antennas must be above local ground")
    for building in buildings:
        if any(building.contains(*p[:2]) and p[2] <= building.roof_m for p in (tx, rx)):
            raise ValueError("antennas must be outdoors or above building roofs")
    total = np.linalg.norm(rx[:2] - tx[:2])
    if total <= 0:
        raise ValueError("profile endpoints must have distinct horizontal positions")
    spacing = _positive(
        sample_spacing_m
        if sample_spacing_m is not None
        else min(np.diff(terrain.x_m).min(), np.diff(terrain.y_m).min()) / 2,
        "sample_spacing_m",
    )
    segments = max(2, int(np.ceil(total / spacing)))
    if segments > 8192:
        raise ValueError("profile exceeds 8192 segments; shorten path or increase sample spacing")
    f = np.linspace(0, 1, segments + 1)
    crossings = []
    for building in buildings:
        interval = building.interval(tx[:2], rx[:2])
        if interval is not None:
            lo, hi = interval
            # Roof entry/exit cannot be skipped even when the building is narrower
            # than the terrain sampling interval. Include neighboring street points.
            crossings.extend([max(0, lo - 1e-8), lo, (lo + hi) / 2, hi, min(1, hi + 1e-8)])
    if crossings:
        f = np.unique(np.r_[f, crossings])
    if len(f) > 8193:
        raise ValueError("profile exceeds 8192 segments including building crossings")
    xy = tx[:2] + f[:, None] * (rx[:2] - tx[:2])
    ground = terrain.sample(xy[:, 0], xy[:, 1])
    obstruction = ground.copy()
    for building in buildings:
        interval = building.interval(tx[:2], rx[:2])
        if interval is not None:
            mask = (f >= interval[0]) & (f <= interval[1])
            obstruction[mask] = np.maximum(obstruction[mask], building.roof_m)
    distance = f * total
    bulge = (
        np.zeros_like(f)
        if effective_earth_radius_m is None
        else distance
        * (total - distance)
        / (2 * _positive(effective_earth_radius_m, "effective_earth_radius_m"))
    )
    effective = obstruction + bulge
    line = tx[2] + f * (rx[2] - tx[2])
    h = effective[1:-1] - line[1:-1]
    v = h * np.sqrt(2 * total / ((C0 / frequency_hz) * distance[1:-1] * (total - distance[1:-1])))
    k = int(np.argmax(v)) + 1
    d1 = distance[k]
    d2 = total - d1
    angle = max(0, np.arctan2(effective[k] - tx[2], d1) + np.arctan2(effective[k] - rx[2], d2))
    return PathProfile(
        distance,
        ground,
        effective,
        line,
        np.r_[np.nan, v, np.nan],
        k,
        float(knife_edge_loss(v[k - 1])),
        bool(np.all(h <= 0)),
        float(np.rad2deg(angle)),
        obstruction,
    )


def relative_pattern_gain(data, index, directions, *, heading_deg=0, elevation_deg=0):
    """Interpolate normalized angular power, returning a relative gain in dB.

    Boresight is aimed along heading (+x toward +y), elevation above the horizon.
    Antenna +x points upward at zero elevation. No absolute gain is inferred.
    Zero field directions return -inf. Seam interpolation is periodic.
    """
    require_full_sphere(data)
    index = frequency_index(data, index)
    if not np.isfinite([heading_deg, elevation_deg]).all():
        raise ValueError("orientation must be finite")
    d = np.asarray(directions, dtype=float)
    if d.shape[-1:] != (3,) or not np.isfinite(d).all() or np.any(np.linalg.norm(d, axis=-1) == 0):
        raise ValueError("directions must be finite nonzero xyz vectors")
    yaw, el = np.deg2rad([heading_deg, elevation_deg])
    z = np.array([np.cos(el) * np.cos(yaw), np.cos(el) * np.sin(yaw), np.sin(el)])
    x = np.array([-np.sin(el) * np.cos(yaw), -np.sin(el) * np.sin(yaw), np.cos(el)])
    y = np.cross(z, x)
    local = d @ np.stack([x, y, z], axis=1)
    theta = np.arccos(np.clip(local[..., 2] / np.linalg.norm(local, axis=-1), -1, 1))
    phi = (
        np.mod(np.arctan2(local[..., 1], local[..., 0]) - data.phi_rad[0], 2 * np.pi)
        + data.phi_rad[0]
    )
    ta = data.theta_rad
    pa = np.r_[data.phi_rad, data.phi_rad[0] + 2 * np.pi]
    i = np.clip(np.searchsorted(ta, theta, side="right") - 1, 0, len(ta) - 2)
    j = np.clip(np.searchsorted(pa, phi, side="right") - 1, 0, len(pa) - 2)
    a = (theta - ta[i]) / (ta[i + 1] - ta[i])
    b = (phi - pa[j]) / (pa[j + 1] - pa[j])
    amplitude = data.field_magnitude[index]
    peak = amplitude.max()
    if not peak:
        raise ValueError("cannot normalize an all-zero antenna pattern")
    power = np.column_stack([(amplitude / peak) ** 2, (amplitude[:, 0] / peak) ** 2])
    gain = (
        (1 - a) * (1 - b) * power[i, j]
        + a * (1 - b) * power[i + 1, j]
        + (1 - a) * b * power[i, j + 1]
        + a * b * power[i + 1, j + 1]
    )
    with np.errstate(divide="ignore"):
        return 10 * np.log10(gain)


@dataclass(frozen=True)
class CoverageResult:
    received_dbm: np.ndarray
    diffraction_db: np.ndarray
    free_space_db: np.ndarray
    relative_gain_db: np.ndarray
    line_of_sight: np.ndarray
    valid: np.ndarray
    large_angle: np.ndarray
    metadata: dict
    x_m: np.ndarray
    y_m: np.ndarray
    ground_elevation_m: np.ndarray
    building_mask: np.ndarray

    def __post_init__(self):
        for key, value in vars(self).items():
            if isinstance(value, np.ndarray):
                value.flags.writeable = False

    def save(self, path):
        """Save results plus all stated assumptions without display clipping."""
        arrays = {k: v for k, v in vars(self).items() if k != "metadata"}
        with Path(path).open("wb") as stream:
            np.savez_compressed(
                stream, **arrays, metadata_json=json.dumps(self.metadata, allow_nan=False)
            )


def coverage_map(
    terrain,
    frequency_hz,
    *,
    tx_xy=None,
    tx_height_m=30,
    rx_height_m=2,
    tx_power_dbm=30,
    tx_peak_gain_dbi=0,
    rx_gain_dbi=0,
    system_loss_db=0,
    pattern=None,
    pattern_index=0,
    heading_deg=0,
    elevation_deg=0,
    diffraction=True,
    min_distance_m=10,
    sample_spacing_m=None,
    effective_earth_radius_m=8500000.0,
    buildings=(),
):
    """Estimate received power on a terrain grid, using a stated assumed link budget.

    Terrain contributes real extra loss, not a decorative surface. One dominant
    knife edge approximates each path; multiple mountains and smooth broad ridges
    can require a more complete diffraction model. All receiver heights are AGL.
    The saved antenna pattern supplies shape only; peak gain is an explicit input.
    Paths inside min_distance_m are masked. No through-rock penetration is modeled.
    """
    if sample_spacing_m is not None:
        sample_spacing_m = _positive(sample_spacing_m, "sample_spacing_m")
    if effective_earth_radius_m is not None:
        effective_earth_radius_m = _positive(effective_earth_radius_m, "effective_earth_radius_m")
    f = _positive(frequency_hz, "frequency_hz")
    tx_h = _positive(tx_height_m, "tx_height_m")
    rx_h = _positive(rx_height_m, "rx_height_m")
    minimum = _positive(min_distance_m, "min_distance_m")
    if (
        not np.isfinite(
            [
                tx_power_dbm,
                tx_peak_gain_dbi,
                rx_gain_dbi,
                system_loss_db,
                heading_deg,
                elevation_deg,
            ]
        ).all()
        or system_loss_db < 0
    ):
        raise ValueError(
            "link budget and orientation must be finite; system loss must be nonnegative"
        )
    if tx_xy is None:
        tx_xy = (terrain.x_m[0] + 0.1 * np.ptp(terrain.x_m), (terrain.y_m[0] + terrain.y_m[-1]) / 2)
    tx_xy = np.asarray(tx_xy, dtype=float)
    if tx_xy.shape != (2,):
        raise ValueError("tx_xy must be a local x,y pair")
    tx = np.r_[tx_xy, float(terrain.sample(*tx_xy)) + tx_h]
    buildings = tuple(buildings)
    if any(b.contains(*tx_xy) and tx[2] <= b.roof_m for b in buildings):
        raise ValueError("transmitter must be outdoors or above building roofs")
    for b in buildings:
        terrain.sample([b.xmin, b.xmax], [b.ymin, b.ymax])
    if pattern is not None:
        pattern_index = frequency_index(pattern, pattern_index)
        if not np.isclose(pattern.frequency_hz[pattern_index], f, rtol=1e-12):
            raise ValueError("coverage frequency must match the selected saved antenna pattern")
        if tx_peak_gain_dbi > 10 * np.log10(directivity(pattern, pattern_index).max()) + 1e-6:
            raise ValueError("assumed peak gain exceeds the selected pattern angular directivity")
    xx, yy = np.meshgrid(terrain.x_m, terrain.y_m)
    xy = np.column_stack([xx.ravel(), yy.ravel()])
    z = terrain.elevation_m.ravel() + rx_h
    distance = np.linalg.norm(np.column_stack([xy, z]) - tx, axis=1)
    horizontal = np.linalg.norm(xy - tx[:2], axis=1)
    valid = (distance >= minimum) & (horizontal > 0)
    building_mask = np.zeros(len(xy), dtype=bool)
    for b in buildings:
        building_mask |= b.contains(xy[:, 0], xy[:, 1])
    # This is an outdoor ground-level map, not indoor or rooftop reception.
    valid &= ~building_mask
    fspl = np.full(len(xy), np.nan)
    loss = fspl.copy()
    gain = fspl.copy()
    los = np.zeros(len(xy), bool)
    angle = np.zeros(len(xy), bool)
    for k in np.flatnonzero(valid):
        rx = np.r_[xy[k], z[k]]
        profile = path_profile(
            terrain,
            tx,
            rx,
            f,
            sample_spacing_m=sample_spacing_m,
            effective_earth_radius_m=effective_earth_radius_m,
            buildings=buildings,
        )
        loss[k] = profile.diffraction_db if diffraction else 0
        los[k] = profile.line_of_sight
        angle[k] = profile.diffraction_angle_deg > 12
        direction = rx - tx
        if diffraction and not profile.line_of_sight:
            edge = profile.dominant_index
            frac = profile.distance_m[edge] / profile.distance_m[-1]
            direction = np.r_[frac * (rx[:2] - tx[:2]), profile.obstruction_m[edge] - tx[2]]
        gain[k] = (
            0
            if pattern is None
            else float(
                relative_pattern_gain(
                    pattern,
                    pattern_index,
                    direction,
                    heading_deg=heading_deg,
                    elevation_deg=elevation_deg,
                )
            )
        )
        fspl[k] = float(free_space_loss(distance[k], f))
    received = tx_power_dbm + tx_peak_gain_dbi + rx_gain_dbi - system_loss_db + gain - fspl - loss
    shape = terrain.elevation_m.shape
    metadata = dict(
        model="Free space plus dominant single knife-edge approximation",
        frequency_hz=f,
        terrain_source=terrain.source,
        terrain_units="m",
        tx_xyz_m=tx.tolist(),
        tx_height_agl_m=tx_h,
        rx_height_agl_m=rx_h,
        tx_power_dbm=float(tx_power_dbm),
        assumed_tx_peak_gain_dbi=float(tx_peak_gain_dbi),
        assumed_rx_gain_dbi=float(rx_gain_dbi),
        system_loss_db=float(system_loss_db),
        saved_pattern_used=pattern is not None,
        heading_deg=float(heading_deg),
        elevation_deg=float(elevation_deg),
        diffraction_enabled=bool(diffraction),
        min_distance_m=minimum,
        sample_spacing_m=sample_spacing_m,
        effective_earth_radius_m=effective_earth_radius_m,
        buildings=[asdict(b) for b in buildings],
        receiver_domain="Outdoor ground grid; building footprints excluded",
        limitations="Single-edge low-angle terrain/roof approximation; no multi-edge interactions, reflections, street-corner propagation, wall/rock penetration, foliage, fading or atmospheric absorption. Not measurement validated.",
    )
    return CoverageResult(
        *(a.reshape(shape) for a in (received, loss, fspl, gain, los, valid, angle)),
        metadata,
        terrain.x_m,
        terrain.y_m,
        terrain.elevation_m,
        building_mask.reshape(shape),
    )
