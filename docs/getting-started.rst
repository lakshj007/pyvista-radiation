Getting started
===================

Install the extension from a checkout::

   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e '.[plot]'

Create and plot a native mesh
---------------------------------

.. code-block:: python

   import pyvista as pv
   from pyvista_radiation import load_patch, radiation_mesh

   data = load_patch()
   mesh = radiation_mesh(data, frequency_index=1)
   plotter = pv.Plotter()
   plotter.add_mesh(mesh, scalars='Relative field (dB)', clim=(-40, 0))
   plotter.show()

The bundled sample is installed with the package and works outside the checkout.
No openEMS installation or simulation is required. The result is a normal
``pyvista.PolyData`` with physical field samples and display metadata. Use
``plotter.radiation.add_pattern(data, index=1)`` to add a pattern through the lazy
PyVista plotter component instead. See :doc:`extension` and :doc:`importing`.

Run ``python examples/pyvista_extension.py`` for an interactive native example.
For headless rendering, pass ``--screenshot preview/pyvista_extension.png``.
``examples/user_arrays.py`` demonstrates complex NumPy input with an analytic
dipole. PyVista's normal notebook backends are supported; interactive notebook
rendering needs the browser/widget dependencies described by PyVista.

Optional browser application
--------------------------------

Install the extra and launch the radiation comparison::

   pip install -e '.[browser]'
   pyvista-radiation

Open http://127.0.0.1:8766. Stop the server with Ctrl+C. The page demonstrates
library meshes, cuts, beamwidths and frequency comparisons. Supply a saved
NPZ file as the first argument. ``pyvista-radiation --native`` opens a native
frequency comparison with sliders. The sliders select frequency indices; titles
show the corresponding GHz value.

The optional propagation example is explicitly enabled::

   pyvista-radiation --coverage
   pyvista-radiation --terrain terrain.npz

This adds synthetic terrain/city coverage after the radiation comparison. It is
a separate approximate model, not a feature required to load or visualize fields.

The browser comparison requires full-sphere sampling containing principal
azimuths 0°, 90°, 180° and 270°. Use the general mesh API for other uniform
azimuth grids. Data loading requires only NumPy. The ``plot`` extra adds PyVista;
``browser`` adds the trame app; ``preview`` remains a compatible alias for the
browser dependencies. This checkout has not been published to PyPI.

Licensing and source data
-----------------------------

Raw solver outputs, reproduction and attribution live in ``data/`` and
``simulations/``. Core code is MIT; the adapted simulation script is
GPL-3.0-or-later; generated data is CC0-1.0. The extension is a third-party project,
not a claim of PyVista endorsement. See :doc:`validation` for scientific limits.
