"""
.. _openems_house_pulse_example:

Explore a recorded radio pulse through two floors
=================================================

Load actual openEMS time samples as native PyVista datasets. Compare a clipped
3D house with an architectural section, then move a time slider without
replacing the mesh or recalculating the fields. Only this vertical field slice
was recorded; the colors do not represent a full 3D field volume.

This compact 500 MHz model uses assumed partitions and wood-class slabs.
It has no house-specific mesh convergence or measurement validation. Red and
blue indicate opposite electric-field directions, not received signal power.

Keep the accompanying ``data`` folder beside this script. The
`complete offline bundle <https://github.com/lakshj007/pyvista-radiation/raw/refs/heads/feat/radiation-comparison-validation/preview/house_showcase.zip>`_
contains both; an individual Python download does not include the VTK assets.
"""
# SPDX-License-Identifier: MIT
# sphinx_gallery_start_ignore
PYVISTA_GALLERY_FORCE_STATIC_IN_DOCUMENT = True
# sphinx_gallery_end_ignore
from pathlib import Path

import numpy as np
import pyvista as pv

# %%
# Read a native VTK MultiBlock dataset. The folder travels with this script;
# no solver, network access, trame server or extension-package import is needed.
# Sphinx-Gallery runs from the example directory without defining __file__.
example_dir = Path(__file__).parent if "__file__" in globals() else Path.cwd()
scene = pv.read(example_dir / "data/house_pulse.vtm")
pulse, building, markers = scene["pulse"], scene["building"], scene["markers"]
recorded_ey = pulse["Ey (V/m)"]  # rows: spatial points; columns: recorded frames
seconds = pulse.field_data["Time (s)"]
reference = float(pulse.field_data["Air pulse reference (V/m)"][0])
initial_frame = int(pulse.field_data["Default frame"][0])
pulse["Ey / air reference"] = recorded_ey[:, initial_frame] / reference

# %%
# Ordinary PyVista filters cut the original building geometry for display.
# The thin translation prevents coplanar wall sections fighting with the field
# slice at y=0. These operations do not change the saved solver fields.
rear_half = building.clip(normal="y", origin=(0, 0, 0), invert=False)
section = building.slice(normal="y", origin=(0, 0, 0)).translate((0, -.04, 0))
plotter = pv.Plotter(shape=(1, 2), window_size=(1440, 1000))
time_labels = []
for column, (geometry, title) in enumerate(((rear_half, "3D cutaway"), (section, "Front section"))):
    plotter.subplot(0, column)
    plotter.set_background("#dce7ee")
    plotter.add_mesh(geometry, scalars="Material", preference="cell",
                     cmap=["#a9bbc5", "#bc9361"], clim=(0, 1),
                     show_scalar_bar=False, show_edges=True, edge_color="#526e7f")
    plotter.add_mesh(pulse, scalars="Ey / air reference", cmap="RdBu_r",
                     clim=(-.25, .25), lighting=False,
                     opacity=[.95, .9, .8, .5, 0, .5, .8, .9, .95],
                     show_scalar_bar=column == 1,
                     scalar_bar_args=dict(title="Ey / shared air reference", color="#183749",
                                          vertical=False, position_x=.15, width=.7, position_y=.12, height=.065,
                                          title_font_size=11, label_font_size=9))
    plotter.add_mesh(pv.Sphere(radius=.08, center=markers.points[0]), color="#d99a10")
    plotter.add_points(markers.points[1:], color="#007d99", point_size=12,
                       render_points_as_spheres=True)
    label_points = markers.points + np.array([.1, -.1, .1])
    plotter.add_point_labels(label_points, list(markers["Label"]), show_points=False,
                             always_visible=True, font_size=14, text_color="#183749",
                             shape_color="#edf3f6", shape_opacity=.8)
    for text, z in (("UPSTAIRS", 4.05), ("DOWNSTAIRS", 1.85)):
        label = pv.Text3D(text, depth=.002, height=.16).rotate_x(90)
        label.translate((-label.bounds[0] - 1.7, -.12, z - label.bounds[4]), inplace=True)
        plotter.add_mesh(label, color="#183749", lighting=False)
    plotter.add_text(title, position=(20, 940), color="#183749", font_size=14)
    time_labels.append(plotter.add_text("", position=(20, 900), color="#183749", font_size=10))
    if column == 0:
        plotter.camera_position = [(7, -8, 6), (0, 0, 2.25), (0, 0, 1)]
    else:
        plotter.camera_position = [(0, -12, 2.35), (0, 0, 2.35), (0, 0, 1)]
    plotter.enable_parallel_projection()
    plotter.camera.parallel_scale = 3.7
    if column == 0:
        plotter.add_text("Tan slab: floor · gap: stairwell opening\nColors: Ey on one recorded vertical cut",
                         position=(20, 65), color="#183749", font_size=10)

# sphinx_gallery_defer_figures

# %%
# Snap to the closest original timestamp. Only display scalars change; the raw
# multi-component Ey array, geometry, actors and user camera remain intact.
def set_time(nanoseconds):
    frame = int(np.argmin(abs(seconds * 1e9 - nanoseconds)))
    pulse["Ey / air reference"][:] = recorded_ey[:, frame] / reference
    pulse.field_data["Displayed time (s)"] = [seconds[frame]]
    for label in time_labels:
        label.SetInput(f"Recorded pulse · {seconds[frame] * 1e9:.2f} ns · 500 MHz")


plotter.add_slider_widget(set_time, (seconds[0] * 1e9, seconds[-1] * 1e9),
                           value=seconds[initial_frame] * 1e9, title="Recorded time (ns)",
                           pointa=(.12, .055), pointb=(.88, .055), fmt="%.2f", color="#183749",
                           title_height=.02, slider_width=.025, tube_width=.005)
plotter.show()
