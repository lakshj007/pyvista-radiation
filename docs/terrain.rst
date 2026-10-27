Terrain-aware coverage prototype
================================

The browser viewer includes a terrain section that estimates actual extra
propagation loss, rather than placing decorative hills around the far-field
surface. It uses synthetic flat, ridge and mountain landscapes over a local
6 km by 4.5 km area. These are illustrative grids, not geographic measurements.

Select a landscape, frequency, transmitter/receiver heights, transmit power,
assumed peak gain and antenna orientation, then click **Calculate coverage**.
Map colors show estimated received power, added terrain loss, or geometric
line of sight. The inspected receiver profile shows how the direct sight line
intersects the terrain. Disable obstruction loss for a baseline comparison.
Vertical display exaggeration changes the picture only, not the calculation.

Model and assumptions
---------------------

The link budget is::

   received_dBm = transmit_dBm + assumed_peak_gain_dBi + relative_pattern_dB
                  + receiver_gain_dBi - system_loss_dB - free_space_dB - diffraction_dB

The saved far field supplies the normalized angular power pattern. Terrain
changes propagation in this layer; it does not re-solve antenna currents,
feed matching or the original near-field environment. Its peak
absolute gain is an explicit assumption; gain and efficiency are not inferred
from the uncalibrated feed matching. Assumed peak gain cannot exceed the pattern's
angular directivity. The browser defaults to 30 dBm transmit power, 0 dBi assumed
peak gain, 0 dBi receiver gain, 30 m transmitter height and 2 m receiver height
above local ground. Receiver sensitivity is only a selectable display threshold,
not a measured device specification. Both heading and elevation can be adjusted.

Free-space attenuation follows `ITU-R P.525-5, Eq.5
<https://www.itu.int/rec/R-REC-P.525-5-202411-I/en>`_. Each sampled terrain profile
is reduced to the obstacle with maximum Fresnel diffraction parameter. Its loss
uses the single-knife-edge approximation in `ITU-R P.526-16, Eq.31
<https://www.itu.int/rec/R-REC-P.526/en>`_. A grazing edge gives about 6.03 dB;
loss is zero for diffraction parameter at or below -0.78. Geometric sight line
can be clear while an obstacle encroaches into the Fresnel zone.

Profiles use bilinearly interpolated elevations, with sample spacing half the
smallest terrain cell by default. The effective-Earth radius is 8,500 km by
default; pass ``None`` to disable curvature. Paths exceeding the low-angle
approximation's roughly 12-degree diffraction angle are flagged in the result
and summarized in the UI. Receiver points within 10 m of the source, or at the
same horizontal position, are excluded rather than assigned artificial power.

For obstructed links the antenna pattern is sampled towards the dominant
obstacle; otherwise it is sampled along the direct path. A link's free-space
reference uses the straight slant distance. Only the strongest sampled obstacle
is represented. This is **not** the complete ITU general-terrain/delta-Bullington
method, nor a full-wave terrain simulation. It may underestimate multiple-ridge
or broad rounded-obstacle losses. There is no modeled penetration through solid
rock, ground reflection, multipath, buildings, foliage, atmospheric absorption,
polarization mismatch or fading. It is not measurement validated and should not
be treated as a deployment-grade coverage prediction.

Real elevation grids
--------------------

The input contract uses local x/y metres and an elevation matrix ordered (y,x).
All elevations and antenna heights share a local vertical datum. Geographic
longitude/latitude degrees and nodata are rejected by the NPZ contract. Project
and crop real elevation data into a local metric grid before importing it.
There is no automatic GeoTIFF download or GIS reprojection in this prototype.

.. code-block:: python

   from pyvista_radiation import TerrainGrid, save_terrain, load_terrain
   terrain = TerrainGrid(x_m, y_m, elevation_m, source='Description of DEM and datum')
   save_terrain('terrain.npz', terrain)

Launch with that grid::

   pyvista-radiation --terrain terrain.npz

For fast exploration start with approximately 80 by 60 grid points over a small
area. Real DEM features finer than the input grid cannot be recovered by profile
interpolation. A path longer than 8,192 profile segments is rejected; choose a
sensible crop/resolution or explicitly increase spacing in the numerical API.

.. code-block:: python

   from pyvista_radiation import coverage_map, load_patch
   data = load_patch()
   result = coverage_map(terrain, data.frequency_hz[1], pattern=data, pattern_index=1,
                         tx_height_m=30, rx_height_m=2, tx_power_dbm=30,
                         tx_peak_gain_dbi=0, heading_deg=0, elevation_deg=0)
   result.save('coverage.npz')

Results include x/y metric axes and ground elevations alongside unsaturated
numeric arrays, validity masks, line-of-sight flags,
large-angle flags and stated assumptions. Plot colors alone are clipped.
Heading is from +x towards +y; elevation is above the horizon. At zero elevation,
the saved antenna +z boresight points along the heading and its +x points upward.

Validation and example
-----------------------

Tests independently check free-space loss at 1 km/2.4 GHz; grazing-edge loss;
profile reciprocity; added attenuation behind a ridge; restoration with greater
antenna height; power-budget scaling; periodic antenna interpolation; missing
terrain data and metric units; near-source masks; and display-only exaggeration.
They verify this implementation of the approximate model, not its accuracy for
real mountains.

Run ``python examples/terrain_coverage.py`` for a saved comparison figure,
coverage arrays and a JSON record of all assumptions.
