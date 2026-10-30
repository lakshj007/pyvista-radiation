"""A PyVista extension for loading, visualizing and analyzing antenna far fields."""

from .environments import synthetic_environment
from .house_fields import (
    CartesianPlane,
    HouseFields,
    house_slice_mesh,
    load_house,
    load_house_fields,
    save_house_fields,
)
from .mesh import difference_mesh, radiation_mesh
from .metrics import beamwidth, half_power_beamwidth, pattern_difference
from .model import RadiationData, load, save
from .nearfield import (
    FieldPlaneData,
    field_plane_mesh,
    load_field_plane,
    load_material_lab,
    load_through_wall,
    save_field_plane,
)
from .network import NetworkCoverageResult, RadioTower, metro_towers, network_coverage
from .numerics import amplitude_db, directivity, power_db, principal_cut, spherical_directions
from .plotting import RadiationViewer, compare_patterns, plot_pattern
from .readers import from_arrays, load_csv
from .samples import load_patch
from .terrain import (
    Building,
    TerrainGrid,
    coverage_map,
    load_terrain,
    save_terrain,
    synthetic_terrain,
)

__version__ = "0.2.0"
__all__ = [
    "CartesianPlane",
    "HouseFields",
    "house_slice_mesh",
    "load_house",
    "load_house_fields",
    "save_house_fields",
    "from_arrays",
    "load_csv",
    "Building",
    "FieldPlaneData",
    "field_plane_mesh",
    "load_field_plane",
    "save_field_plane",
    "load_through_wall",
    "load_material_lab",
    "RadioTower",
    "NetworkCoverageResult",
    "network_coverage",
    "metro_towers",
    "synthetic_environment",
    "TerrainGrid",
    "coverage_map",
    "load_terrain",
    "save_terrain",
    "synthetic_terrain",
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
