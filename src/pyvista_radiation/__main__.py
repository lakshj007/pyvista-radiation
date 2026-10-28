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
    parser.add_argument(
        "--terrain", help="Local metric terrain NPZ; defaults to illustrative synthetic landscapes"
    )
    parser.add_argument(
        "--coverage", action="store_true", help="include the optional terrain/city propagation demo"
    )
    from .environments import ENVIRONMENTS

    parser.add_argument("--environment", choices=[key for key, _ in ENVIRONMENTS],
                        help="open the landscape demo with this initial environment")
    args = parser.parse_args()
    data = load(args.dataset) if args.dataset else load_patch()
    if args.native:
        from .plotting import compare_patterns

        viewer = compare_patterns(
            data, (0, len(data.frequency_hz) - 1), radial_scale="db", floor_db=-30
        )
        viewer.show()
    else:
        from .terrain import load_terrain
        from .webapp import serve

        serve(data, port=args.port, terrain=load_terrain(args.terrain) if args.terrain else None,
              coverage=args.coverage, environment=args.environment)


if __name__ == "__main__":
    main()
