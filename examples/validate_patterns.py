"""Regenerate numerical validation figures and a machine-readable error report."""

import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pyvista_radiation import (
    amplitude_db,
    directivity,
    load_patch,
    radiation_mesh,
    spherical_directions,
)

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT / "preview"
    out.mkdir(exist_ok=True)
    data = load_patch()
    report = {"cut_max_relative_amplitude_error": {}, "directivity_relative_error": {}}
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), layout="constrained")
    colors = ["#1574b8", "#cb5b32", "#16816b"]
    with np.load(ROOT / "data/reference_cuts.npz", allow_pickle=False) as ref:
        theta = ref["theta_rad"]
        for k, f in enumerate(data.frequency_hz):
            mesh = radiation_mesh(data, k, mode="sphere")
            peak = data.field_magnitude[k].max()
            for col, phi in enumerate((0, np.pi / 2)):
                requested = spherical_directions(np.abs(theta), [phi, phi + np.pi])
                vectors = np.array([requested[i, 0 if t >= 0 else 1] for i, t in enumerate(theta)])
                nearest = (vectors @ mesh["Direction"].T).argmax(axis=1)
                actual = mesh["Field magnitude (V/m)"][nearest] / peak
                original = ref["field_magnitude"][k, :, col] / peak
                error = actual - original
                report["cut_max_relative_amplitude_error"][f"{f / 1e9:g}GHz_{col}"] = float(
                    np.max(abs(error))
                )
                axes[0, col].plot(
                    np.rad2deg(theta),
                    amplitude_db(original),
                    color=colors[k],
                    label=f"{f / 1e9:g} GHz solver",
                )
                axes[0, col].plot(
                    np.rad2deg(theta)[::3], amplitude_db(actual)[::3], ".", color=colors[k], ms=3
                )
                axes[1, col].plot(np.rad2deg(theta), error, color=colors[k])
            report["directivity_relative_error"][f"{f / 1e9:g}GHz"] = float(
                directivity(data, k).max() / data.directivity_max[k] - 1
            )
    for col, plane in enumerate(("xz", "yz")):
        axes[0, col].set(
            title=f"{plane} plane: solver lines / mesh sample dots",
            ylabel="Relative field (dB)",
            ylim=(-40, 1),
        )
        axes[1, col].set(xlabel="Signed theta (degrees)", ylabel="Mesh − independent solver / peak")
        axes[0, col].legend()
        for row in range(2):
            axes[row, col].grid(alpha=0.2)
            axes[row, col].set_xlim(-180, 180)
    fig.suptitle("Saved openEMS reference validation · no solver run required")
    fig.savefig(out / "validation.png", dpi=160)
    plt.close(fig)
    # Show independent analytic targets used by tests and quadrature convergence.
    degrees = np.linspace(0, 180, 181)
    t = np.deg2rad(degrees)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    axes[0].plot(degrees, np.sin(t), label="Dipole: |E| = sin θ")
    axes[0].plot(degrees, 1.5 * np.sin(t) ** 2, label="Dipole: D = 1.5 sin² θ")
    axes[0].plot(degrees, np.ones_like(t), "--", label="Isotropic: D = 1")
    axes[0].set(xlabel="Theta (degrees)", ylabel="Linear ratio", title="Analytic angular targets")
    errors = []
    steps = [15, 10, 5, 2, 1]
    trap = getattr(np, "trapezoid", None) or np.trapz
    for step in steps:
        th = np.deg2rad(np.arange(0, 181, step))
        estimate = 2 / trap(np.sin(th) ** 3, th)
        errors.append(abs(estimate - 1.5))
    axes[1].loglog(steps, errors, "o-")
    axes[1].set(
        xlabel="Theta spacing (degrees)",
        ylabel="Absolute error in peak directivity",
        title="Dipole quadrature convergence",
    )
    axes[0].legend()
    for ax in axes:
        ax.grid(alpha=0.2)
    fig.savefig(out / "analytic_validation.png", dpi=160)
    plt.close(fig)
    report["dipole_peak_directivity_absolute_error"] = dict(
        zip(map(str, steps), map(float, errors))
    )
    (out / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    for name in ("validation.png", "analytic_validation.png"):
        (ROOT / "docs" / "_static" / name).write_bytes((out / name).read_bytes())
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
