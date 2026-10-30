"""Actual openEMS two-floor fields in native PyVista, including a recorded pulse."""

import argparse
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from pyvista_radiation.house_fields import load_house


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--port", type=int, default=8769)
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--case", choices=("open", "closed", "air"), default="open")
    parser.add_argument("--time-ns", type=float, default=24)
    args = parser.parse_args()
    if args.browser:
        from pyvista_radiation.house_view import serve_house

        serve_house(port=args.port)
        return
    import pyvista as pv

    from pyvista_radiation._house_scene import BACKGROUND, INK, add_labels, geometry_bounds
    from pyvista_radiation.house_fields import house_slice_mesh

    data = load_house()
    plotter = pv.Plotter(shape=(2, 2), off_screen=args.screenshot is not None, window_size=(1700, 1500))
    geometry = []
    recipe = data.metadata["recipe"]
    definition = next(c for c in recipe["cases"] if c["key"] == args.case)
    frame = int(np.argmin(abs(data.time_s[args.case] - args.time_ns * 1e-9)))
    actual_ns = data.time_s[args.case][frame] * 1e9
    configurations = [
        ("vertical", "pulse", f"3D cutaway · recorded pulse at {actual_ns:.2f} ns", "house"),
        ("vertical", "pulse", f"Vertical cut · recorded pulse at {actual_ns:.2f} ns", "section"),
        ("downstairs", "magnitude_db", "Downstairs · steady 500 MHz field", "floor"),
        ("upstairs", "magnitude_db", "Upstairs · steady 500 MHz field", "floor"),
    ]
    for i, (plane, mode, title, camera) in enumerate(configurations):
        plotter.subplot(i // 2, i % 2)
        plotter.set_background(BACKGROUND)
        mesh = house_slice_mesh(data, args.case, plane, mode=mode, frame=frame)
        geometry.append(mesh)
        plotter.add_mesh(mesh, lighting=False, scalars="Displayed field",
                         cmap="viridis" if mode == "magnitude_db" else "RdBu_r",
                         clim=(-60, 0) if mode == "magnitude_db" else (-.25, .25),
                         opacity=1.0 if mode == "magnitude_db" else [.95, .9, .8, .5, 0, .5, .8, .9, .95],
                         show_scalar_bar=i in (1, 3),
                         scalar_bar_args=dict(color=INK, title=("Steady |E| / air reference (dB)" if mode == "magnitude_db"
                                                     else "Recorded Ey / air pulse reference"),
                                              title_font_size=11, label_font_size=9,
                                              position_y=.035, height=.07))
        view = "house" if camera == "house" else plane
        for box in definition["boxes"]:
            bounds = geometry_bounds(box, view, {k: p.fixed_m for k, p in data.planes.items()})
            if bounds is None:
                continue
            geometry.append(pv.Box(bounds=bounds))
            color = "#bc9361" if box["material"] == "timber" else ("#b5c5cf" if view == "house" else "#526e7f")
            plotter.add_mesh(geometry[-1], color=color, show_edges=True,
                             edge_color=INK, line_width=1, lighting=view == "house")
        scene = SimpleNamespace(data=data, geometry=geometry, plotter=plotter)
        add_labels(scene)
        label_view = "vertical" if view == "house" else view
        for actor, label_plane, case in scene.label_actors:
            actor.SetVisibility(label_plane == label_view and (case is None or case == args.case))
        if plane == "vertical" or np.isclose(data.planes[plane].fixed_m, recipe["source_xyz_m"][2]):
            geometry.append(pv.Sphere(radius=.08, center=recipe["source_xyz_m"]))
            plotter.add_mesh(geometry[-1], color="#d99a10")
        for receiver in recipe["receiver_xyz_m"]:
            if plane != "vertical" and not np.isclose(data.planes[plane].fixed_m, receiver[2]):
                continue
            geometry.append(pv.Sphere(radius=.065, center=receiver))
            plotter.add_mesh(geometry[-1], color="#007d99")
        plotter.add_text(title, position=(20, 680), color=INK, font_size=14)
        plotter.add_text(definition["label"], position=(20, 645), color=INK, font_size=10)
        if camera == "house":
            plotter.camera_position = [(7, -8, 6.45), (0, 0, 2.7), (0, 0, 1)]
            scale = 4.1
        elif camera == "section":
            plotter.camera_position = [(0, -12, 2.7), (0, 0, 2.7), (0, 0, 1)]
            scale = 3.4
        else:
            z = data.planes[plane].fixed_m
            plotter.camera_position = [(0, 0, z + 12), (0, 0, z), (0, 1, 0)]
            scale = 2.7
        plotter.enable_parallel_projection()
        plotter.camera.parallel_scale = scale
        plotter.add_axes(color=INK)
    if args.screenshot:
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
        plotter.screenshot(args.screenshot)
        print(args.screenshot.resolve())
    else:
        plotter.show()
    plotter.close()


if __name__ == "__main__":
    main()
