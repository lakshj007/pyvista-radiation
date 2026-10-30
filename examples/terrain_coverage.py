"""Generate a reproducible illustrative terrain coverage comparison."""

import json
from pathlib import Path

import numpy as np
import pyvista as pv

from pyvista_radiation import load_patch
from pyvista_radiation.terrain import coverage_map, synthetic_terrain
from pyvista_radiation.terrain_view import terrain_mesh

ROOT = Path(__file__).resolve().parents[1]


def main():
    terrain = synthetic_terrain("mountains")
    data = load_patch()
    kwargs = dict(pattern=data, pattern_index=1)
    actual = coverage_map(terrain, 2.4e9, **kwargs)
    baseline = coverage_map(terrain, 2.4e9, diffraction=False, **kwargs)
    out = ROOT / "preview"
    out.mkdir(exist_ok=True)
    actual.save(out / "terrain_coverage.npz")
    plotter = pv.Plotter(shape=(1, 3), off_screen=True, window_size=(1650, 650))
    for panel, (result, quantity, title) in enumerate(
        [
            (baseline, "received", "Obstruction loss disabled"),
            (actual, "received", "Terrain diffraction included"),
            (actual, "diffraction", "Added dominant-edge loss"),
        ]
    ):
        plotter.subplot(0, panel)
        plotter.set_background("#132d40")
        mesh = terrain_mesh(terrain, result, quantity=quantity, vertical_exaggeration=3)
        clim, cmap = ((-120, -40), "viridis") if quantity == "received" else ((0, 50), "magma")
        plotter.add_mesh(
            mesh,
            scalars=mesh.active_scalars_name,
            cmap=cmap,
            clim=clim,
            scalar_bar_args={
                "title": (
                    f"Panel {panel + 1}: received power (dBm)"
                    if quantity == "received"
                    else "Additional loss (dB)"
                ),
                "color": "white",
                "vertical": False,
                "position_x": 0.15,
                "position_y": 0.13,
                "width": 0.72,
                "label_font_size": 10,
                "title_font_size": 11,
            },
        )
        plotter.add_text(title, position=(12, 610), font_size=14, color="white")
        plotter.add_text(
            "Synthetic mountains · 2.4 GHz\nTx 30 dBm · assumed peak gain 0 dBi\nHeights: Tx 30 m / Rx 2 m AGL\nApproximate model · vertical display ×3",
            position=(12, 12),
            font_size=9,
            color="white",
        )
        tx = np.array(actual.metadata["tx_xyz_m"])
        tx[2] *= 3
        plotter.add_mesh(pv.Sphere(radius=35, center=tx), color="#ffdb76")
        plotter.camera_position = [(0, -6600, 5100), (0, 0, 150), (0, 0, 1)]
        plotter.camera.parallel_projection = True
        plotter.camera.parallel_scale = 3900
    plotter.link_views()
    plotter.screenshot(out / "terrain_coverage.png")
    plotter.close()
    report = dict(
        metadata=actual.metadata,
        blocked_fraction=float(np.mean(~actual.line_of_sight[actual.valid])),
        covered_fraction_above_minus90_dbm=float(np.mean(actual.received_dbm[actual.valid] >= -90)),
        maximum_added_loss_db=float(np.nanmax(actual.diffraction_db)),
        large_angle_fraction=float(np.mean(actual.large_angle[actual.valid])),
    )
    (out / "terrain_coverage.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
