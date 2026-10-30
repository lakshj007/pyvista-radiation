pyvista-radiation
=================

A third-party PyVista extension for antenna radiation data. Load saved complex
far fields, create ordinary PyVista meshes, compare frequencies and extract
principal-plane cuts in your own Python workflows. The bundled openEMS patch
example runs without a solver. A lazy plotter component integrates directly with
your existing ``pyvista.Plotter``; the browser dashboard is an optional demo.

.. toctree::
   :maxdepth: 2

   getting-started
   extension
   importing
   examples
   validation
   api

.. toctree::
   :maxdepth: 1
   :caption: Optional application example

   terrain
   nearfield
   material-lab
   house

The :download:`version 1 NPZ contract <data-contract.md>` documents physical
units, array ordering, angular conventions, provenance, and validation rules.

Scope
-----

The core library reads and visualizes supplied results. It does not launch openEMS, infer gain from
unnormalized fields, or claim measurement or mesh-convergence validation for
the tutorial antenna. Directivity from angular integration is separately
validated and does not establish antenna efficiency.
