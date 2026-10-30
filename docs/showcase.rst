A focused PyVista showcase
==========================

This review example shows how PyVista can visualize another library's saved
simulation results. The short script uses native VTK loading,
volume clipping, wall slicing, shared scalar updates and a recorded-time slider.
It requires only NumPy and PyVista, independently of ``pyvista-radiation``.

.. image:: ../preview/house_showcase.png
   :alt: A 3D cutaway beside a labeled vertical house section at 23.88 ns

:download:`Download the complete offline example bundle <../preview/house_showcase.zip>`
contains the script, VTK assets, licenses, provenance and a headless renderer.
Keep its ``data`` folder beside the script. The generated
:doc:`auto_examples/plot_house_pulse` page executes the actual example source.
Its documentation image is static; the time slider runs in a live Python session.

Try it
------

.. code-block:: sh

   python -m venv .review-venv
   .review-venv/bin/python -m pip install 'pyvista>=0.49' numpy
   .review-venv/bin/python examples/house_showcase/plot_house_pulse.py

Or unpack the downloaded bundle anywhere and run ``plot_house_pulse.py`` from
that folder. It needs no extension import, openEMS, Docker, trame or data download.
Select time with the slider, rotate the cutaway, or zoom using normal PyVista
interaction. TX is the transmitter; A, B and C are receiver locations. The tan
slab separates downstairs from upstairs, with a gap at the stairwell opening.

What is supplied
----------------

The native ``MultiBlock`` asset contains a vertical field ``StructuredGrid``,
volume cells for the original building boxes and marker coordinates. All 143
original timestamps are retained. The display grid takes every second spatial
sample of the original 50 mm recording, yielding 100 mm spacing; selected
float32 field values and float64 timestamps remain unchanged. The solver mesh
was 25 mm. The spatial reduction is for visualization, not a refined calculation.

Colors show recorded Ey divided by a common air reference, clipped to ±0.25 for
display. Weak values blend into the background. This is one plane in a 3D model,
not a volumetric field recording, received power or isolated ray paths.

The 4 × 3 m model operates at 500 MHz with assumed partitions and wood-class
slabs. It has no house-specific mesh convergence or measurement validation.
Numerical assets are CC0-1.0; the example is MIT. The native files retain full
source provenance, with additional source/exporter/file hashes in the manifest.

For review
----------

The :download:`draft upstream proposal <upstream-proposal.md>` asks maintainers
whether a gallery example or external showcase listing is the preferred route.
The example follows PyVista's `gallery format
<https://docs.pyvista.org/examples/99-advanced/add_example.html>`_.
An upstream dataset contribution would follow the `dataset guidance
<https://docs.pyvista.org/contributing#adding-a-new-dataset>`_ and use their
preferred asset hosting and download wrapper. No upstream acceptance is assumed.

The full house browser and material experiments remain separate demonstrations.
See :doc:`house` for the complete recording and :doc:`release-readiness` for the
remaining work before an experimental package release.
