from pathlib import Path

import numpy as np

from pyvista_radiation import load_patch


def test_recorded_excitation_calibration():
    root = Path(__file__).resolve().parents[1]
    d = load_patch()
    signal = np.loadtxt(root / "data/raw/excitation.csv")
    spectrum = (
        2
        * (signal[1, 0] - signal[0, 0])
        * np.array(
            [np.sum(signal[:, 1] * np.exp(-2j * np.pi * f * signal[:, 0])) for f in d.frequency_hz]
        )
    )
    c = d.metadata["provenance"]["calibration"]
    np.testing.assert_allclose(
        spectrum,
        np.array(c["spectrum_seconds_real"]) + 1j * np.array(c["spectrum_seconds_imag"]),
        rtol=1e-12,
    )
    assert d.metadata["normalization"] == "none"
    assert d.metadata["field_unit"] == "V/m"
