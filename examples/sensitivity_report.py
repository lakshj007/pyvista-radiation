"""Analyze recorded controlled solver checks. Does not launch the solver."""

import json
import re
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pyvista_radiation import half_power_beamwidth

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT / "data/sensitivity"
    manifest = json.loads((folder / "manifest.json").read_text())
    cases = {c["name"]: c for c in manifest["cases"]}
    loaded = {name: dict(np.load(folder / f"{name}.npz", allow_pickle=False)) for name in cases}
    norm = {}
    power = {}
    report = {
        "cases": {},
        "criteria": {
            "cut_rms_fraction": 0.01,
            "s11_complex_change": 0.02,
            "plane_peak_directivity_db_change": 0.1,
        },
    }
    for name, values in loaded.items():
        e = np.hypot(abs(values["e_theta"]), abs(values["e_phi"]))
        norm[name] = e / e.max(axis=(1, 2))[:, None, None]
        port = values["port"]
        spectrum = port[:, 5] + 1j * port[:, 6]
        power[name] = values["prad_raw"] / abs(spectrum * cases[name]["amplitude"]) ** 2
        report["cases"][name] = dict(
            s11_db=(20 * np.log10(abs(port[:, 1] + 1j * port[:, 2]))).tolist(),
            plane_peak_directivity_dbi=(10 * np.log10(values["dmax_planes"])).tolist(),
            radiated_power_unit_drive_w=power[name].tolist(),
            radiation_efficiency=(values["prad_raw"] / port[:, 4]).tolist(),
            reached_decay_target=None
            if cases[name].get("fixed_steps")
            else "Warning: Max." not in (folder / f"{name}.log").read_text(),
            beamwidth_xz_deg=[
                half_power_beamwidth(
                    np.rad2deg(values["theta_rad"]), 20 * np.log10(np.maximum(a[:, 0], 1e-15))
                )["width_deg"]
                for a in norm[name]
            ],
        )

    def compare(a, b):
        va, vb = loaded[a], loaded[b]
        return dict(
            cut_rms_fraction=np.sqrt(np.mean((norm[b] - norm[a]) ** 2, axis=(1, 2))).tolist(),
            max_cut_fraction=np.max(abs(norm[b] - norm[a]), axis=(1, 2)).tolist(),
            s11_complex_change=abs(
                (vb["port"][:, 1] + 1j * vb["port"][:, 2])
                - (va["port"][:, 1] + 1j * va["port"][:, 2])
            ).tolist(),
            plane_peak_directivity_db_change=abs(
                10 * np.log10(vb["dmax_planes"] / va["dmax_planes"])
            ).tolist(),
        )

    report["refinement_20_to_25"] = compare("mur20", "mur25")
    report["refinement_25_to_30"] = compare("mur25", "mur30")
    report["boundary_mur_to_pml"] = compare("mur20", "pml20")
    report["box_1_to_1_5"] = compare("mur20", "large20")
    newest = report["refinement_25_to_30"]
    report["refinement_meets_screening_criteria"] = all(
        max(newest[key]) <= limit for key, limit in report["criteria"].items()
    )
    counts = {
        name: int(re.search(r"Time for (\d+) iterations", (folder / f"{name}.log").read_text())[1])
        for name in ("fixed20", "fixed_double20")
    }
    if set(counts.values()) != {60000}:
        raise ValueError("Linearity controls must both complete exactly 60000 iterations")
    report["fixed_control_iteration_counts"] = counts
    base, twice = loaded["fixed20"], loaded["fixed_double20"]
    raw = np.hypot(abs(base["e_theta"]), abs(base["e_phi"]))
    raw2 = np.hypot(abs(twice["e_theta"]), abs(twice["e_phi"]))
    report["double_excitation"] = dict(
        max_relative_field_linearity_error=float(np.max(abs(raw2 - 2 * raw)) / np.max(2 * raw)),
        max_relative_power_linearity_error=float(
            np.max(abs(twice["prad_raw"] / base["prad_raw"] / 4 - 1))
        ),
        max_s11_complex_change=float(
            np.max(
                abs(
                    (base["port"][:, 1] + 1j * base["port"][:, 2])
                    - (twice["port"][:, 1] + 1j * twice["port"][:, 2])
                )
            )
        ),
        max_unit_drive_power_relative_error=float(
            np.max(abs(power["fixed_double20"] / power["fixed20"] - 1))
        ),
    )
    report["double_excitation"]["window_steps"] = 60000
    report["double_excitation"]["meets_linearity_tolerance"] = all(
        value < 1e-4
        for key, value in report["double_excitation"].items()
        if key not in ("window_steps",)
    )
    fig, axes = plt.subplots(1, 3, figsize=(15, 4), layout="constrained")
    freq = np.array([2.2, 2.4, 2.6])
    for name, c in cases.items():
        if c.get("fixed_steps"):
            continue
        axes[0].plot(freq, report["cases"][name]["s11_db"], "o-", label=name)
        axes[1].plot(freq, report["cases"][name]["beamwidth_xz_deg"], "o-")
        axes[2].plot(
            np.rad2deg(loaded[name]["theta_rad"]),
            20 * np.log10(np.maximum(norm[name][1, :, 0], 0.001)),
            label=name,
        )
    axes[0].set(xlabel="Frequency (GHz)", ylabel="S11 (dB)", title="Feed matching sensitivity")
    axes[1].set(
        xlabel="Frequency (GHz)",
        ylabel="xz half-power width (degrees)",
        title="Main-lobe width sensitivity",
    )
    axes[2].set(
        xlabel="Signed theta (degrees)",
        ylabel="Relative field (dB)",
        title="2.4 GHz xz cut",
        ylim=(-40, 1),
    )
    axes[0].legend(fontsize=8)
    for ax in axes:
        ax.grid(alpha=0.2)
    fig.savefig(ROOT / "preview/sensitivity.png", dpi=160)
    plt.close(fig)
    (folder / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
