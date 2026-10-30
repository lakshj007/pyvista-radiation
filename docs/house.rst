Two-floor wave house
====================

A compact 4 × 3 m, two-level structure demonstrates vertical propagation,
transmission, reflection and interference in actual 3D openEMS fields. PyVista
renders recorded slices and building geometry; it does not calculate the waves.
The three cases are an open stairwell, the same structure with its middle-floor
opening filled, and an air baseline.

Run the example
---------------

.. code-block:: sh

   python examples/two_floor_house.py --browser   # localhost:8769
   python examples/two_floor_house.py             # native four-panel view
   python examples/two_floor_house.py --time-ns 24 --screenshot preview/house.png

The browser starts with a labeled **Front cutaway**. Solid wall sections and tan
timber slabs make the two levels and floor opening visible. **3D cutaway** shows
the rear half of the structure with its front and roof removed. **Downstairs plan**
and **Upstairs plan** switch directly to steady field slices with wall sections at
the selected height. Only receiver markers on that floor are shown in plan views.

**Show signal** hides the field slice so the building can be inspected on its own;
**Show labels** controls annotations. TX is the transmitter, A the downstairs
receiver, B the receiver directly above TX and C the upstairs receiver by the
opening. Weak pulse/phase fields blend into the background using display opacity;
raw values remain unchanged. Magnitude views use opaque colors. Cutaway geometry
and exterior visibility are display operations: all walls remain in the calculation.
The stairwell is an air opening, without modeled stairs.

Recorded pulse versus steady wave
---------------------------------

**Play recorded pulse** displays unchanged saved Ey samples on the vertical
y=0 plane, in their original time order. The time slider reports the actual
openEMS timestamp. Red and blue denote opposite electric-field directions,
not high and low received power. The saved pulse uses the original common
Gaussian port drive. It is not a phase animation made from a single frequency.

Steady modes use complex vector fields at 500 MHz, normalized to a 1 V incident
feed wave. **Play one cycle** reconstructs Re(Ey exp(j phase)) from those phasors;
this illustrates steady oscillation, not pulse arrival. Magnitude mode shows
``20 log10(|E|/reference)``, clipped to −60…0 dB for display. It is not received dBm.
Pulse and steady modes use separate shared air references outside a 0.2 m source
radius. Pulse colors clip at ±0.25 of the pulse reference, preserving raw values.

In this run the open-house downstairs receiver has its largest absolute Ey at
15.79 ns, while the receiver directly upstairs peaks at 22.72 ns. These are pulse
peaks, not first-arrival measurements. The steady upstairs receiver by the opening
is −1.79 dB relative to air, compared with −2.95 dB for the filled floor. An opening
does not guarantee a stronger field at every position because paths interfere.

Use ordinary PyVista grids
--------------------------

.. code-block:: python

   import pyvista as pv
   from pyvista_radiation import load_house, house_slice_mesh

   data = load_house()
   mesh = house_slice_mesh(data, 'open', mode='pulse', frame=62)
   plotter = pv.Plotter()
   plotter.add_mesh(mesh, scalars='Displayed field', cmap='RdBu_r',
                    clim=(-.25, .25), lighting=False)
   plotter.show()

``CartesianPlane`` stores full complex vector fields in (case, v, u, xyz) order,
with explicit Cartesian axis indices and fixed position. ``HouseFields`` stores
per-case pulse arrays in (time, v, u) order and corresponding timestamps. NPZ
round trips retain coordinates in metres, time in seconds, frequency in hertz,
and field in V/m without pickle. Pulse grids have 50 mm spatial spacing;
steady planes use 25 mm spacing. Air terminates earlier and has fewer frames;
there is no temporal interpolation or zero padding. The returned mesh is a normal
``pyvista.StructuredGrid`` with physical coordinates and unclipped raw field arrays.

Geometry, source and limits
---------------------------

The model is 4.55 m high with a 150 mm timber middle slab at z=2.2…2.35 m,
a 0.8 × 1 m opening, roof and ground slabs, and assumed homogeneous 100 mm
partitions. A horizontal 250 mm dipole at (−1.1, 0, 1) m has a 50 ohm feed.
Its y orientation places the vertical slice in a broadside radiation direction.
The pulse is centered at 500 MHz with a 100 MHz Gaussian corner frequency.

Timber uses a wood-class example (relative permittivity 1.99 and conductivity
0.0047 × 0.5^1.0718 S/m). Partitions use assumed relative permittivity 2.5 and
conductivity 0.005 S/m. These are fixed isotropic coefficients, not measured
construction materials. There is no furniture, reinforcement, glazing, real
stair geometry or antenna/device calibration. This is not a Wi-Fi-band or
measured-house prediction.

The solver mesh has 7,947,225 cells (25 mm spacing), with PML on all six sides.
All runs reach below −60 dB residual energy. **No house-specific mesh convergence
study has been performed**; energy decay does not establish spatial accuracy.
Only the recorded planes are available, not a volumetric field recording.

Reproduce and inspect
---------------------

.. code-block:: sh

   python simulations/run_house.py --build

This uses the existing pinned Docker solver image and runs three real calculations.
The exporter saves the packaged NPZ and ``data/house/metadata.json``. Raw HDF5 files
are losslessly gzip-compressed in ``data/house/raw`` alongside geometry XML, port
spectra, energy traces and logs. Both compressed and original byte hashes, solver
version, recipe and generator hashes are retained. ``--work`` resumes a matching
work directory. Docker/openEMS are needed to recalculate, not to view saved fields.
