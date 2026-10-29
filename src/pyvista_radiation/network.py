"""Independent radio links and strongest-server coverage; no interference model."""

from dataclasses import asdict, dataclass

import numpy as np

from .terrain import CoverageResult, _positive, coverage_map

TOWER_COLORS = ("#ffc857", "#ed785f", "#69c5ef", "#c699ed", "#66d2b2")


@dataclass(frozen=True)
class RadioTower:
    """One transmitter in local metres; antenna height is above local ground."""

    name: str
    x_m: float
    y_m: float
    height_m: float = 60
    power_dbm: float = 40
    peak_gain_dbi: float = 0

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("tower name must be nonempty")
        if not np.isfinite([self.x_m, self.y_m, self.power_dbm, self.peak_gain_dbi]).all():
            raise ValueError("tower coordinates, power and gain must be finite")
        _positive(self.height_m, "tower height")


@dataclass(frozen=True)
class NetworkCoverageResult:
    """Per-tower links and their pointwise maximum, never summed RF power.

    ``serving_index`` indexes ``towers`` and is -1 where every link is invalid.
    Equal powers choose the first tower. A valid antenna null (-inf dBm) remains
    valid. Strongest-link losses and sight lines belong to that winning link.
    """

    towers: tuple
    links: tuple
    strongest: CoverageResult
    serving_index: np.ndarray

    def __post_init__(self):
        self.serving_index.flags.writeable = False

    def save(self, path):
        """Save grid, strongest link, tower identities and all individual powers."""
        import json

        with open(path, "wb") as stream:
            np.savez_compressed(
                stream,
                x_m=self.strongest.x_m,
                y_m=self.strongest.y_m,
                ground_elevation_m=self.strongest.ground_elevation_m,
                received_dbm=self.strongest.received_dbm,
                valid=self.strongest.valid,
                serving_index=self.serving_index,
                per_tower_received_dbm=np.stack([link.received_dbm for link in self.links]),
                metadata_json=json.dumps(self.strongest.metadata, allow_nan=False),
            )


def network_coverage(terrain, frequency_hz, towers, *, buildings=(), **link_options):
    """Evaluate co-frequency towers independently and select the strongest link.

    Shared ``link_options`` are forwarded to :func:`coverage_map` (receiver
    height, diffraction, pattern, etc.). Transmitter location, height, power
    and peak gain come from each ``RadioTower``. Omitting ``pattern`` uses an
    omnidirectional reference, not the saved patch antenna. This estimates
    outdoor received power, not SINR, capacity, interference or handover.
    """
    towers = tuple(towers)
    if not towers or not all(isinstance(t, RadioTower) for t in towers):
        raise ValueError("provide at least one RadioTower")
    if len({t.name for t in towers}) != len(towers):
        raise ValueError("tower names must be unique")
    if {"tx_xy", "tx_height_m", "tx_power_dbm", "tx_peak_gain_dbi"} & link_options.keys():
        raise ValueError("transmitter settings belong on each RadioTower")
    buildings = tuple(buildings)
    links = tuple(
        coverage_map(
            terrain, frequency_hz, tx_xy=(tower.x_m, tower.y_m),
            tx_height_m=tower.height_m, tx_power_dbm=tower.power_dbm,
            tx_peak_gain_dbi=tower.peak_gain_dbi, buildings=buildings, **link_options,
        )
        for tower in towers
    )
    powers = np.stack([link.received_dbm for link in links])
    valid_links = np.stack([link.valid for link in links])
    valid = valid_links.any(axis=0)
    best = np.argmax(np.where(valid_links, powers, -np.inf), axis=0)
    # If every valid link is a null, argmax could otherwise pick an invalid link.
    all_null = valid & np.isneginf(np.max(np.where(valid_links, powers, -np.inf), axis=0))
    best[all_null] = np.argmax(valid_links, axis=0)[all_null]

    def winning(name):
        stacked = np.stack([getattr(link, name) for link in links])
        values = np.take_along_axis(stacked, best[None], axis=0)[0]
        return np.where(valid, values, False if values.dtype.kind == "b" else np.nan)

    metadata = dict(links[0].metadata)
    for key in ("tx_xyz_m", "tx_height_agl_m", "tx_power_dbm", "assumed_tx_peak_gain_dbi"):
        metadata.pop(key)
    metadata.update(
        schema_version=1,
        aggregation="Maximum independent received power; no power sum or interference",
        towers=[dict(asdict(tower), tx_xyz_m=link.metadata["tx_xyz_m"])
                for tower, link in zip(towers, links)],
    )
    strongest = CoverageResult(
        *(winning(key) for key in ("received_dbm", "diffraction_db", "free_space_db",
                                  "relative_gain_db", "line_of_sight")),
        valid, winning("large_angle"), metadata,
        terrain.x_m, terrain.y_m, terrain.elevation_m, links[0].building_mask,
    )
    serving = np.where(valid, best, -1)
    return NetworkCoverageResult(towers, links, strongest, serving)


def metro_towers():
    """Five reserved outdoor sites for the synthetic 7 km square region."""
    return (
        RadioTower("A: West ridge", -2450, -1750),
        RadioTower("B: North town", -1900, 2100),
        RadioTower("C: Central city", 0, 0),
        RadioTower("D: South town", 2200, -1800),
        RadioTower("E: East ridge", 2300, 2200),
    )
