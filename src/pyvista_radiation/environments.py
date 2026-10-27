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
)


def synthetic_environment(kind="ridge", nx=81, ny=61):
    """Return ground terrain and opaque building boxes; all coordinates in metres.

    City footprints are independent of terrain grid resolution. Streets cross
    x=0 and y=0, allowing west/centre/east outdoor transmitter positions.
    These illustrative scenes do not represent any real geographic location.
    """
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
