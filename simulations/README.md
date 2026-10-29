# Reproduce the patch reference

For the larger **material wave lab**, run
`python simulations/run_material_lab.py --build --refine`. It archives eight
1 GHz material/structure cases in a 2.4 × 1.6 × 1 m domain, with an optional
air/concrete mesh check. Open the bundled results using
`python examples/through_wall.py --materials --browser` (port 8768).
The [material lab documentation](../docs/material-lab.rst) records the ITU
material-class coefficients, thin-sheet approximation and other assumptions.

For the separate, independently authored **through-wall field experiment**, run
`python simulations/run_through_wall.py --build`. It compares a fed dipole in
air, an assumed lossy dielectric wall, and a PEC wall, then performs a finer
air/dielectric sensitivity pair. Each accepted run must reach -60 dB residual
energy. See [the field experiment documentation](../docs/nearfield.rst).
View saved results with `python examples/through_wall.py --browser` on port 8767.
No solver is required for viewing the bundled sample.

Adapted from Thorsten Liebig's **Simple Patch Antenna** tutorial:
https://github.com/thliebig/openEMS/blob/53a426429809ade506828c0aadb550589a115ee5/matlab/Tutorials/Simple_Patch_Antenna.m

Upstream revision: `53a426429809ade506828c0aadb550589a115ee5`.
The Octave adaptation is GPL-3.0-or-later; see `licenses/GPL-3.0.txt`.
Original copyright notice is retained. Changes: headless execution, fixed output
paths, three selected frequencies, full-sphere angular grid, independent signed
principal-plane cuts, and CSV port output instead of interactive figures.
The script uses the packaged Debian solver, whose exact build is saved in the
result's metadata. The newer tutorial's geometry is compatible with this solver.
The Python exporter is independently written and uses h5py only during generation.

From the repository root, with Docker running:

```sh
mkdir -p data/raw
docker build -t pyvista-radiation-solver -f simulations/Dockerfile .
docker run --rm -v "$PWD:/work" pyvista-radiation-solver
docker run --rm -v "$PWD:/work" pyvista-radiation-solver python3 simulations/export_npz.py
python examples/preview.py
```

A solver run recreates `simulations/work/patch`. Do not use that directory for
other work. Large time-domain recordings stay there and are ignored by Git.
Small original NF2FF outputs in `data/raw/` are retained for auditing and independent
plot regeneration. The full sphere has theta 0:5:180°, phi 0:5:355° (37 × 72).
Independent cuts have signed theta −180:5:180°, phi 0° and 90°. Frequencies:
2.2, 2.4, 2.6 GHz. Fields are evaluated at r=1 m about center (0,0,1 mm).

Geometry: PEC patch 32 × 40 mm, 60 × 60 mm ground and substrate, substrate
thickness 1.524 mm, relative permittivity 3.38, conductivity corresponding to
loss tangent 0.001 at 2.45 GHz. Feed at x=−6 mm, z directed, 50 Ω.
Gaussian pulse centered at 2 GHz, 1 GHz corner; Mur boundaries, 200 × 200 × 150 mm
box, up to 30,000 timesteps. This is a tutorial reference, not a mesh-convergence
study or a measurement-validated antenna model. Solver log records termination.

The numerical outputs generated here are dedicated under CC0-1.0 (see
`data/LICENSE`). This does not relicense the tutorial or solver. No original
website screenshots or third-party plots are bundled. Reference figures are
newly rendered from our saved solver outputs.

## Sensitivity and source calibration review

`run_sensitivity.py` generates attributed Octave cases from the same geometry
recipe. Run it in the solver image, then `python examples/sensitivity_report.py`.
Results are in `data/sensitivity/`; generated GPL case sources are under
`simulations/sensitivity_sources/`. Logs and geometry show the actual time cap,
mesh and boundary positions for each run. The calibrated exchange dataset divides
the pulse Fourier spectrum out of fields and powers using the archived `et`
waveform, with factors recorded in `patch_reference.json`. Raw HDF5 outputs are
unchanged. This yields response to the tutorial's unit-amplitude temporal source envelope,
not unit incident power, gain or measurement validation.
