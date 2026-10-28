"""Reproducible synthetic landscapes and outdoor city test scenes."""

import numpy as np

from .terrain import Building, TerrainGrid, synthetic_terrain

ENVIRONMENTS = (
    ("flat", "Flat"),
    ("ridge", "Ridge"),
    ("mountains", "Mountains"),
    ("rugged", "Rugged mountain range"),
    ("valley", "Winding valley"),
    ("city", "City · low-rise blocks"),
    ("downtown", "City · downtown towers"),
    ("hillside_city", "City · hills, valley & neighborhoods"),
)


def _hillside_ground(x, y):
    """Smooth synthetic ridges surrounding a winding, dry urban valley."""
    valley_x = 130 + 150 * np.sin(y / 400)
    ground = (
        22
        + 190 * np.exp(-(((x + 900) / 340) ** 2) - ((y - 130) / 750) ** 2)
        + 245 * np.exp(-(((x - 900) / 390) ** 2) - ((y - 600) / 420) ** 2)
        + 115 * np.exp(-(((x - 400) / 520) ** 2) - ((y + 780) / 320) ** 2)
        + 28 * (1 + np.sin(x / 300 + y / 240))
    )
    return ground * (1 - 0.65 * np.exp(-(((x - valley_x) / 150) ** 2)))


def environment_roads(kind):
    """Return decorative road centerlines (N,2) and widths in local metres.

    The same corridors reserve building-free space in the hillside preset.
    Road materials/thickness do not contribute propagation losses.
    """
    if kind != "hillside_city":
        return ()
    x = np.linspace(-1200, 1200, 161)
    y = np.linspace(-900, 900, 121)
    roads = [
        (np.column_stack([x, np.zeros_like(x)]), 22),
        (np.column_stack([-220 + 160 * np.sin(y / 360) + 0.12 * y, y]), 20),
        (np.column_stack([x, 420 + 90 * np.sin(x / 350 + 0.7)]), 16),
        (np.column_stack([x, -450 + 110 * np.sin(x / 500)]), 16),
        (np.column_stack([760 + 65 * np.sin(y / 310), y]), 14),
    ]
    # Short cross streets join the two north/south routes. The central avenue
    # stays free of buildings for all three transmitter presets.
    for offset in (-700, -250, 230, 700):
        xx = np.linspace(-600, 1080, 85)
        roads.append((np.column_stack([xx, offset + 25 * np.sin(xx / 280)]), 10))
    return tuple(roads)


def _near_road(x, y, margin):
    """Conservative exact segment intersection with an expanded footprint."""
    for points, width in environment_roads("hillside_city"):
        low = np.array([np.min(x), np.min(y)]) - width / 2 - margin
        high = np.array([np.max(x), np.max(y)]) + width / 2 + margin
        start = points[:-1]
        delta = points[1:] - points[:-1]
        moving = delta != 0
        a = np.divide(low - start, delta, out=np.full_like(delta, -np.inf), where=moving)
        b = np.divide(high - start, delta, out=np.full_like(delta, np.inf), where=moving)
        parallel_miss = np.any(~moving & ((start < low) | (start > high)), axis=1)
        enter = np.maximum(0, np.max(np.minimum(a, b), axis=1))
        leave = np.minimum(1, np.min(np.maximum(a, b), axis=1))
        if np.any(~parallel_miss & (enter <= leave)):
            return True
    return False


def _hillside_city(nx, ny):
    validated = synthetic_terrain("flat", nx, ny)
    x, y = validated.x_m * 0.4, validated.y_m * 0.4
    xx, yy = np.meshgrid(x, y)
    terrain = TerrainGrid(
        x,
        y,
        _hillside_ground(xx, yy),
        "Synthetic hillside city · ridges, dry valley, neighborhoods and parkland "
        "(illustrative; 2.4 × 1.8 km; metres)",
    )
    rng = np.random.default_rng(29)
    buildings = []
    reserved = ((900, 675), (900, -675))  # inspected outdoor receiver plazas
    for cx in np.arange(-1050, 1051, 140):
        for cy in np.arange(-770, 771, 140):
            # Leave ridges and two park districts open, creating an uneven city edge.
            if ((cx + 670) / 240) ** 2 + ((cy - 500) / 240) ** 2 < 1:
                continue
            if ((cx - 350) / 190) ** 2 + ((cy + 260) / 150) ** 2 < 1:
                continue
            split = rng.random() < 0.6
            for side in (-1, 1) if split else (0,):
                bx = cx + side * 28 + rng.uniform(-8, 8)
                by = cy + rng.uniform(-14, 14)
                width = rng.uniform(28, 42) if split else rng.uniform(60, 90)
                depth = rng.uniform(46, 90)
                xmin, xmax = bx - width / 2, bx + width / 2
                ymin, ymax = by - depth / 2, by + depth / 2
                sx, sy = np.meshgrid(np.linspace(xmin, xmax, 5), np.linspace(ymin, ymax, 5))
                if _near_road(sx, sy, 6):
                    continue
                if any(
                    xmin - 30 < px < xmax + 30 and ymin - 30 < py < ymax + 30 for px, py in reserved
                ):
                    continue
                # Include every grid breakpoint, where extrema of the bilinear
                # terrain can occur. Foundations meet the ground without floating.
                footprint_x = np.r_[xmin, x[(x > xmin) & (x < xmax)], xmax]
                footprint_y = np.r_[ymin, y[(y > ymin) & (y < ymax)], ymax]
                fx, fy = np.meshgrid(footprint_x, footprint_y)
                ground = terrain.sample(fx, fy)
                downtown = np.exp(-(((bx - 230) / 420) ** 2) - ((by - 140) / 360) ** 2)
                height = rng.uniform(8, 25) + 175 * downtown * rng.uniform(0.5, 1.15)
                buildings.append(
                    Building(
                        xmin,
                        xmax,
                        ymin,
                        ymax,
                        float(ground.min()) - 1,
                        float(ground.max()) + height,
                    )
                )
    return terrain, tuple(buildings)


def synthetic_environment(kind="ridge", nx=81, ny=61):
    """Return ground terrain and opaque building boxes; all coordinates in metres.

    City footprints are independent of terrain grid resolution. Streets cross
    x=0 and y=0, allowing west/centre/east outdoor transmitter positions.
    These illustrative scenes do not represent any real geographic location.
    """
    if kind == "hillside_city":
        return _hillside_city(nx, ny)
    if kind not in ("city", "downtown"):
        return synthetic_terrain(kind, nx, ny), ()
    # Reuse grid validation, then crop the flat ground to a neighborhood scale.
    flat = synthetic_terrain("flat", nx, ny)
    terrain = TerrainGrid(
        flat.x_m * (800 / 3000),
        flat.y_m * (600 / 2250),
        flat.elevation_m,
        f"Synthetic {'downtown towers' if kind == 'downtown' else 'low-rise city'} "
        "(illustrative; 1.6 × 1.2 km; metres)",
    )
    rng = np.random.default_rng(17)
    buildings = []
    for x in np.arange(-675, 676, 150):
        for y in np.arange(-525, 526, 150):
            width, depth = rng.uniform(65, 105, 2)
            height = rng.uniform(8, 24)
            if kind == "downtown":
                height += 135 * np.exp(-((x / 430) ** 2) - (y / 350) ** 2) * rng.uniform(0.6, 1.3)
            buildings.append(
                Building(x - width / 2, x + width / 2, y - depth / 2, y + depth / 2, 0, height)
            )
    return terrain, tuple(buildings)
