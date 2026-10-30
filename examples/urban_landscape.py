"""Render the PyVista hillside-city showcase without starting a browser server."""

import argparse
from pathlib import Path

from trame.app import get_server

from pyvista_radiation import load_patch
from pyvista_radiation.terrain_view import TerrainPanel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot", type=Path, default=Path("preview/urban_landscape.png"))
    args = parser.parse_args()
    panel = TerrainPanel(
        get_server("hillside-example", client_type="vue3"),
        load_patch(),
        initial_kind="hillside_city",
    )
    p = panel.plotter
    p.window_size = (1400, 900)
    p.add_text("Urban radio playground", position="upper_left", color="white", font_size=22)
    p.add_text(
        "Synthetic hills, valley & neighborhoods · 2.4 GHz\n"
        "Ground colors: estimated reception · gold marker: transmitter\n"
        "Approximate terrain/roof diffraction · roads are visual context",
        position="lower_left",
        color="white",
        font_size=11,
    )
    p.add_scalar_bar(
        "Estimated received power (dBm)",
        mapper=panel.actor.mapper,
        color="white",
        vertical=False,
        position_x=0.55,
        position_y=0.05,
        width=0.4,
        title_font_size=12,
        label_font_size=10,
    )
    args.screenshot.parent.mkdir(parents=True, exist_ok=True)
    p.screenshot(args.screenshot)
    p.close()
    print(args.screenshot.resolve())


if __name__ == "__main__":
    main()
