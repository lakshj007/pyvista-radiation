"""Console entry point for saved results and the packaged sample."""

import argparse

from .model import load
from .samples import load_patch


def main():
    parser = argparse.ArgumentParser(
        description="Explore saved antenna radiation patterns in PyVista"
    )
    parser.add_argument("dataset", nargs="?", help="NPZ file; defaults to bundled openEMS patch")
    parser.add_argument(
        "--native", action="store_true", help="open native PyVista comparison window"
    )
    parser.add_argument(
        "--port", type=int, default=8766, help="localhost browser port (default 8766)"
    )
    args = parser.parse_args()
    data = load(args.dataset) if args.dataset else load_patch()
    if args.native:
        from .plotting import compare_patterns

        viewer = compare_patterns(
            data, (0, len(data.frequency_hz) - 1), radial_scale="db", floor_db=-30
        )
        viewer.show()
    else:
        from .webapp import serve

        serve(data, port=args.port)


if __name__ == "__main__":
    main()
