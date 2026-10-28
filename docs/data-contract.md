# Radiation NPZ contract, version 1

`load(path)` returns `RadiationData`. The core package requires only NumPy; loading
never imports openEMS, CSXCAD, PyVista, h5py, or pickle. `save(path, data)` writes
compressed NPZ. No fields are normalized on import or export.

| NPZ key | Shape / type | Meaning |
|---|---|---|
| `frequency_hz` | `(F,)` real | Positive, strictly increasing frequencies in Hz |
| `theta_rad` | `(T,)` real | Strictly increasing polar angle, 0 to π inclusive |
| `phi_rad` | `(P,)` real | Strictly increasing azimuth, [0, 2π); no duplicate endpoint |
| `e_theta`, `e_phi` | `(F,T,P)` complex | Original transverse electric fields, V/m at reference radius |
| `radiated_power_w` | optional `(F,)` real | Nonnegative total radiated power, W |
| `directivity_max` | optional `(F,)` real | Peak directivity, linear ratio ≥1 |
| `metadata_json` | scalar Unicode | JSON object described below |

All numbers must be finite. Axes must be nonempty. Array ordering is always
frequency, theta, phi: `e_theta[k, i, j]` refers to frequency k, theta i, phi j.
Complex components must retain their phase. Real amplitude-only or arbitrarily
normalized input is unsupported in version 1. Both optional quantities may be
absent; no power or directivity is inferred by the loader.

Angles use a right-handed coordinate system: θ from +z, φ from +x towards +y.
Direction = `(sinθ cosφ, sinθ sinφ, cosθ)`. The theta basis is
`(cosθ cosφ, cosθ sinφ, −sinθ)`; the phi basis is `(−sinφ, cosφ, 0)`.
Component values at poles may depend on φ because the basis rotates. Full-sphere
coverage is required by the example preview but not by the data model.

## Required metadata

```json
{
  "schema_version": 1,
  "angle_convention": "theta_from_+z_phi_from_+x_toward_+y",
  "angle_unit": "rad",
  "frequency_unit": "Hz",
  "field_unit": "V/m",
  "array_order": ["frequency", "theta", "phi"],
  "reference_radius_m": 1.0,
  "normalization": "none",
  "provenance": {
    "kind": "simulation",
    "source": "source identifier or citation",
    "generator": "reproduction command or script",
    "solver_version": "exact solver build"
  }
}
```

`kind` may also be `analytic`, with solver_version `not applicable`.
The `from_arrays` and `load_csv` adapters construct this same contract from
explicitly declared complex V/m samples. They convert selected degree angles
to radians and validate/remove an agreeing duplicate phi endpoint. They do not
infer phase, physical units, normalization, gain or source calibration.
Unknown schema versions, conventions, units, order, normalization and archive
keys fail clearly with `ValueError`. Additional JSON metadata is preserved.
Record antenna parameters, phase center, solver settings, generation date,
upstream revision, attribution and raw-file checksums in provenance.
The convention for a solver's time phasor is retained in its original complex
values; this package currently compares magnitudes, not cross-solver phases.

## Physical values and display values

`field_magnitude` = `sqrt(abs(e_theta)**2 + abs(e_phi)**2)`, in V/m.
The preview radius is field magnitude divided by that frequency's sampled peak.
Color = `20 log10(field / peak)`, clipped to −40 dB for display only.
Zero fields display at the floor. No display floor is written back to the data.
Every frequency uses its own peak: this compares pattern shapes, not absolute
field strength, gain, efficiency or power across frequencies. Directivity and
power are retained exactly as reported by the solver and are not preview labels.

## Example

```python
from pyvista_radiation import load, save
pattern = load('data/patch_reference.npz')
print(pattern.frequency_hz, pattern.e_theta.shape)
print(pattern.metadata['provenance'])
save('copy.npz', pattern)
```

The bundled patch exchange data is calibrated to the tutorial's unit-amplitude temporal source envelope by dividing its pulse Fourier spectrum out of fields and powers. Original raw Fourier arrays remain in `data/raw/`; calibration factors and the waveform are archived. `normalization: none` means no display normalization; physical source calibration is recorded separately in provenance.
