Actual through-wall fields
==========================

This example uses **actual three-dimensional openEMS FDTD fields**, displayed
in ordinary PyVista meshes. It is separate from the large synthetic city's
approximate coverage model. A saved sample is bundled, so viewing it requires
neither Docker nor an installed solver::

   pip install -e '.[browser]'
   python examples/through_wall.py --browser

The viewer opens on localhost port 8767. Choose air, a lossy dielectric wall, or
a perfect electric conductor. Field strength uses one shared air reference for
all three cases. Wave phase displays ``Re(Ez exp(j phase))``; **Play one cycle**
cycles the saved steady-state phasors. It is not a recording of pulse arrival.
Drag to rotate the slice and wall geometry; the zoom buttons retain the angle.

For native PyVista, without a listening server::

   python examples/through_wall.py
   python examples/through_wall.py --phase 90 --screenshot preview/through_wall_phase.png

Scene and physical meaning
--------------------------

The domain is 0.8 × 0.6 × 0.4 m. A 50 mm tall, fat PEC dipole at
(-0.22, 0, 0) m has 10 mm square arms, a 10 mm feed gap and a 50-ohm lumped port.
An 80 mm thick wall extends over y = ±0.2 m and z = ±0.12 m. The dielectric's
relative permittivity is 4 and conductivity is 0.03 S/m; these are illustrative
constants, **not measured concrete properties**. The third case replaces it
with a perfect conductor. No room, terrain or city propagation is implied.

All cases record complex vector E fields at 2.4 GHz on the horizontal z = 0
plane. The computation itself remains 3D. Receiver markers are at (-0.12,0,0)
and (0.2,0,0) m. The gold marker locates the dipole; cyan markers locate receivers.
The wall outline marks its finite extent.

The dielectric permits nonzero fields inside it. A perfect conductor has zero
internal electric field, but fields can still reach its far side around its
edges. Both cases include reflected waves. **Total field at a point can increase
relative to air because of interference.** Consequently the receiver ratio
``20 log10(|E_case| / |E_air|)`` is a total-field comparison, not an isolated
material penetration loss, receiver dBm, antenna gain or building coverage.

Calibration and reproducibility
-------------------------------

Each raw field phasor is divided by the complex incident-voltage spectrum from
``calcPort``. Saved values are V/m for a **1 V incident voltage wave at the
50-ohm feed**, not normalization to radiated power. A shared display reference
is the maximum baseline ``|E|`` on the saved plane outside a 30 mm source exclusion
radius. Magnitude colors clip to [-50,0] dB, and instantaneous Ez colors to
±0.25 of that reference. These bounds never alter the raw complex arrays.

The baseline grid is 5 mm with PML_8 on all six faces. The Gaussian source is
centered at 2.4 GHz with a 0.4 GHz corner. A run is accepted by the exporter only
when it completes and the reported residual energy reaches -60 dB; hitting the
timestep cap is rejected. A finer air/dielectric pair checks receiver ratios
with a maximum 4 mm mesh and extra lines at antenna boundaries. Actual grid
lines, warnings, solver version, logs and source hashes are retained. Two-grid
sensitivity does not establish full convergence or hardware accuracy.

In the bundled run the dielectric-versus-air field change differs by about
0.021 dB at the front receiver and 0.099 dB at the rear receiver between grids.
The rear field is about +2.4 dB versus air in this particular finite-wall setup;
the PEC control is about -15.6 dB. These are total-field values at specific
locations, not general attenuation values for a material.

Regenerate the solver data from the repository root::

   python simulations/run_through_wall.py --build

Docker must be running. This uses the existing pinned Debian solver image and
the actual installed openEMS version is recorded, rather than assuming it
matches the latest documentation. Intermediate files remain in a unique
``simulations/work/through_wall_*`` directory. The exporter archives small raw
HDF5 planes, XML geometry, feed spectra and run logs in ``data/through_wall``;
the compact viewing sample is packaged under ``pyvista_radiation/data``.
The numerical outputs are CC0; these independently authored scripts are MIT.

Library workflow
----------------

These Cartesian near fields have their own contract; they are not forced into
the angular far-field ``RadiationData`` format::

   import pyvista as pv
   from pyvista_radiation import load_through_wall, field_plane_mesh

   fields = load_through_wall()
   mesh = field_plane_mesh(fields, 'dielectric', mode='phase', phase_deg=90)
   plotter = pv.Plotter()
   plotter.add_mesh(mesh, cmap='RdBu_r', clim=(-0.25, 0.25), lighting=False)
   plotter.view_xy()
   plotter.show()

The returned object is a ``pyvista.StructuredGrid``. Point arrays preserve the
real and imaginary xyz field vectors in addition to display scalars. Save it as
VTS or use ordinary PyVista filters. ``FieldPlaneData`` stores fields ordered
(case, y, x, component_xyz); its version-1 NPZ format explicitly records metres,
Hz, V/m, source normalization and provenance. Loading requires NumPy only.

Validation checks include the air-case phase slope against the free-space
wavenumber, zero interior fields in the PEC control, nonzero interior fields in
the dielectric, complex-array/VTS round trips, shared amplitude references,
phase reconstruction, field-decay evidence and raw-file integrity. These
checks verify the experiment and data handling, not a measured wall material.

Primary references: `openEMS excitation and port concepts
<https://docs.openems.de/en/stable/concepts/excitations.html>`_,
`field dumps <https://docs.openems.de/en/stable/concepts/dump.html>`_, and
`material properties <https://docs.openems.de/en/latest/concepts/properties.html>`_.
