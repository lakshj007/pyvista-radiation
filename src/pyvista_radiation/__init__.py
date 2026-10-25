"""Saved antenna far fields, validated geometry and interactive PyVista views."""

from .mesh import difference_mesh, radiation_mesh
from .metrics import beamwidth, half_power_beamwidth, pattern_difference
from .model import RadiationData, load, save
from .numerics import amplitude_db, directivity, power_db, principal_cut, spherical_directions
from .plotting import RadiationViewer, compare_patterns, plot_pattern
from .samples import load_patch

__version__ = "0.2.0"
__all__ = [
    "beamwidth",
    "half_power_beamwidth",
    "pattern_difference",
    "difference_mesh",
    "RadiationData",
    "load",
    "save",
    "radiation_mesh",
    "amplitude_db",
    "power_db",
    "directivity",
    "principal_cut",
    "spherical_directions",
    "RadiationViewer",
    "plot_pattern",
    "compare_patterns",
    "load_patch",
]
