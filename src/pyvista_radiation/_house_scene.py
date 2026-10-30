"""Display-only architectural sections of the saved solver geometry."""

import numpy as np

WALL = "#526e7f"
TIMBER = "#bc9361"
INK = "#183749"
BACKGROUND = "#dce7ee"


def geometry_bounds(box, view, heights):
    """Intersect original boxes with a section, plan or rear-half cutaway.

    These bounds are only drawing geometry. They never alter the saved fields
    or the geometry used in the solver, and never fill the stairwell opening.
    """
    bounds = list(box["bounds_m"])
    if view == "exterior":
        return bounds
    if view == "house":
        if box["role"] == "roof" or bounds[3] <= 0:
            return None
        bounds[2] = max(0, bounds[2])
    elif view == "vertical":
        if not bounds[2] <= 0 <= bounds[3]:
            return None
        bounds[2:4] = [-.035, .035]
    else:
        z = heights[view]
        if not bounds[4] <= z <= bounds[5]:
            return None
        bounds[4:6] = [z - .035, z + .035]
    return bounds


def add_architecture(viewer):
    import pyvista as pv

    heights = {name: p.fixed_m for name, p in viewer.data.planes.items()}
    viewer.actor_views = {}
    for case in viewer.data.metadata["recipe"]["cases"]:
        actors = []
        for view in ("house", "vertical", "downstairs", "upstairs", "exterior"):
            for i, box in enumerate(case["boxes"]):
                bounds = geometry_bounds(box, view, heights)
                if bounds is None:
                    continue
                mesh = pv.Box(bounds=bounds)
                viewer.geometry.append(mesh)
                color = TIMBER if box["material"] == "timber" else ("#b5c5cf" if view in ("house", "exterior") else WALL)
                actor = viewer.plotter.add_mesh(
                    mesh, color=color, opacity=1, show_edges=True,
                    edge_color=INK, line_width=1, lighting=view in ("house", "exterior"),
                    ambient=.45, diffuse=.55,
                    name=f"house_{case['key']}_{view}_{i}", reset_camera=False,
                )
                actors.append((actor, box["role"]))
                viewer.actor_views[id(actor)] = view
        viewer.case_actors[case["key"]] = actors


def add_labels(viewer):
    """Text is mesh geometry, so the labels also work in local VTK.js views."""
    import pyvista as pv

    viewer.label_actors = []
    recipe = viewer.data.metadata["recipe"]
    for view in ("vertical", "downstairs", "upstairs"):
        if view == "vertical":
            labels = [("UPSTAIRS", (-1.7, -.12, 4.08), .18, None),
                      ("DOWNSTAIRS", (-1.7, -.12, 1.87), .18, None),
                      ("OPENING", (1.02, -.12, 2.55), .12, "open"),
                      ("SOLID FLOOR", (.5, -.12, 2.55), .12, "closed")]
            points = [recipe["source_xyz_m"], *recipe["receiver_xyz_m"]]
            labels += [(name, (x + .08, -.14, z + .08), .15, None)
                       for name, (x, _, z) in zip(("TX", "A", "B", "C"), points)]
        else:
            z = viewer.data.planes[view].fixed_m
            labels = [(view.upper(), (-1.7, 1.12, z + .08), .18, None)]
            points = [recipe["source_xyz_m"], *recipe["receiver_xyz_m"]]
            labels += [(name, (x + .1, y + .1, z + .09), .15, None)
                       for name, (x, y, height) in zip(("TX", "A", "B", "C"), points)
                       if np.isclose(height, z)]
        for i, (text, position, height, case) in enumerate(labels):
            mesh = pv.Text3D(text, depth=.002, height=height)
            if view == "vertical":
                mesh.rotate_x(90, inplace=True)
            if view == "vertical":
                mesh.translate((-mesh.bounds[0], 0, -mesh.bounds[4]), inplace=True)
            else:
                mesh.translate((-mesh.bounds[0], -mesh.bounds[2], 0), inplace=True)
            mesh.translate(position, inplace=True)
            viewer.geometry.append(mesh)
            actor = viewer.plotter.add_mesh(mesh, color=INK, lighting=False,
                                            name=f"label_{view}_{i}", reset_camera=False)
            viewer.label_actors.append((actor, view, case))
    line = pv.Line((.8, -.12, 2.28), (1.05, -.12, 2.51))
    viewer.geometry.append(line)
    actor = viewer.plotter.add_mesh(line, color=INK, line_width=2,
                                    name="opening_leader", reset_camera=False)
    viewer.label_actors.append((actor, "vertical", "open"))
