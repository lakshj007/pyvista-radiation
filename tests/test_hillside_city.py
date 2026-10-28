import numpy as np
import pytest

from pyvista_radiation import coverage_map, synthetic_environment
from pyvista_radiation.environments import environment_roads
from pyvista_radiation.terrain import Building


def test_hillside_city_has_grounded_buildings_and_open_presets():
    t, buildings = synthetic_environment("hillside_city", nx=25, ny=19)
    again, other = synthetic_environment("hillside_city", nx=25, ny=19)
    np.testing.assert_array_equal(t.elevation_m, again.elevation_m)
    assert buildings == other
    assert 120 < len(buildings) < 300
    assert np.ptp(t.elevation_m) > 200
    assert np.ptp([b.base_m for b in buildings]) > 100
    assert max(b.roof_m - b.base_m for b in buildings) > 100
    for b in buildings:
        xx, yy = np.meshgrid(np.linspace(b.xmin, b.xmax, 9), np.linspace(b.ymin, b.ymax, 9))
        ground = t.sample(xx, yy)
        assert np.all(ground >= b.base_m)
        assert np.all(ground < b.roof_m)
    for x, y in ((-960, 0), (0, 0), (960, 0), (-480, 0), (900, 675), (900, -675)):
        assert not any(b.contains(x, y) for b in buildings)


def test_roads_do_not_cross_buildings_and_preserve_footprints_across_resolution():
    _, buildings = synthetic_environment("hillside_city", nx=25, ny=19)
    _, fine = synthetic_environment("hillside_city")
    assert [(b.xmin, b.xmax, b.ymin, b.ymax) for b in buildings] == [
        (b.xmin, b.xmax, b.ymin, b.ymax) for b in fine
    ]
    for b in buildings:
        for points, width in environment_roads("hillside_city"):
            expanded = Building(
                b.xmin - width / 2, b.xmax + width / 2, b.ymin - width / 2, b.ymax + width / 2, 0, 1
            )
            assert all(
                expanded.interval(start, end) is None for start, end in zip(points[:-1], points[1:])
            )
    assert not environment_roads("downtown")


def test_buildings_change_coverage_on_the_same_hilly_ground():
    t, buildings = synthetic_environment("hillside_city", nx=25, ny=19)
    bare = coverage_map(t, 2.4e9)
    urban = coverage_map(t, 2.4e9, buildings=buildings)
    raised = coverage_map(t, 2.4e9, buildings=buildings, tx_height_m=150)
    valid = urban.valid & bare.valid
    assert np.any(urban.diffraction_db[valid] > bare.diffraction_db[valid] + 1)
    assert np.any(abs(urban.received_dbm[valid] - raised.received_dbm[valid]) > 1)
    assert urban.building_mask.any() and np.isnan(urban.received_dbm[urban.building_mask]).all()


def test_roads_are_draped_on_terrain_and_display_scale_is_only_visual():
    pytest.importorskip("pyvista")
    from pyvista_radiation.terrain_view import road_meshes, terrain_mesh

    t, buildings = synthetic_environment("hillside_city", nx=25, ny=19)
    a, b = road_meshes(t, "hillside_city", 1), road_meshes(t, "hillside_city", 3)
    assert len(a) == 9
    for one, three in zip(a, b):
        np.testing.assert_allclose(one.points[:, :2], three.points[:, :2])
        np.testing.assert_allclose(one.points[:, 2] * 3, three.points[:, 2])
        np.testing.assert_allclose(
            one.points[:, 2], t.sample(one.points[:, 0], one.points[:, 1]) + 0.6
        )
    result = coverage_map(t, 2.4e9, buildings=buildings)
    before = result.received_dbm.copy()
    mesh = terrain_mesh(t, result, quantity="elevation")
    np.testing.assert_allclose(mesh["Ground elevation (m)"], t.elevation_m.ravel(order="F"))
    np.testing.assert_array_equal(result.received_dbm, before)
