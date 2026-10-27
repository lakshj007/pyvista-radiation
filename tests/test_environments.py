import json

import numpy as np
import pytest

from pyvista_radiation import Building, TerrainGrid, coverage_map, synthetic_environment
from pyvista_radiation.terrain import path_profile


def flat():
    return TerrainGrid([0, 500, 1000], [-100, 0, 100], np.zeros((3, 3)))


def test_environment_scenes_and_reproducibility():
    for kind in ("valley", "rugged", "city", "downtown"):
        t, boxes = synthetic_environment(kind, nx=21, ny=17)
        again, more_boxes = synthetic_environment(kind, nx=21, ny=17)
        np.testing.assert_array_equal(t.elevation_m, again.elevation_m)
        assert boxes == more_boxes
        assert np.isfinite(t.elevation_m).all()
        if boxes:
            assert len(boxes) == 80
            assert all(not b.contains(0, 0) for b in boxes)
        else:
            assert np.ptp(t.elevation_m) > 100
    _, low = synthetic_environment("city")
    _, high = synthetic_environment("downtown")
    assert max(b.roof_m for b in high) > 100
    assert max(b.roof_m for b in low) < 25


def test_narrow_building_cannot_be_skipped_by_coarse_terrain_samples():
    t = flat()
    b = Building(401, 402, -20, 20, 0, 40)
    assert b.interval([0, 0], [1000, 0]) == pytest.approx((0.401, 0.402))
    assert b.interval([0, 50], [1000, 50]) is None
    clear = path_profile(t, [0, 0, 10], [1000, 0, 2], 2.4e9, sample_spacing_m=500)
    blocked = path_profile(t, [0, 0, 10], [1000, 0, 2], 2.4e9, sample_spacing_m=500, buildings=(b,))
    reverse = path_profile(t, [1000, 0, 2], [0, 0, 10], 2.4e9, sample_spacing_m=500, buildings=(b,))
    assert clear.line_of_sight and not blocked.line_of_sight
    assert blocked.diffraction_db > 25
    assert blocked.diffraction_db == pytest.approx(reverse.diffraction_db)
    assert blocked.obstruction_m.max() == 40
    assert blocked.terrain_m.max() == 0


def test_building_shadow_link_budget_footprint_mask_and_export(tmp_path):
    t = flat()
    b = Building(450, 550, -30, 30, 0, 40)
    result = coverage_map(t, 2.4e9, tx_xy=(0, 0), buildings=(b,))
    baseline = coverage_map(t, 2.4e9, tx_xy=(0, 0), buildings=(b,), diffraction=False)
    assert result.building_mask[1, 1] and not result.valid[1, 1]
    assert np.isnan(result.received_dbm[1, 1])
    assert result.valid[1, 2] and not result.line_of_sight[1, 2]
    assert baseline.received_dbm[1, 2] - result.received_dbm[1, 2] == pytest.approx(
        result.diffraction_db[1, 2]
    )
    result.save(tmp_path / "city.npz")
    with np.load(tmp_path / "city.npz", allow_pickle=False) as z:
        assert z["building_mask"][1, 1]
        assert json.loads(z["metadata_json"].item())["buildings"][0]["roof_m"] == 40
    with pytest.raises(ValueError, match="transmitter"):
        coverage_map(t, 2.4e9, tx_xy=(500, 0), buildings=(b,))
    # A transmitter above a roof is supported by the numerical API; heights
    # remain relative to ground, never implicitly relative to the roof.
    rooftop = coverage_map(t, 2.4e9, tx_xy=(500, 0), tx_height_m=50, buildings=(b,))
    assert rooftop.valid.any()


def test_building_height_and_clear_street_paths():
    t = flat()
    b = Building(450, 550, -20, 20, 0, 40)
    low = path_profile(t, [0, 0, 10], [1000, 0, 2], 2.4e9, buildings=(b,))
    high = path_profile(t, [0, 0, 100], [1000, 0, 2], 2.4e9, buildings=(b,))
    street = path_profile(t, [0, 50, 10], [1000, 50, 2], 2.4e9, buildings=(b,))
    assert not low.line_of_sight and high.line_of_sight and street.line_of_sight
    assert high.diffraction_db < low.diffraction_db
    with pytest.raises(ValueError):
        Building(1, 0, 0, 1, 0, 10)


def test_building_display_scale_does_not_change_geometry_model():
    pytest.importorskip("pyvista")
    from pyvista_radiation.terrain_view import building_mesh

    b = Building(10, 20, 30, 40, 5, 50)
    a = building_mesh((b,), 1)
    c = building_mesh((b,), 3)
    np.testing.assert_allclose(c.points[:, :2], a.points[:, :2])
    np.testing.assert_allclose(c.points[:, 2], 3 * a.points[:, 2])
    assert b.roof_m == 50


def test_panel_switches_city_landscape_and_outdoor_positions(analytic, monkeypatch):
    pytest.importorskip("pyvista")
    pytest.importorskip("trame")
    from trame.app import get_server

    from pyvista_radiation import terrain_view

    monkeypatch.setattr(terrain_view, "synthetic_environment",
                        lambda kind: synthetic_environment(kind, nx=17, ny=13))
    panel = terrain_view.TerrainPanel(get_server("city-switch-test", client_type="vue3"), analytic())

    class View:
        cameras = 0

        def update(self):
            pass

        def update_camera(self):
            self.cameras += 1

    panel.view = View()
    s = panel.server.state
    try:
        s.terrain_kind = "downtown"
        for position, receiver in (("west", "north"), ("center", "far"), ("east", "south")):
            s.terrain_position, s.terrain_receiver = position, receiver
            panel.calculate()
            assert not s.terrain_error
            assert len(panel.buildings) == 80
            assert "buildings" in panel.plotter.actors
            assert panel.result.building_mask.any()
        assert panel.view.cameras == 1  # auto-frame on scene change, keep camera on other edits
        s.terrain_kind = "rugged"
        panel.calculate()
        assert not s.terrain_error
        assert not panel.buildings and "buildings" not in panel.plotter.actors
        assert not panel.result.building_mask.any()
        assert panel.view.cameras == 2
    finally:
        panel.plotter.close()
