"""Render the standalone example headlessly, with an optional recorded-pulse GIF."""

import argparse
import runpy
from pathlib import Path
from unittest.mock import patch

import pyvista as pv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot", type=Path, required=True)
    parser.add_argument("--gif", type=Path)
    args = parser.parse_args()
    pv.OFF_SCREEN = True
    with patch.object(pv.Plotter, "show"):
        demo = runpy.run_path(str(Path(__file__).with_name("plot_house_pulse.py")))
    plotter = demo["plotter"]
    try:
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
        plotter.screenshot(args.screenshot)
        if args.gif:
            from PIL import Image

            # One shared palette contains the scene and complete color bar.
            palette = Image.fromarray(plotter.screenshot()).resize((1008, 700)).convert("P", palette=Image.Palette.ADAPTIVE, colors=128)
            frames = []
            for time in demo["seconds"]:
                demo["set_time"](time * 1e9)
                plotter.render()
                frames.append(Image.fromarray(plotter.screenshot()).resize((1008, 700)).quantize(palette=palette, dither=Image.Dither.NONE))
            args.gif.parent.mkdir(parents=True, exist_ok=True)
            frames[0].save(args.gif, save_all=True, append_images=frames[1:], loop=0, duration=65,
                           optimize=False, disposal=2)
            print(f"Recorded movie: {len(frames)} original timestamps")
        print(args.screenshot.resolve())
    finally:
        plotter.close()


if __name__ == "__main__":
    main()
