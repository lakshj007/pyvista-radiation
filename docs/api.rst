API reference
=============

Data
----

.. autoclass:: pyvista_radiation.RadiationData
   :members:

.. autofunction:: pyvista_radiation.load
.. autofunction:: pyvista_radiation.save
.. autofunction:: pyvista_radiation.load_patch
.. autofunction:: pyvista_radiation.from_arrays
.. autofunction:: pyvista_radiation.load_csv

Geometry and numerics
---------------------

.. autofunction:: pyvista_radiation.radiation_mesh
.. autofunction:: pyvista_radiation.spherical_directions
.. autofunction:: pyvista_radiation.amplitude_db
.. autofunction:: pyvista_radiation.power_db
.. autofunction:: pyvista_radiation.directivity
.. autofunction:: pyvista_radiation.principal_cut

Plotting
--------

.. autoclass:: pyvista_radiation._pyvista_plugin.RadiationComponent
   :members: add_pattern, set_frequency, remove_pattern

.. autoclass:: pyvista_radiation.RadiationViewer
   :members:

.. autofunction:: pyvista_radiation.plot_pattern
.. autofunction:: pyvista_radiation.compare_patterns

Browser app
-----------

.. autofunction:: pyvista_radiation.webapp.create_app
.. autofunction:: pyvista_radiation.webapp.serve

Comparison measurements
------------------------

.. autofunction:: pyvista_radiation.beamwidth
.. autofunction:: pyvista_radiation.half_power_beamwidth
.. autofunction:: pyvista_radiation.pattern_difference
.. autofunction:: pyvista_radiation.difference_mesh

Terrain and coverage
--------------------

.. autoclass:: pyvista_radiation.TerrainGrid
   :members:

.. autofunction:: pyvista_radiation.synthetic_terrain
.. autofunction:: pyvista_radiation.synthetic_environment

.. autoclass:: pyvista_radiation.Building
   :members:

.. autofunction:: pyvista_radiation.load_terrain
.. autofunction:: pyvista_radiation.save_terrain
.. autofunction:: pyvista_radiation.coverage_map

.. autoclass:: pyvista_radiation.RadioTower
   :members:

.. autoclass:: pyvista_radiation.NetworkCoverageResult
   :members:

.. autofunction:: pyvista_radiation.network_coverage
.. autofunction:: pyvista_radiation.metro_towers

.. autofunction:: pyvista_radiation.terrain.path_profile
.. autofunction:: pyvista_radiation.terrain.free_space_loss
.. autofunction:: pyvista_radiation.terrain.knife_edge_loss
