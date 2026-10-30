"""Generate reference plots and a standalone, rotatable PyVista HTML preview."""

import argparse
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pyvista as pv

from pyvista_radiation import load
from pyvista_radiation.display import preview_mesh

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show", action="store_true", help="also open native interactive window")
    args = parser.parse_args()
    data = load(ROOT / "data/patch_reference.npz")
    output = ROOT / "preview"
    output.mkdir(exist_ok=True)
    colors = ["#2870b5", "#bf4e20", "#167c68"]
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
    with np.load(ROOT / "data/reference_cuts.npz", allow_pickle=False) as cuts:
        fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout="constrained")
        for k, f in enumerate(data.frequency_hz):
            peak = data.field_magnitude[k].max()
            for plane, ax in enumerate(axes):
                ref = cuts["field_magnitude"][k, :, plane]
                relative = ref / peak if peak else np.zeros_like(ref)
                ax.plot(
                    np.rad2deg(cuts["theta_rad"]),
                    20 * np.log10(np.maximum(relative, 1e-2)),
                    color=colors[k],
                    label=f"{f / 1e9:.1f} GHz",
                )
        for ax, title in zip(axes, ["xz plane · φ = 0°", "yz plane · φ = 90°"]):
            ax.set(
                title=title,
                xlabel="Signed θ (degrees)",
                ylabel="Relative field (dB)",
                xlim=(-180, 180),
                ylim=(-40, 1),
                xticks=np.arange(-180, 181, 60),
            )
            ax.grid(alpha=0.2)
            ax.legend()
        fig.suptitle(
            "openEMS patch antenna / independent reference cuts\nEach frequency normalized to its own full-sphere field maximum",
            fontsize=14,
        )
        fig.savefig(output / "reference_cuts.png", dpi=180)
        plt.close(fig)
    port = np.loadtxt(ROOT / "data/raw/port.csv", delimiter=",")
    fig, axes = plt.subplots(1, 2, figsize=(13, 4), layout="constrained")
    axes[0].plot(
        port[:, 0] / 1e9, 20 * np.log10(np.maximum(np.hypot(port[:, 1], port[:, 2]), 1e-12))
    )
    axes[0].set(xlabel="Frequency (GHz)", ylabel="S11 (dB)", title="Input matching")
    axes[1].plot(port[:, 0] / 1e9, port[:, 3], label="Real")
    axes[1].plot(port[:, 0] / 1e9, port[:, 4], label="Imaginary")
    axes[1].set(xlabel="Frequency (GHz)", ylabel="Input impedance (Ω)", title="Feed impedance")
    axes[1].legend()
    for ax in axes:
        ax.grid(alpha=0.2)
    fig.savefig(output / "port_reference.png", dpi=180)
    plt.close(fig)
    plotter = pv.Plotter(shape=(1, 3), off_screen=not args.show, window_size=(1650, 700))
    for k, f in enumerate(data.frequency_hz):
        plotter.subplot(0, k)
        plotter.set_background("#101d2c")
        plotter.add_mesh(
            preview_mesh(data, k),
            scalars="Relative field (dB)",
            cmap="viridis",
            clim=(-40, 0),
            smooth_shading=True,
            scalar_bar_args={
                "title": f"{f / 1e9:.1f} GHz · relative field (dB)",
                "color": "white",
                "vertical": False,
                "position_y": 0.10,
                "position_x": 0.16,
                "width": 0.72,
                "title_font_size": 12,
                "label_font_size": 10,
            },
        )
        plotter.add_text(f"{f / 1e9:.1f} GHz", position=(15, 635), font_size=20, color="white")
        plotter.add_text(
            "openEMS · 32 × 40 mm patch\nRadius: field / peak (display only)",
            position=(15, 12),
            font_size=10,
            color="white",
        )
        plotter.add_axes(color="white")
        plotter.camera_position = [(2.4, -3.4, 2.2), (0, 0, 0.3), (0, 0, 1)]
        plotter.camera.zoom(0.85)
    plotter.link_views()
    plotter.screenshot(output / "radiation_patterns.png")
    plotter.trame.export_html(output / "radiation_patterns.html")
    # VTK.js does not export PyVista's 2D text actors. Supply HTML labels so
    # frequencies and normalization remain visible in the offline viewer.
    html_path = output / "radiation_patterns.html"
    headings = "".join(f"<div>{f / 1e9:.1f} GHz</div>" for f in data.frequency_hz)
    overlay = (
        "<style>.pattern-labels{position:fixed;inset:18px 0 auto;z-index:10;"
        "color:#fff;font-family:system-ui,sans-serif;pointer-events:none}"
        ".pattern-heading{display:grid;grid-template-columns:repeat(3,1fr);"
        "font-size:clamp(20px,3vw,38px)}.pattern-heading>div{padding-left:20px}"
        ".pattern-note{font-size:13px;margin:12px 20px;color:#c6d4df}</style>"
        '<header class="pattern-labels"><div class="pattern-heading">'
        + headings
        + '</div><p class="pattern-note">openEMS · 32 × 40 mm patch · '
        "Radius: field / peak at each frequency · Color: relative field, −40 to 0 dB"
        "<br>Drag to rotate · Scroll to zoom</p></header>"
    )
    html = html_path.read_text()
    html = html.replace(
        "<body>", '<body><div class="content" style="position:fixed;inset:0"></div>'
    )
    html = html.replace(
        "VTK.js | Example - OfflineLocalView", "Patch antenna | openEMS radiation patterns"
    )
    html_path.write_text(html.replace("</body>", overlay + "</body>"))
    if args.show:
        plotter.show()
    plotter.close()
    print("Preview:", output / "radiation_patterns.html")


if __name__ == "__main__":
    main()
