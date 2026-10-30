import pytest

pytest.importorskip("trame")
pytest.importorskip("pyvista")

from pyvista_radiation import synthetic_terrain
from pyvista_radiation.webapp import create_app


@pytest.mark.parametrize("coverage", [False, True])
def test_browser_demo_keeps_propagation_optional(analytic, coverage):
    kwargs = dict(coverage=coverage)
    if coverage:
        kwargs["terrain"] = synthetic_terrain("flat", nx=9, ny=7)
    server, viewer = create_app(analytic(), server_name=f"extension-demo-{coverage}", **kwargs)
    try:
        assert (server._terrain_panel is not None) == coverage
        assert len(viewer.meshes) == 2
        assert "PyVista extension" in server.state.trame__title
    finally:
        viewer.close()
        server._difference_plotter.close()
        if server._terrain_panel is not None:
            server._terrain_panel.plotter.close()


def test_environment_opens_the_city_showcase_without_coverage_flag(analytic, monkeypatch):
    from pyvista_radiation import terrain_view
    from pyvista_radiation.environments import synthetic_environment

    monkeypatch.setattr(terrain_view, "synthetic_environment",
                        lambda kind: synthetic_environment(kind,nx=17,ny=13))
    server, viewer = create_app(analytic(), server_name="hillside-showcase-test",
                                environment="hillside_city")
    panel = server._terrain_panel
    try:
        assert panel is not None and not server.state.terrain_error
        assert server.state.terrain_kind == "hillside_city"
        assert server.state.terrain_exaggeration == 1
        assert len(panel.buildings) > 100
        assert len(panel.context_actor_names) == 9
        assert panel.mesh.active_scalars_name == "Estimated received power (dBm)"
        old = panel.result
        camera = tuple(panel.plotter.camera.position)
        panel.plotter.camera.azimuth += 45
        panel.reset_view()
        assert panel.result is old
        assert tuple(panel.plotter.camera.position) == camera
        server.state.terrain_kind = "flat"
        panel.calculate()
        assert not panel.context_actor_names and not panel.buildings
    finally:
        viewer.close()
        server._difference_plotter.close()
        panel.plotter.close()
