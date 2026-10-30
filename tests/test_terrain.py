import numpy as np
import pytest

from pyvista_radiation.terrain import (
    TerrainGrid,
    coverage_map,
    free_space_loss,
    knife_edge_loss,
    load_terrain,
    path_profile,
    relative_pattern_gain,
    save_terrain,
    synthetic_terrain,
)


def test_bilinear_metric_surface_and_order():
    x = np.array([0.0, 10.0, 20.0])
    y = np.array([0.0, 5.0, 10.0])
    xx, yy = np.meshgrid(x, y)
    t = TerrainGrid(x, y, 2 * xx + 3 * yy)
    assert t.sample(7, 4) == pytest.approx(26)
    assert t.sample(20, 10) == pytest.approx(70)
    with pytest.raises(ValueError):
        t.sample(21, 5)
    assert not t.elevation_m.flags.writeable


def test_terrain_roundtrip_and_nodata(tmp_path):
    t = synthetic_terrain("ridge", nx=21, ny=17)
    save_terrain(tmp_path / "t.npz", t)
    a = load_terrain(tmp_path / "t.npz")
    np.testing.assert_array_equal(a.elevation_m, t.elevation_m)
    assert a.source == t.source
    with pytest.raises(ValueError):
        TerrainGrid([0, 1], [0, 1], [[0, np.nan], [0, 0]])
    np.savez(
        tmp_path / "bad.npz",
        x_m=[0, 1],
        y_m=[0, 1],
        elevation_m=np.zeros((2, 2)),
        metadata_json='{"schema_version":1,"horizontal_unit":"degrees","vertical_unit":"m"}',
    )
    with pytest.raises(ValueError):
        load_terrain(tmp_path / "bad.npz")


def test_p525_free_space_reference():
    assert free_space_loss(1000, 2.4e9) == pytest.approx(100.052008, abs=1e-5)
    assert free_space_loss(2000, 2.4e9) - free_space_loss(1000, 2.4e9) == pytest.approx(6.020599913)
    for d, f in [(0, 2.4e9), (100, -1), (np.nan, 2.4e9)]:
        with pytest.raises(ValueError):
            free_space_loss(d, f)


def test_p526_single_edge_reference():
    # Independent benchmark: an edge grazing the direct path gives ~6 dB.
    assert knife_edge_loss(0) == pytest.approx(6.032852, abs=1e-5)
    assert knife_edge_loss(-1) == 0
    assert knife_edge_loss(-0.78) == 0
    assert knife_edge_loss(2) > knife_edge_loss(1) > knife_edge_loss(0)


def test_exact_grazing_profile():
    t = TerrainGrid([0, 500, 1000], [-1, 1], np.array([[0, 10, 0], [0, 10, 0]]))
    p = path_profile(
        t, [0, 0, 10], [1000, 0, 10], 2.4e9, sample_spacing_m=500, effective_earth_radius_m=None
    )
    assert p.v[p.dominant_index] == pytest.approx(0)
    assert p.diffraction_db == pytest.approx(knife_edge_loss(0))
    assert p.line_of_sight  # grazing, but not Fresnel-clear


def test_ridge_obstructs_path_height_restores_clearance():
    t = synthetic_terrain("ridge", nx=41, ny=31)
    low = path_profile(
        t, [-800, 0, float(t.sample(-800, 0)) + 30], [800, 0, float(t.sample(800, 0)) + 2], 2.4e9
    )
    high = path_profile(
        t, [-800, 0, float(t.sample(-800, 0)) + 400], [800, 0, float(t.sample(800, 0)) + 2], 2.4e9
    )
    assert not low.line_of_sight and low.diffraction_db > 20
    assert high.line_of_sight and high.diffraction_db < low.diffraction_db


def test_frequency_and_profile_reciprocity():
    t = synthetic_terrain("ridge", nx=41, ny=31)
    a = [-800, 0, 30]
    b = [800, 0, 2]
    low = path_profile(t, a, b, 1e9)
    high = path_profile(t, a, b, 3e9)
    reverse = path_profile(t, b, a, 3e9)
    assert high.diffraction_db > low.diffraction_db
    assert reverse.diffraction_db == pytest.approx(high.diffraction_db, rel=1e-10)


def test_pattern_boresight_and_periodic_seam(analytic):
    d = analytic("dipole")
    # Rotating the dipole pattern's z null onto world +x must produce a null.
    assert relative_pattern_gain(d, 0, np.array([1.0, 0, 0])) < -100
    assert relative_pattern_gain(d, 0, np.array([0.0, 0, 1])) == pytest.approx(0, abs=0.01)
    a = relative_pattern_gain(d, 0, [1, 1e-9, 1], heading_deg=0)
    b = relative_pattern_gain(d, 0, [1, -1e-9, 1], heading_deg=0)
    assert a == pytest.approx(b, abs=1e-7)
    with pytest.raises(ValueError):
        relative_pattern_gain(d, 0, [0, 0, 0])


def test_coverage_link_budget_and_actual_terrain_effect():
    t = synthetic_terrain("ridge", nx=21, ny=17)
    a = coverage_map(t, 2.4e9, diffraction=True)
    b = coverage_map(t, 2.4e9, diffraction=False)
    j = np.argmin(abs(t.y_m))
    i = np.argmin(abs(t.x_m - 800))
    assert a.diffraction_db[j, i] > 20
    assert b.received_dbm[j, i] - a.received_dbm[j, i] == pytest.approx(a.diffraction_db[j, i])
    np.testing.assert_allclose(
        a.received_dbm[a.valid], 30 - a.free_space_db[a.valid] - a.diffraction_db[a.valid]
    )
    c = coverage_map(t, 2.4e9, tx_power_dbm=40)
    np.testing.assert_allclose(c.received_dbm[a.valid] - a.received_dbm[a.valid], 10)
    assert a.metadata["assumed_tx_peak_gain_dbi"] == 0


def test_coverage_frequency_validation_and_near_mask(analytic):
    t = synthetic_terrain("flat", nx=11, ny=9)
    with pytest.raises(ValueError):
        coverage_map(t, 2.4e9, pattern=analytic(), pattern_index=0)
    a = coverage_map(t, 2.4e9, tx_xy=(0, 0), min_distance_m=100)
    assert not a.valid[4, 5]
    assert np.isnan(a.received_dbm[4, 5])
    assert np.isfinite(a.received_dbm[a.valid]).all()


def test_exaggeration_only_changes_display_and_export(tmp_path):
    pytest.importorskip("pyvista")
    from pyvista_radiation.terrain_view import terrain_mesh

    t = synthetic_terrain("ridge", nx=11, ny=9)
    r = coverage_map(t, 2.4e9)
    original = r.received_dbm.copy()
    a = terrain_mesh(t, r, vertical_exaggeration=1)
    b = terrain_mesh(t, r, vertical_exaggeration=3)
    np.testing.assert_allclose(b.points[:, 2], 3 * a.points[:, 2])
    np.testing.assert_allclose(
        a["Estimated received power (dBm)"], b["Estimated received power (dBm)"]
    )
    np.testing.assert_array_equal(r.received_dbm, original)
    r.save(tmp_path / "coverage.npz")
    with np.load(tmp_path / "coverage.npz", allow_pickle=False) as z:
        np.testing.assert_array_equal(z["received_dbm"], original)
        np.testing.assert_array_equal(z["x_m"], t.x_m)
        np.testing.assert_array_equal(z["ground_elevation_m"], t.elevation_m)


def test_curvature_and_sampling_limits():
    t = TerrainGrid([0, 10000, 20000], [-1, 1], np.zeros((2, 3)))
    flat = path_profile(
        t, [0, 0, 2], [20000, 0, 2], 2.4e9, sample_spacing_m=1000, effective_earth_radius_m=None
    )
    curved = path_profile(t, [0, 0, 2], [20000, 0, 2], 2.4e9, sample_spacing_m=1000)
    assert flat.line_of_sight and not curved.line_of_sight
    assert curved.diffraction_db > flat.diffraction_db
    with pytest.raises(ValueError, match="8192"):
        path_profile(t, [0, 0, 2], [20000, 0, 2], 2.4e9, sample_spacing_m=0.1)


def test_asymmetric_pattern_seam_and_gain_bound(analytic):
    d = analytic("asymmetric")
    a = relative_pattern_gain(d, 0, [0, 1e-6, 1])
    b = relative_pattern_gain(d, 0, [0, -1e-6, 1])
    assert a == pytest.approx(b, abs=1e-8)
    assert a == pytest.approx(0, abs=1e-5)
    t = synthetic_terrain("flat", nx=5, ny=5)
    with pytest.raises(ValueError, match="exceeds"):
        coverage_map(t, 1e9, pattern=d, pattern_index=0, tx_peak_gain_dbi=100)


def test_terrain_panel_error_and_zero_pattern(analytic):
    pytest.importorskip("pyvista")
    pytest.importorskip("trame")
    from trame.app import get_server

    from pyvista_radiation.terrain_view import TerrainPanel

    server = get_server("terrain-test-error", client_type="vue3")
    terrain = synthetic_terrain("flat", nx=9, ny=7)
    panel = TerrainPanel(server, analytic(), terrain)
    try:
        before = panel.result
        server.state.terrain_peak_gain = 6
        panel.calculate()
        assert "exceeds" in server.state.terrain_error
        assert panel.result is before
    finally:
        panel.plotter.close()
    zero = TerrainPanel(
        get_server("terrain-test-zero", client_type="vue3"), analytic("zero"), terrain
    )
    try:
        assert zero.unavailable
        assert "nonzero" in zero.server.state.terrain_error
    finally:
        zero.plotter.close()
