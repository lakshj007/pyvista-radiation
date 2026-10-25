from pathlib import Path

import numpy as np
import pytest

from pyvista_radiation import load
from pyvista_radiation.display import preview_mesh

ROOT = Path(__file__).resolve().parents[1]


def test_saved_solver_reference():
    data = load(ROOT / "data/patch_reference.npz")
    assert data.e_theta.shape == (3, 37, 72)
    assert data.metadata["provenance"]["kind"] == "simulation"
    assert np.all(data.radiated_power_w > 0)
    assert np.all(data.directivity_max > 1)
    # Separate NF2FF calls must reproduce full-grid samples, including negative
    # theta directions mapped to the opposite azimuth. Compare magnitudes: the
    # local spherical basis changes sign under this mapping.
    with np.load(ROOT / "data/reference_cuts.npz", allow_pickle=False) as cuts:
        for plane, j in enumerate([0, 18]):
            for ci, angle in enumerate(cuts["theta_rad"]):
                i = int(round(abs(angle) / np.deg2rad(5)))
                az = j if angle >= 0 else (j + 36) % 72
                scale = data.field_magnitude.max(axis=(1, 2))
                np.testing.assert_allclose(
                    cuts["field_magnitude"][:, ci, plane] / scale,
                    data.field_magnitude[:, i, az] / scale,
                    rtol=1e-5,
                    atol=1e-7,
                )


def test_preview_closed_surface():
    pytest.importorskip("pyvista")
    data = load(ROOT / "data/patch_reference.npz")
    mesh = preview_mesh(data, 1)
    assert mesh.n_points == 35 * 72 + 2
    assert mesh.n_open_edges == 0
    assert mesh.n_cells == 2 * 35 * 72
    assert np.isfinite(mesh.points).all()
    np.testing.assert_allclose(np.linalg.norm(mesh.points, axis=1).max(), 1)


def test_mesh_samples_match_independent_solver_cuts():
    pytest.importorskip("pyvista")
    from pyvista_radiation import radiation_mesh, spherical_directions

    data = load(ROOT / "data/patch_reference.npz")
    with np.load(ROOT / "data/reference_cuts.npz", allow_pickle=False) as cuts:
        theta = cuts["theta_rad"]
        for i in range(3):
            mesh = radiation_mesh(data, i, mode="sphere")
            peak = data.field_magnitude[i].max()
            for plane, phi in enumerate((0, np.pi / 2)):
                requested = spherical_directions(np.abs(theta), [phi, phi + np.pi])
                xyz = np.array([requested[j, 0 if t >= 0 else 1] for j, t in enumerate(theta)])
                nearest = (xyz @ mesh["Direction"].T).argmax(axis=1)
                np.testing.assert_allclose(
                    mesh["Field magnitude (V/m)"][nearest] / peak,
                    cuts["field_magnitude"][i, :, plane] / peak,
                    rtol=1e-5,
                    atol=2e-7,
                )
