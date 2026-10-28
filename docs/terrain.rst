Terrain-aware coverage prototype
================================

This is an optional application example separate from the PyVista radiation
extension. Launch with ``pyvista-radiation --coverage`` or
``python examples/coverage_demo.py``. The landscape appears first, with radiation
graphs and path details in expandable sections. The radiation-only browser demo
and native APIs work independently of this layer.

The browser viewer includes a terrain section that estimates actual extra
propagation loss, rather than placing decorative hills around the far-field
surface. It uses synthetic flat, ridge and mountain landscapes over a local
6 km by 4.5 km area, including rugged ranges and a winding valley. Low-rise
city blocks and downtown towers use a smaller 1.6 km by 1.2 km area. These are
illustrative scenes, not geographic measurements.

City environments
-----------------

The default coverage showcase is **City · hills, valley & neighborhoods**.
Select it explicitly with ``pyvista-radiation --environment hillside_city``.
It spans 2.4 km by 1.8 km, with about 190 buildings over roughly 267 m of elevation
variation. It combines a winding dry valley, ridges, a tall center, smaller
neighborhoods, open park districts and draped road ribbons. Building foundations
extend down to the minimum terrain elevation within their footprints; roofs
remain above the maximum terrain elevation there, avoiding floating boxes.
Transmitter presets and inspected receiver plazas are reserved outdoors.

The ground elevations and building roof heights both participate in the existing
obstruction/diffraction calculation. Roads are decorative context and do not add
material attenuation. Parkland is reserved open ground; no vegetation or foliage
propagation is invented. Geometry is deterministic and entirely synthetic.

The **Terrain elevation** map option colors physical ground heights rather than
received power. Vertical exaggeration remains display-only. **Reset view** frames
the calculated scene without applying pending control changes.
Run ``python examples/urban_landscape.py`` to save a native PyVista screenshot;
``--screenshot path.png`` selects the destination. It requires the browser extra
for the shared scene builder, but starts no browser or listening server.

Choose **City · low-rise blocks** or **City · downtown towers** in the Environment
selector. Both contain 80 reproducible building boxes and intersecting streets.
Choose a west, center or east transmitter position, adjust its height, and
calculate again. Heights remain relative to local ground, not roof level.
Moving the transmitter does not automatically turn its antenna; adjust heading
under More settings when comparing opposite ends of the scene.

Pale building boxes are obstacles. Colors on the ground show estimated outdoor
reception. Building footprints are excluded from reception statistics and saved
results mark them with ``building_mask``; no indoor values or rooftop receivers
are invented. Building entry/exit intersections are inserted into each path
profile even when a footprint is narrower than the terrain sampling interval.
Roof heights contribute to obstruction, geometric sight lines and the dominant
diffraction edge. The inspected profile separates ground from the roof surface.
Turning obstruction loss off retains buildings and receiver masks for comparison.

This is **not a validated urban propagation model**. Only the vertical path
over roofs is approximated; side-edge diffraction, street-corner propagation,
reflections between facades, materials, indoor reception and multipath are
omitted. Dense city results can therefore differ substantially from real signals.
The categories and additional effects of urban propagation are discussed in
`ITU-R P.1411 <https://www.itu.int/rec/R-REC-P.1411-13-202509-I/en>`_; this prototype
does not implement that recommendation.

The numerical API accepts custom boxes with absolute local base/roof elevations::

   from pyvista_radiation import Building, synthetic_environment, coverage_map
   terrain, buildings = synthetic_environment('downtown')
   result = coverage_map(terrain, 2.4e9, buildings=buildings, tx_xy=(0, 0))
   result.save('city_coverage.npz')

The saved coverage archive includes the building geometry in its JSON metadata,
the footprint mask, and the ground coordinate/elevation arrays. The terrain-only
NPZ loader still accepts only ground elevations; city presets are selected in
the viewer. No live maps or real city building data are downloaded.

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
rock or walls, ground reflection, multipath, foliage, atmospheric absorption,
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
