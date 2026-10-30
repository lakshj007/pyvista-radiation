Recorded RF pulse through two floors
====================================

A standalone PyVista example for review. Open a native 3D cutaway beside a front
section, then drag the time slider through actual openEMS recordings. TX is the
downstairs transmitter; A is a downstairs receiver, B is directly above TX,
and C is upstairs by the floor opening. Tan slabs are timber-class material.
The colored surface is a single vertical field slice, not a wall or a full
volumetric recording. Red and blue show opposite electric-field directions.

Run it
------

Keep this folder and its ``data`` subfolder together. From any working directory:

.. code-block:: sh

   python -m pip install 'pyvista>=0.49' numpy
   python /path/to/house_showcase/plot_house_pulse.py

No radiation extension, openEMS, Docker, browser server or network access is
needed after installation. Drag to rotate, scroll to zoom, and use the time
slider. The Python process must stay open for the slider callback. The gallery
HTML and PNG preview are static snapshots; a standalone HTML export cannot
execute Python callbacks.

For a headless PNG, with an optional animated GIF of every saved frame:

.. code-block:: sh

   python render_preview.py --screenshot preview.png
   python render_preview.py --screenshot preview.png --gif pulse.gif

PyVista's Pillow dependency is used only to write the optional GIF. Playback is
slowed for viewing; its labels retain physical solver timestamps.

Data and scope
--------------

``data/house_pulse.vtm`` is an ordinary VTK MultiBlock with three blocks:

* ``pulse``: a StructuredGrid at y=0, with ``Ey (V/m)`` stored as point-by-time
  components and the original ``Time (s)`` field array.
* ``building``: volume cells describing the original open-stairwell material
  boxes, with material IDs 0 (assumed partition) and 1 (wood-class slab).
* ``markers``: original transmitter and receiver positions and labels.

The approximately 1.5 MB dataset includes all 143 original pulse timestamps.
It retains every second spatial sample of the 50 mm recording, giving a 100 mm
display grid. Selected float32 values are unchanged; there is no temporal
thinning, interpolation or recalculation. Original 25 mm solver geometry is
retained separately from display sampling. The air reference is inherited from
the complete experiment, rather than recomputed from the reduced display grid.

This is a compact 4 × 3 m, 500 MHz numerical model with assumed homogeneous
partitions and timber-class slabs. It is not a Wi-Fi-band prediction. There is
no house-specific mesh convergence or measurement validation. Only the vertical
Ey component is recorded here; this example cannot isolate individual reflected
paths or report received dBm.

``data/manifest.json`` records source/exporter hashes, derivation and native-file
hashes. The pulse also retains full source provenance as VTK field data. The
exporter in the parent repository is ``simulations/export_house_showcase.py``.
Code is MIT (``LICENSE``); numerical data are CC0-1.0 (``data/LICENSE``).
