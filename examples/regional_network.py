"""Native PyVista example: a 7 km square landscape and five independent towers."""

import argparse
from pathlib import Path

import pyvista as pv

from pyvista_radiation import metro_towers, network_coverage, synthetic_environment
from pyvista_radiation.network import TOWER_COLORS
from pyvista_radiation.terrain_view import building_mesh, road_meshes, terrain_mesh, tower_mesh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot", type=Path, help="save an image instead of opening a window")
    parser.add_argument("--grid", type=int, default=101, help="samples per axis; 101 gives 70 m spacing")
    parser.add_argument("--map", choices=("received", "serving", "elevation"), default="received")
    parser.add_argument("--save-data", type=Path, help="optional network results NPZ")
    args = parser.parse_args()
    terrain, buildings = synthetic_environment("metro_network", nx=args.grid, ny=args.grid)
    towers = metro_towers()
    result = network_coverage(terrain, 2.4e9, towers, buildings=buildings)
    ground = terrain_mesh(terrain, result.strongest, quantity=args.map,
                          serving_index=result.serving_index)
    plotter = pv.Plotter(off_screen=args.screenshot is not None, window_size=(1600, 1100))
    plotter.set_background("#132d40")
    cmap = {"received": "viridis", "serving": list(TOWER_COLORS), "elevation": "gist_earth"}[args.map]
    clim = {"received": (-120, -40), "serving": (-0.5, 4.5),
            "elevation": (terrain.elevation_m.min(), terrain.elevation_m.max())}[args.map]
    plotter.add_mesh(ground, cmap=cmap, clim=clim, smooth_shading=True,
                     show_scalar_bar=args.map != "serving",
                     scalar_bar_args=dict(color="white", title_font_size=13, label_font_size=11,
                                          position_x=0.53, position_y=0.04, width=0.43, height=0.08))
    geometry = [building_mesh(buildings), *road_meshes(terrain, "metro_network")]
    plotter.add_mesh(geometry[0], color="#b4c4cb", show_edges=True, edge_color="#5b7585")
    for road in geometry[1:]:
        plotter.add_mesh(road, color="#364857", lighting=False)
    for i, (tower, link) in enumerate(zip(towers, result.links)):
        xyz = link.metadata["tx_xyz_m"]
        mast = tower_mesh(terrain, xyz)
        marker = pv.Sphere(radius=25, center=xyz)
        geometry.extend([mast, marker])
        plotter.add_mesh(mast, color="white", line_width=3)
        plotter.add_mesh(marker, color=TOWER_COLORS[i])
    plotter.add_legend([(t.name, c) for t, c in zip(towers, TOWER_COLORS)],
                       bcolor="#132d40", face="circle", size=(0.2, 0.18))
    plotter.add_text("7 × 7 km · five radio towers", position=(24, 1040), color="white", font_size=22)
    plotter.add_text(
        f"49 km² · {len(buildings)} buildings · 2.4 GHz\n"
        "Each tower: 60 m AGL, 40 dBm, omnidirectional 0 dBi reference\n"
        "Strongest independent link · approximate terrain/roof diffraction\n"
        "No interference, reflections or handover model",
        position=(24, 24), color="white", font_size=10,
    )
    plotter.camera_position = [(-6500, -7800, 6500), (0, 0, 250), (0, 0, 1)]
    plotter.enable_parallel_projection()
    plotter.camera.parallel_scale = 4400
    plotter.add_axes()
    if args.save_data:
        args.save_data.parent.mkdir(parents=True, exist_ok=True)
        result.save(args.save_data)
    if args.screenshot:
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
        plotter.screenshot(args.screenshot)
        print(args.screenshot.resolve())
    else:
        plotter.show()
    plotter.close()


if __name__ == "__main__":
    main()
