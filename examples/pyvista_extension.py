"""Use the extension in a normal PyVista scene; no browser or solver required.

Run interactively: python examples/pyvista_extension.py
Headless artifact: python examples/pyvista_extension.py --screenshot preview/pyvista_extension.png
"""

import argparse
from pathlib import Path

import pyvista as pv

from pyvista_radiation import load_patch, radiation_mesh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    data = load_patch()
    plotter = pv.Plotter(
        shape=(1, 3), off_screen=args.screenshot is not None, window_size=(1500, 650)
    )
    meshes = [radiation_mesh(data, 1, mode="sphere", floor_db=-30)]
    for panel, title in enumerate(
        ("Native PolyData", "Your PyVista Plotter", "Standard clip filter")
    ):
        plotter.subplot(0, panel)
        plotter.set_background("#132d40")
        if panel == 0:
            plotter.add_mesh(
                meshes[0],
                scalars="Relative field (dB)",
                cmap="viridis",
                clim=(-30, 0),
                show_scalar_bar=False,
                smooth_shading=True,
            )
        elif panel == 1:
            actor = plotter.radiation.add_pattern(
                data, index=0, radial_scale="db", floor_db=-30, show_scalar_bar=False
            )
            # Actor, camera and color limits survive a frequency change.
            meshes.append(plotter.radiation.set_frequency(actor, 1))
        else:
            meshes.append(meshes[1].clip(normal="x", origin=(0, 0, 0)))
            plotter.add_mesh(
                meshes[2],
                scalars="Relative field (dB)",
                cmap="viridis",
                clim=(-30, 0),
                show_scalar_bar=False,
                smooth_shading=True,
            )
        plotter.add_text(title, position=(18, 595), font_size=17, color="white")
        plotter.add_text(
            "2.4 GHz · saved openEMS patch\nColor: relative field, -30 to 0 dB\nRadius is a display scale, not metres",
            position=(18, 30),
            font_size=10,
            color="white",
        )
        plotter.add_axes(color="white", viewport=(0.02, 0.2, 0.17, 0.35))
        plotter.camera_position = [(2.7, -3.8, 2.3), (0, 0, 0), (0, 0, 1)]
        plotter.camera.parallel_projection = True
        plotter.camera.parallel_scale = 1.45
    plotter.link_views()
    if args.screenshot:
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
        plotter.screenshot(args.screenshot)
        meshes[1].save(args.screenshot.with_suffix(".vtp"))
        plotter.close()
        print(args.screenshot.resolve())
    else:
        plotter.show()


if __name__ == "__main__":
    main()
