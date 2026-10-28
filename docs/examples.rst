Radiation visualization examples
================================

Start with ``python examples/pyvista_extension.py`` for a normal PyVista scene,
or ``python examples/user_arrays.py`` for analytic NumPy input. Both need only
the ``plot`` extra. See :doc:`extension` for the plotter component, standard
filters and mesh export, and :doc:`importing` for solver-independent adapters.

Create meshes
-------------

.. code-block:: python

   from pyvista_radiation import load_patch, radiation_mesh
   data = load_patch()
   pattern = radiation_mesh(data, 1)
   sphere = radiation_mesh(data, 1, mode='sphere')
   weak_lobes = radiation_mesh(data, 1, radial_scale='db', floor_db=-30)
   pattern.save('pattern.vtp')

Each point carries relative field dB, physical field magnitude, display radius
and its original unit direction. Mesh field data records the frequency and
normalization reference. Theta includes both poles; phi omits the duplicate
seam. Nonuniform theta is supported. Phi must uniformly cover the full circle.
Pole magnitudes must agree across phi, even though complex components may vary
with the rotating basis. A single vertex represents each pole.

Compare two frequencies
-----------------------

.. code-block:: python

   from pyvista_radiation import load_patch, compare_patterns
   viewer = compare_patterns(load_patch(), (0, 2), radial_scale='db', floor_db=-30)
   viewer.show()

A reusable viewer can update an existing scene::

   viewer.set_frequency(0, 1)
   viewer.configure(mode='sphere', normalization='global')

These operations preserve the camera and actors. ``viewer.close()`` releases
resources. For a live browser view, use ``pyvista-radiation`` or run
``python examples/compare_frequencies.py``.
The separate terrain/city example requires ``pyvista-radiation --coverage``
or ``python examples/coverage_demo.py`` and is documented in :doc:`terrain`.

Read the scales
---------------

* **Per frequency:** each frequency's sampled maximum is 0 dB and radius 1.
  This compares shape and hides absolute amplitude differences.
* **Global:** one sampled maximum over the entire saved dataset is 0 dB.
  This compares saved field amplitudes. Excitation spectra and feed matching
  affect these values; this is not a gain or efficiency comparison.
* **Linear radius:** relative field amplitude, with no radial display floor.
* **Decibel radius:** ``(relative_dB - floor_dB) / (-floor_dB)``. Weak lobes
  become easier to inspect. A value at the floor has zero display radius.
* **Sphere:** unit radius. Only color represents field strength.

Colors and cut plots share limits. Cuts use ``20 log10`` for field amplitude.
Power ratios and directivity use ``10 log10``. The floor changes only display
values, never the saved complex fields. Nulls can map to coincident points in a
variable-radius surface; the sphere retains nondegenerate geometry everywhere.

Angular directivity
-------------------

.. code-block:: python

   from pyvista_radiation import directivity, radiation_mesh
   linear_D = directivity(data, 1)
   mesh = radiation_mesh(data, 1, quantity='directivity')

This computes ``4π |E|² / integral(|E|² dΩ)`` for a homogeneous far-field medium
at fixed radius. It does not need an absolute field calibration and is not gain.
Color is dBi; linear radius is ``sqrt(D / Dmax)``. Field normalization selection
does not change directivity. An all-zero field has undefined directivity and
raises ``ValueError``. Do not interpret numerical quadrature as a new solver run.

Differences and measured widths
-------------------------------

The live viewer includes front (+z), back (-z), side (+x) and isometric camera
presets. A separate unit sphere shows right-frequency minus left-frequency
field dB with a diverging color map. Positive (red) means the right frequency
is stronger for the selected normalization. Both fields are floored before
subtraction; two values at the floor give zero. Colors saturate outside ±20 dB.

.. code-block:: python

   from pyvista_radiation import beamwidth, difference_mesh, pattern_difference
   width = beamwidth(data, 1, 'xz')
   signed_db = pattern_difference(data, 0, 2)
   difference_sphere = difference_mesh(data, 0, 2)
   viewer.camera_preset('back')

Widths are the interpolated half-power crossings around the sampled main-lobe
peak in each principal plane. They are independent of the display floor and
inherit the saved angular grid's resolution. Omnidirectional or zero cuts have
no bounded half-power width. Front/back values in the table are the backward
axis relative to the full-sphere sampled peak, not integrated hemispheric power.
