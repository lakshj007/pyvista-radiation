"""Build a short-dipole analytic example from complex NumPy arrays.

Run: python examples/user_arrays.py [--screenshot preview/user_arrays.png]
"""

import argparse
from pathlib import Path

import numpy as np
import pyvista as pv

from pyvista_radiation import from_arrays, principal_cut, radiation_mesh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    theta = np.linspace(0, 180, 91)
    phi = np.arange(0, 360, 5)
    # A deliberately declared zero phase; magnitude in V/m at a 1 m radius.
    e_theta = np.broadcast_to(np.sin(np.deg2rad(theta))[:, None], (91, 72)).astype(complex)
    data = from_arrays(
        2.4e9,
        theta,
        phi,
        e_theta,
        reference_radius_m=1,
        source="Analytic short z-directed dipole",
        angle_unit="deg",
        kind="analytic",
        solver_version="not applicable",
    )
    mesh = radiation_mesh(data, quantity="directivity")
    angles, field_db = principal_cut(data, 0, plane="xz")
    print(f"Principal cut: {len(angles)} samples; peak {field_db.max():g} dB")
    plotter = pv.Plotter(off_screen=args.screenshot is not None)
    plotter.add_mesh(mesh, scalars="Directivity (dBi)", cmap="viridis")
    plotter.add_text("Analytic dipole · directivity, not gain", font_size=14)
    plotter.add_axes()
    if args.screenshot:
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
        plotter.screenshot(args.screenshot)
        plotter.close()
    else:
        plotter.show()


if __name__ == "__main__":
    main()
