"""Actual openEMS through-wall fields in native PyVista or the optional browser."""

import argparse
from pathlib import Path

from pyvista_radiation.nearfield import field_plane_mesh, load_material_lab, load_through_wall


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--materials", action="store_true", help="larger 1 GHz material comparison")
    parser.add_argument("--port", type=int)
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--phase", type=float, help="show an instantaneous Ez phase instead of magnitude")
    args = parser.parse_args()
    data = load_material_lab() if args.materials else load_through_wall()
    if args.browser:
        from pyvista_radiation.wall_view import serve_wall

        serve_wall(data, port=args.port or (8768 if args.materials else 8767))
        return
    import pyvista as pv

    from pyvista_radiation.wall_view import case_bounds, case_definitions

    columns = min(4, len(data.case_names))
    rows = (len(data.case_names) + columns - 1) // columns
    plotter = pv.Plotter(shape=(rows, columns), off_screen=args.screenshot is not None,
                         window_size=(600 * columns, 800 * rows))
    labels = {item["key"]: item["label"] for item in case_definitions(data)}
    geometry = []
    mode = "phase" if args.phase is not None else "magnitude_db"
    for i, case in enumerate(data.case_names):
        plotter.subplot(i // columns, i % columns)
        plotter.set_background("#132d40")
        mesh = field_plane_mesh(data, case, mode=mode, phase_deg=args.phase or 0)
        geometry.append(mesh)
        plotter.add_mesh(mesh, lighting=False, cmap="viridis" if mode == "magnitude_db" else "RdBu_r",
                         clim=(-50, 0) if mode == "magnitude_db" else (-0.25, 0.25),
                         show_scalar_bar=i == 1,
                         scalar_bar_args=dict(color="white", title_font_size=10, label_font_size=9,
                                              position_y=0.015, height=0.06))
        for bounds in case_bounds(data, case):
            box = pv.Box(bounds=bounds)
            geometry.append(box)
            plotter.add_mesh(box, color="white", opacity=0.1, show_edges=True, edge_color="white")
        span = data.x_m[-1] - data.x_m[0]
        source = pv.Sphere(radius=0.012 * span, center=data.metadata["source_xyz_m"])
        geometry.append(source)
        plotter.add_mesh(source, color="#ffc857")
        for receiver in data.metadata["receivers"]:
            marker = pv.Sphere(radius=0.009 * span, center=receiver["xyz_m"])
            geometry.append(marker)
            plotter.add_mesh(marker, color="#66d2e7")
        plotter.add_text(labels[case], position=(18, 735), font_size=14, color="white")
        plotter.add_text(f"Actual openEMS · {data.frequency_hz / 1e9:g} GHz · z = 0 slice", position=(18, 695), font_size=9, color="white")
        behind = data.metadata["receivers"][1]["change_vs_air_db"][i]
        plotter.add_text(f"Behind wall: {behind:+.1f} dB vs air\nTotal field; includes interference and edge diffraction",
                         position=(18, 80), font_size=9, color="white")
        plotter.view_xy()
        plotter.enable_parallel_projection()
        plotter.camera.parallel_scale = 0.72 * span
    plotter.link_views()
    if args.screenshot:
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
        plotter.screenshot(args.screenshot)
        print(args.screenshot.resolve())
    else:
        plotter.show()
    plotter.close()


if __name__ == "__main__":
    main()
