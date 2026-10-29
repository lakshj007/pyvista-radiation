import json

import numpy as np
import pytest

from pyvista_radiation import (
    Building,
    RadioTower,
    TerrainGrid,
    coverage_map,
    metro_towers,
    network_coverage,
    synthetic_environment,
)
from pyvista_radiation.terrain import path_profile


def flat():
    return TerrainGrid(np.linspace(-1000, 1000, 9), np.linspace(-500, 500, 5), np.zeros((5, 9)))


def test_network_chooses_nearest_free_space_link_and_not_power_sum(tmp_path):
    t = flat()
    towers = (RadioTower("West", -750, 0), RadioTower("East", 750, 0))
    result = network_coverage(t, 2.4e9, towers)
    assert result.serving_index[2, 1] == 1  # West site excluded locally; East still valid
    assert result.serving_index[2, 2] == 0
    assert result.serving_index[2, 6] == 1
    assert result.serving_index[2, 4] == 0  # exact tie picks first
    received = result.strongest.received_dbm[2, 4]
    expected = 40 - 20 * np.log10(4 * np.pi * np.hypot(750, 58) * 2.4e9 / 299792458)
    assert received == pytest.approx(expected)
    assert received == result.links[0].received_dbm[2, 4]  # no +3 dB power addition
    assert not result.strongest.received_dbm.flags.writeable
    assert not result.serving_index.flags.writeable
    assert "tx_xyz_m" not in result.strongest.metadata
    result.save(tmp_path / "network.npz")
    with np.load(tmp_path / "network.npz", allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved["serving_index"], result.serving_index)
        assert saved["per_tower_received_dbm"].shape == (2, 5, 9)
        assert json.loads(saved["metadata_json"].item())["towers"][1]["name"] == "East"


def test_one_tower_matches_single_link_and_building_masks_apply_to_network():
    t = flat()
    b = Building(-10, 10, -10, 10, 0, 80)
    tower = RadioTower("West", -750, 0, height_m=30, power_dbm=30)
    network = network_coverage(t, 2.4e9, [tower], buildings=(b,))
    single = coverage_map(t, 2.4e9, tx_xy=(-750, 0), buildings=(b,))
    np.testing.assert_array_equal(network.strongest.received_dbm, single.received_dbm)
    assert network.serving_index[2, 4] == -1
    assert not network.strongest.valid[2, 4]
    assert network.links[0].diffraction_db[2, 6] > 20


def test_antenna_null_is_valid_even_when_another_tower_is_masked(analytic):
    result = network_coverage(
        flat(), 1e9,
        [RadioTower("Local", 0, 0, height_m=2), RadioTower("West", -500, 0, height_m=2)],
        pattern=analytic("dipole"), pattern_index=0,
    )
    assert result.strongest.valid[2, 4]
    assert result.serving_index[2, 4] == 1
    assert np.isneginf(result.strongest.received_dbm[2, 4])
    assert result.strongest.valid[2, 6]
    assert result.serving_index[2, 6] == 0  # two nulls tie in input order


def test_blocked_near_tower_can_lose_to_far_clear_tower():
    t = flat()
    towers = (RadioTower("Near", -250, 0, height_m=30),
              RadioTower("Far", 750, 500, height_m=30))
    building = Building(-150, -100, -50, 50, 0, 100)
    clear = network_coverage(t, 2.4e9, towers)
    blocked = network_coverage(t, 2.4e9, towers, buildings=[building])
    assert clear.serving_index[2, 4] == 0
    assert blocked.serving_index[2, 4] == 1
    assert blocked.strongest.diffraction_db[2, 4] == blocked.links[1].diffraction_db[2, 4]


def test_accelerated_coverage_retains_exact_roof_crossings_in_all_directions():
    t = flat()
    buildings = (Building(-501, -499, -10, 10, 0, 80),
                 Building(100, 101, -100, 400, 0, 60),
                 Building(-900, -800, 400, 450, 0, 120))
    for tx in ((-750, 0), (750, 0), (0, -500)):
        result = coverage_map(t, 2.4e9, tx_xy=tx, buildings=buildings)
        for iy, ix in np.argwhere(result.valid):
            profile = path_profile(t, [*tx, 30], [t.x_m[ix], t.y_m[iy], 2],
                                   2.4e9, buildings=buildings)
            assert result.diffraction_db[iy, ix] == pytest.approx(profile.diffraction_db)
            assert result.line_of_sight[iy, ix] == profile.line_of_sight


def test_network_rejects_missing_duplicate_and_conflicting_transmitters():
    with pytest.raises(ValueError, match="at least one"):
        network_coverage(flat(), 2.4e9, [])
    with pytest.raises(ValueError, match="unique"):
        network_coverage(flat(), 2.4e9, [RadioTower("A", 0, 0)] * 2)
    with pytest.raises(ValueError, match="settings"):
        network_coverage(flat(), 2.4e9, [RadioTower("A", 0, 0)], tx_height_m=20)
    with pytest.raises(ValueError, match="positive"):
        RadioTower("A", 0, 0, height_m=0)
    with pytest.raises(ValueError, match="inside"):
        network_coverage(flat(), 2.4e9, [RadioTower("outside", 2000, 0)])


def test_regional_scene_is_7km_square_and_reserves_all_tower_sites():
    t, buildings = synthetic_environment("metro_network", nx=25, ny=25)
    again, other = synthetic_environment("metro_network", nx=25, ny=25)
    np.testing.assert_array_equal(t.elevation_m, again.elevation_m)
    assert buildings == other
    assert np.ptp(t.x_m) == np.ptp(t.y_m) == 7000
    assert np.ptp(t.elevation_m) > 600
    assert len(buildings) > 600
    for tower in metro_towers():
        assert not any(b.contains(tower.x_m, tower.y_m) for b in buildings)
    for b in buildings:
        xx, yy = np.meshgrid(np.linspace(b.xmin, b.xmax, 5), np.linspace(b.ymin, b.ymax, 5))
        assert np.all(t.sample(xx, yy) > b.base_m)
        assert np.all(t.sample(xx, yy) < b.roof_m)


def test_network_panel_reuses_calculations_for_map_controls_and_cleans_up(analytic, monkeypatch):
    pytest.importorskip("pyvista")
    pytest.importorskip("trame")
    from trame.app import get_server

    from pyvista_radiation import terrain_view

    monkeypatch.setattr(terrain_view, "synthetic_environment",
                        lambda kind, **_: synthetic_environment(kind, nx=17, ny=17))
    panel = terrain_view.TerrainPanel(get_server("regional-panel-test", client_type="vue3"),
                                     analytic(), initial_kind="metro_network")
    s = panel.server.state
    try:
        assert not s.terrain_error
        network = panel.network
        assert len(panel.tower_actor_names) == 15
        s.terrain_quantity = "serving"
        s.terrain_exaggeration = 3
        panel.calculate()
        assert not s.terrain_error
        assert panel.network is network
        assert panel.mesh.active_scalars_name == "Strongest tower (index)"
        np.testing.assert_array_equal(panel.mesh.points[:, 2],
                                      3 * panel.terrain.elevation_m.ravel(order="F"))
        s.terrain_network_view = "3"
        panel.calculate()
        assert not s.terrain_error
        assert panel.network is network and panel.result is network.links[3]
        assert s.terrain_quantity == "received"
        assert "Only tower D" in s.terrain_network_note
        s.terrain_kind = "flat"
        panel.calculate()
        assert not s.terrain_error
        assert len(panel.tower_actor_names) == 2
        assert "tower_4_halo" not in panel.plotter.actors
        assert s.terrain_network_note == ""
    finally:
        panel.plotter.close()
