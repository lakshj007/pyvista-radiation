import numpy as np
import pytest

from pyvista_radiation import RadiationData
from pyvista_radiation.model import CONVENTION


@pytest.fixture
def analytic():
    def create(kind="isotropic", ntheta=91, nphi=72, scale=(1.0, 0.5)):
        theta = np.linspace(0, np.pi, ntheta)
        phi = np.linspace(0, 2 * np.pi, nphi, endpoint=False)
        t, p = np.meshgrid(theta, phi, indexing="ij")
        magnitude = {
            "isotropic": np.ones_like(t),
            "dipole": np.sin(t),
            "asymmetric": 1 + 0.5 * np.sin(t) * np.cos(p),
            "zero": np.zeros_like(t),
        }[kind]
        fields = np.array([s * magnitude for s in scale], dtype=complex)
        metadata = dict(
            schema_version=1,
            angle_convention=CONVENTION,
            angle_unit="rad",
            frequency_unit="Hz",
            field_unit="V/m",
            array_order=["frequency", "theta", "phi"],
            reference_radius_m=1,
            normalization="none",
            provenance=dict(
                kind="analytic", source=kind, generator="pytest", solver_version="not applicable"
            ),
        )
        return RadiationData(
            np.arange(1, len(scale) + 1) * 1e9, theta, phi, fields, np.zeros_like(fields), metadata
        )

    return create
