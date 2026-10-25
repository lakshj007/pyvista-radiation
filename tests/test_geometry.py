import numpy as np
import pytest

from pyvista_radiation import radiation_mesh, spherical_directions

pv = pytest.importorskip("pyvista")


def test_cardinal_directions():
    xyz = spherical_directions([0, np.pi / 2, np.pi], [0, np.pi / 2, np.pi, 3 * np.pi / 2])
    np.testing.assert_allclose(xyz[1], [[1, 0, 0], [0, 1, 0], [-1, 0, 0], [0, -1, 0]], atol=1e-15)
    np.testing.assert_allclose(xyz[0], np.tile([0, 0, 1], (4, 1)), atol=1e-15)
    np.testing.assert_allclose(xyz[-1], np.tile([0, 0, -1], (4, 1)), atol=1e-15)


def test_sphere_topology_normals_and_seam(analytic):
    d = analytic(ntheta=9, nphi=12)
    mesh = radiation_mesh(d, mode="sphere")
    assert mesh.n_points == 7 * 12 + 2
    assert mesh.n_cells == 2 * 7 * 12
    assert mesh.n_open_edges == 0
    assert mesh.n_points - mesh.extract_all_edges().n_cells + mesh.n_cells == 2
    assert mesh.is_all_triangles
    np.testing.assert_allclose(np.linalg.norm(mesh.points, axis=1), 1)
    # Each triangle has outward winding, including seam and pole fans.
    triangles = mesh.points[mesh.faces.reshape(-1, 4)[:, 1:]]
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    assert np.all(np.sum(normals * triangles.mean(axis=1), axis=1) > 0)
    assert mesh.compute_cell_sizes()["Area"].min() > 0
    assert (
        mesh.extract_feature_edges(
            boundary_edges=True, non_manifold_edges=True, feature_edges=False, manifold_edges=False
        ).n_cells
        == 0
    )


def test_orientation_and_array_order(analytic):
    d = analytic("asymmetric", ntheta=9, nphi=12)
    m = radiation_mesh(d)
    direction = m["Direction"]
    np.testing.assert_allclose(m["Field magnitude (V/m)"], 1 + 0.5 * direction[:, 0], atol=1e-14)
    np.testing.assert_allclose(np.linalg.norm(m.points, axis=1), m["Field magnitude (V/m)"] / 1.5)


def test_global_scale_and_db_radius(analytic):
    d = analytic()
    m = radiation_mesh(d, 1, normalization="global")
    np.testing.assert_allclose(m["Display radius"], 0.5)
    np.testing.assert_allclose(m["Relative field (dB)"], -6.020599913)
    db = radiation_mesh(d, 1, normalization="global", radial_scale="db", floor_db=-30)
    np.testing.assert_allclose(db["Display radius"], (-6.020599913 + 30) / 30)
    np.testing.assert_array_equal(d.e_theta[1], 0.5 + np.zeros_like(d.e_theta[1]))


def test_zeros_and_nulls(analytic):
    d = analytic("zero")
    assert np.isfinite(radiation_mesh(d).points).all()
    assert np.all(radiation_mesh(d)["Display radius"] == 0)
    assert np.all(radiation_mesh(d, mode="sphere")["Display radius"] == 1)
    assert np.all(radiation_mesh(d)["Relative field (dB)"] == -40)
    assert radiation_mesh(analytic("dipole")).n_open_edges == 0


@pytest.mark.parametrize(
    "option,value",
    [
        ("mode", "invalid"),
        ("radial_scale", "invalid"),
        ("normalization", "invalid"),
        ("quantity", "gain"),
        ("floor_db", 0),
        ("frequency_index", -1),
        ("frequency_index", 0.5),
    ],
)
def test_invalid_options(analytic, option, value):
    with pytest.raises(ValueError):
        radiation_mesh(analytic(), **{option: value})


def test_missing_angular_coverage(analytic):
    from dataclasses import replace

    d = analytic()
    partial = replace(d, theta_rad=d.theta_rad[1:], e_theta=d.e_theta[:, 1:], e_phi=d.e_phi[:, 1:])
    with pytest.raises(ValueError, match="full theta"):
        radiation_mesh(partial)
    partial = replace(
        d, phi_rad=d.phi_rad[:-1], e_theta=d.e_theta[:, :, :-1], e_phi=d.e_phi[:, :, :-1]
    )
    with pytest.raises(ValueError, match="full-circle"):
        radiation_mesh(partial)


def test_inconsistent_poles(analytic):
    from dataclasses import replace

    d = analytic()
    e = d.e_theta.copy()
    e[0, 0, 0] *= 2
    with pytest.raises(ValueError, match="pole"):
        radiation_mesh(replace(d, e_theta=e))


def test_directivity_mesh_is_labeled_and_linear_radius_normalized(analytic):
    mesh = radiation_mesh(analytic(), quantity="directivity")
    np.testing.assert_allclose(mesh["Directivity (dBi)"], 0, atol=0.001)
    np.testing.assert_allclose(mesh["Display radius"], 1)
    assert "Relative field (dB)" not in mesh.point_data
