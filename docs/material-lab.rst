Larger material wave lab
========================

This is a second **actual openEMS full-wave example**, with a 2.4 × 1.6 × 1 m
domain: 20 times the volume of the original through-wall experiment. It runs
at 1 GHz, using a 120 mm numerical dipole, three receiver positions and a
finite 1 m wide × 0.6 m high sample. It is a free-space material experiment,
not a furnished room or a city model.

View the bundled solver output without installing or running openEMS::

   python examples/through_wall.py --materials --browser

The separate viewer uses localhost port 8768. The original small experiment
remains on port 8767. Native PyVista and screenshot workflows are also available::

   python examples/through_wall.py --materials
   python examples/through_wall.py --materials --phase 90 --screenshot preview/material_lab.png

Cases
-----

The first case is the common air baseline. Four equal-thickness 120 mm slabs
use material-class examples from **ITU-R P.2040-4 (2025), Table 3** evaluated
at the 1 GHz recording frequency:

============  =====================  ==================
Material      Relative permittivity   Conductivity (S/m)
============  =====================  ==================
Wood          1.99                   0.0047
Glass         6.31                   0.0036
Brick         3.91                   0.0238
Concrete      5.24                   0.0462
============  =====================  ==================

These are reference examples for material classes, not measured products or
universal properties for every wood, glass or concrete. The published model
uses frequency in GHz. Values here are held constant over the pulse band,
so this experiment does not implement broadband dielectric dispersion.

Three additional cases explore different openEMS capabilities:

* **Glass / air / glass:** two 20 mm glass panes separated by an 80 mm air gap.
  The geometry is an illustrative layered stack, with less glass than the
  solid slab. Both panes are visible in the viewer.
* **Resistive conducting sheet:** ``AddConductingSheet`` represents a synthetic
  100 micrometre film with conductivity 10,000 S/m (1 ohm per square). It is
  simulated as a zero-thickness surface at x = 0.06 m. This is openEMS's thin-sheet
  approximation, not an explicitly resolved volume or a measured metal coating.
* **Perfect metal:** ``AddMetal`` provides the opaque PEC control. It is not a
  finite-conductivity model of a particular metal.

The layer and sheet cases deliberately have different material volumes from
the bulk slabs; the interface explains this when selected. Source, domain,
recording grid and receiver positions stay the same across all eight cases.

Reading the view
----------------

The viewer preserves the original experiment's field-strength and steady-state
phase modes. One shared air reference prevents per-material rescaling from
concealing differences. White outlines show the actual bulk, layered or
zero-thickness geometry. Cyan markers are before the sample, behind it, and
beside its edge. Gold marks the antenna.

All complex fields are normalized to a 1 V incident wave at the 50-ohm dipole
feed. Receiver differences are total electric-field amplitude changes versus
air, including reflection, transmission and diffraction around finite edges.
They are not pure material penetration losses, calibrated received dBm, or
proof that one material will always give better reception. Interference can
raise or lower the field at a particular point.

The display is one horizontal z = 0 slice of each 3D calculation. A phase cycle
reconstructs ``Re(Ez exp(j phase))`` from saved phasors; it does not rerun the
solver or replay the first arrival of the Gaussian pulse.

Reproduction and checks
-----------------------

Run the actual solver cases with the existing Docker image::

   python simulations/run_material_lab.py --build --refine

Eight 10 mm base-grid cases run two at a time. The optional refinement pair
runs air and concrete sequentially with a requested maximum 8 mm spacing and
geometry-aligned local refinement. Exact grid nodes and smallest/largest cells
are archived. Both use PML_8 boundaries, the same source, and a -60 dB energy
decay target; the exporter rejects capped or incomplete runs.

Each unique work directory retains a JSON recipe. ``--work path --refine``
resumes completed cases only when the recipe matches. Failed work should be
inspected before starting a fresh directory. Raw HDF5 planes, XML, port spectra,
logs and hashes are archived in ``data/material_lab``. The compact sample is
bundled in the Python package. Code is MIT and generated numerical data CC0.

The air/concrete grid check covers the marked receiver ratios only. It does
not establish convergence for every material or the entire field, and the
example has no measurement validation. The original 2.4 GHz wall dataset,
source and audit records are preserved independently.

In the bundled run, concrete-versus-air receiver changes differ between grids
by about 0.038 dB before the slab, 0.031 dB behind it, and 0.041 dB beside its
edge. This check applies to those receivers and that material, not every case.

Use ordinary PyVista from Python::

   import pyvista as pv
   from pyvista_radiation import load_material_lab, field_plane_mesh

   data = load_material_lab()
   mesh = field_plane_mesh(data, 'glass', mode='phase', phase_deg=90)
   plotter = pv.Plotter()
   plotter.add_mesh(mesh, cmap='RdBu_r', clim=(-0.25, 0.25), lighting=False)
   plotter.view_xy()
   plotter.show()

References: `ITU-R P.2040-4, Table 3
<https://www.itu.int/dms_pubrec/itu-r/rec/p/R-REC-P.2040-4-202509-I%21%21PDF-E.pdf>`_
and `openEMS material models
<https://docs.openems.de/en/latest/concepts/properties.html>`_.
