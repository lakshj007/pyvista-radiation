"""Regression checks on archived solver experiments; never run a solver in CI."""

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def test_fixed_window_excitation_linearity():
    folder = ROOT / "data/sensitivity"
    a = dict(np.load(folder / "fixed20.npz", allow_pickle=False))
    b = dict(np.load(folder / "fixed_double20.npz", allow_pickle=False))
    for field in ["e_theta", "e_phi"]:
        scale = np.max(abs(a[field]))
        np.testing.assert_allclose(b[field] / scale, 2 * a[field] / scale, rtol=1e-4, atol=1e-5)
    np.testing.assert_allclose(b["prad_raw"], 4 * a["prad_raw"], rtol=1e-4, atol=0)
    np.testing.assert_allclose(b["port"][:, 1:3], a["port"][:, 1:3], rtol=1e-4, atol=1e-5)


def test_sensitivity_report_records_limits():
    r = json.loads((ROOT / "data/sensitivity/report.json").read_text())
    assert r["double_excitation"]["meets_linearity_tolerance"]
    assert not r["refinement_meets_screening_criteria"]
    assert max(r["refinement_25_to_30"]["cut_rms_fraction"]) < 0.003
    for name in ["mur20", "mur25", "mur30", "pml20", "large20", "double20"]:
        assert r["cases"][name]["reached_decay_target"]
