pyvista-radiation
=================

Turn saved antenna far fields into validated PyVista surfaces and compare their
frequency dependence. The bundled openEMS patch example runs without a solver.

.. toctree::
   :maxdepth: 2

   getting-started
   examples
   terrain
   validation
   api

The :download:`version 1 NPZ contract <data-contract.md>` documents physical
units, array ordering, angular conventions, provenance, and validation rules.

Scope
-----

This package reads saved results. It does not launch openEMS, infer gain from
unnormalized fields, or claim measurement or mesh-convergence validation for
the tutorial antenna. Directivity from angular integration is separately
validated and does not establish antenna efficiency.
