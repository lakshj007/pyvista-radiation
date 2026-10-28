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
