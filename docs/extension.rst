Using the PyVista extension
===============================

``pyvista-radiation`` is an independent downstream PyVista extension. Its main
outputs are ordinary ``pyvista.PolyData`` datasets, compatible with standard
PyVista plotters, filters, subplots, notebooks and VTK file export. The browser
dashboard is an optional example application, not a required execution path.

Add patterns to your own plotter
------------------------------------

Install the checkout with ``pip install -e '.[plot]'``. The package declares a
``pyvista.plotter_components`` entry point, following PyVista's
`documented extension contract <https://docs.pyvista.org/extras/extending_pyvista.html>`_.
PyVista loads its component module only when you first access ``plotter.radiation``.

.. code-block:: python

   import pyvista as pv
   from pyvista_radiation import load_patch

   data = load_patch()
   plotter = pv.Plotter()
   actor = plotter.radiation.add_pattern(
       data, index=0, radial_scale='db', floor_db=-30,
       opacity=0.9, cmap='viridis', name='antenna_pattern',
   )
   plotter.radiation.set_frequency(actor, 1)
   plotter.show()

``add_pattern`` returns a native ``pyvista.Actor`` in the current subplot.
Display/normalization options match ``radiation_mesh``. Other keywords go to
``Plotter.add_mesh``. Color limits stay fixed across frequency updates; use
explicit ``clim`` when comparing directivity at several frequencies. Distinct
scalar-bar titles are needed if you want separate bars for different quantities.
The component leaves the caller's theme, background, lighting and other actors
under caller control. ``set_frequency`` keeps the actor, styling and camera,
returns its new mesh, and preserves frequency/normalization metadata.

Call ``plotter.radiation.remove_pattern(actor)`` to remove a managed actor.
Closing/deep-cleaning the plotter releases the component's retained references.
If you remove an actor with PyVista directly, later frequency updates reject it.
No observers, threads, servers or solver processes are started by this component.

Work with plain meshes
--------------------------

.. code-block:: python

   from pyvista_radiation import radiation_mesh, principal_cut, difference_mesh

   mesh = radiation_mesh(data, 1)
   clipped = mesh.clip(normal='x')
   difference = difference_mesh(data, 0, 2)
   theta_deg, field_db = principal_cut(data, 1, plane='xz')
   mesh.save('radiation.vtp')

No custom dataset subclass or accessor is necessary. VTP export preserves mesh
arrays and metadata but is a visualization export: it does not contain all
original complex fields. Use ``save('fields.npz', data)`` to preserve those.
PyVista filters operate on the display geometry. For example, geometrical surface
area of a radius-normalized pattern is not physical radiated power. Use the
numerical API on the original angular fields for radiation quantities.

Examples
------------

``examples/pyvista_extension.py`` shows a native mesh, the plotter component and
a standard clip filter side by side. It needs the ``plot`` extra only. Pass
``--screenshot preview/pyvista_extension.png`` to generate an off-screen PNG and
a VTP file. ``examples/user_arrays.py`` builds an analytic dipole from NumPy.

In a notebook, use PyVista's normal notebook backend. An interactive trame
backend needs the optional browser dependencies and a working Jupyter widget
environment; the extension itself does not replace PyVista's backend setup.
Open ``examples/pyvista_extension.ipynb`` for a walkthrough. Install
``pip install -e '.[notebook]'`` in the notebook's kernel environment and use
your existing Jupyter or notebook editor. Its default backend is interactive
trame; select ``static`` in the backend cell if your frontend cannot serve widgets.

Optional propagation example
--------------------------------

``pyvista-radiation`` opens the radiation-only browser demo.
``pyvista-radiation --coverage`` opens the hillside-city showcase first, with
radiation comparisons in an expandable section below. Use
``--environment hillside_city`` to select it explicitly; any supported environment
can be selected with this option. ``--terrain terrain.npz`` also enables the demo.
``examples/coverage_demo.py`` launches the same optional example.
The propagation model is separate from mesh conversion and is not a claim
that PyVista itself simulates radio propagation. See :doc:`terrain` for limits.
