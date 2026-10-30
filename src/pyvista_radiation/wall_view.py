"""A small, actual openEMS field experiment displayed with ordinary PyVista."""


import numpy as np

from .nearfield import field_plane_mesh, load_through_wall

CASE_LABELS = {"air": "Air baseline", "dielectric": "Lossy dielectric wall", "metal": "Metal wall (PEC)"}


def case_definitions(data):
    """Case geometry is saved with the solver data, including layers and sheets."""
    return data.metadata.get("case_definitions", [
        dict(key=key, label=CASE_LABELS.get(key, key), model="air" if key == "air" else "bulk",
             bounds_m=data.metadata["wall_bounds_m"]) for key in data.case_names
    ])


def case_bounds(data, case):
    definition = next(item for item in case_definitions(data) if item["key"] == case)
    if definition["model"] == "air":
        return []
    bounds = definition["bounds_m"]
    if definition["model"] == "layered":
        return [[*layer, *bounds[2:]] for layer in definition["layers_m"]]
    return [bounds]


class WallViewer:
    """One horizontal slice of computed fields; retain complex vectors."""

    def __init__(self, data=None, *, off_screen=True):
        import pyvista as pv

        self.data = load_through_wall() if data is None else data
        self.plotter = pv.Plotter(off_screen=off_screen, window_size=(1100, 700))
        self.plotter.set_background("#132d40")
        self.view = None
        self.mesh = None
        self.actor = None
        self.geometry = []
        self.initial_case = ("concrete" if "concrete" in self.data.case_names else
                             "dielectric" if "dielectric" in self.data.case_names else self.data.case_names[0])
        self.initial_mode = "phase" if self.data.metadata.get("experiment") == "material_lab" else "magnitude_db"
        self.initial_phase = 90 if self.initial_mode == "phase" else 0
        self.update(self.initial_case, self.initial_mode, self.initial_phase)
        self.reset_view()

    def update(self, case, mode, phase):
        import pyvista as pv

        data = self.data
        updated = field_plane_mesh(data, case, mode=mode, phase_deg=float(phase))
        cmap = "viridis" if mode == "magnitude_db" else "RdBu_r"
        clim = (-50, 0) if mode == "magnitude_db" else (-0.25, 0.25)
        if self.mesh is not None:
            # Keep dataset, actor and VTK array identities stable during animation.
            # Replacing actors each frame can race the browser geometry cache.
            for name in ("Electric field real (V/m)", "Electric field imaginary (V/m)"):
                self.mesh[name][:] = updated[name]
            self.mesh["Displayed field"][:] = updated.active_scalars
            self.actor.mapper.lookup_table.cmap = cmap
            self.actor.mapper.scalar_range = clim
            for key, actors in self.case_actors.items():
                for actor in actors:
                    actor.SetVisibility(key == case)
            if self.case_actors[case]:
                self.wall_actor = self.case_actors[case][0]
        else:
            self.mesh = updated
            self.mesh.rename_array(updated.active_scalars_name, "Displayed field")
            self.mesh.set_active_scalars("Displayed field")
            self.actor = self.plotter.add_mesh(
                self.mesh, name="field", reset_camera=False, lighting=False,
                scalars="Displayed field", cmap=cmap, clim=clim, show_scalar_bar=False,
            )
            self.case_actors = {}
            for key in data.case_names:
                self.case_actors[key] = []
                for i, bounds in enumerate(case_bounds(data, key)):
                    box = pv.Box(bounds=bounds)
                    self.geometry.append(box)
                    actor = self.plotter.add_mesh(
                        box, color="#d0d9df", opacity=0.12, show_edges=True,
                        edge_color="white", line_width=2, name=f"wall_{key}_{i}", reset_camera=False,
                    )
                    actor.SetVisibility(key == case)
                    self.case_actors[key].append(actor)
            self.wall_actor = (self.case_actors[case] or
                               next(actors for actors in self.case_actors.values() if actors))[0]
            source = data.metadata["source_xyz_m"]
            length = data.metadata["source_length_m"]
            mast = pv.Line([*source[:2], -length / 2], [*source[:2], length / 2])
            marker = pv.Sphere(radius=0.012 * np.ptp(data.x_m), center=source)
            self.geometry.extend([mast, marker])
            self.plotter.add_mesh(mast, color="#ffc857", line_width=6, name="antenna", reset_camera=False)
            self.plotter.add_mesh(marker, color="#ffc857", name="source", reset_camera=False)
            for i, receiver in enumerate(data.metadata["receivers"]):
                point = pv.Sphere(radius=0.009 * np.ptp(data.x_m), center=receiver["xyz_m"])
                self.geometry.append(point)
                self.plotter.add_mesh(point, color="#66d2e7", name=f"receiver_{i}", reset_camera=False)
        self.plotter.reset_camera_clipping_range()
        self.plotter.render()
        if self.view is not None:
            self.view.update()

    def reset_view(self, **_):
        self.plotter.view_xy()
        self.plotter.camera.parallel_projection = True
        self.plotter.camera.parallel_scale = 0.63 * max(np.ptp(self.data.x_m), np.ptp(self.data.y_m))
        self.plotter.reset_camera_clipping_range()
        if self.view is not None:
            self.view.update_camera()

    def close(self):
        self.plotter.close()


def create_wall_app(data=None, *, server_name="through-wall-fields"):
    """Build a local trame viewer of saved solver data, without running openEMS."""
    import asyncio

    from trame.app import get_server
    from trame.ui.html import DivLayout
    from trame.widgets import html
    from trame_pyvista.widgets import PyVistaLocalView

    viewer = WallViewer(data)
    data = viewer.data
    server = get_server(server_name, client_type="vue3")
    state = server.state
    lab = data.metadata.get("experiment") == "material_lab"
    labels = {item["key"]: item["label"] for item in case_definitions(data)}
    state.trame__title = ("Material wave lab" if lab else "Through-wall fields") + " · openEMS × PyVista"
    state.wall_case, state.wall_mode = viewer.initial_case, viewer.initial_mode
    state.wall_phase, state.wall_playing = viewer.initial_phase, False

    def update(**_):
        viewer.update(state.wall_case, state.wall_mode, state.wall_phase)
        i = data.case_names.index(state.wall_case)
        state.wall_caption = labels[state.wall_case]
        definition = next(item for item in case_definitions(data) if item["key"] == state.wall_case)
        state.wall_material_note = definition.get("description", "")
        if "relative_permittivity" in definition:
            state.wall_material_note += (f" · εr = {definition['relative_permittivity']:g}"
                                         f" · conductivity {definition['conductivity_s_per_m']:g} S/m")
        if definition["model"] == "sheet":
            state.wall_material_note += f" · sheet resistance {definition['sheet_resistance_ohm_per_square']:g} Ω/square"
        state.wall_scale = ("Relative |E|: −50 to 0 dB · same air reference for every case"
                            if state.wall_mode == "magnitude_db" else
                            f"Re(Ez) at {float(state.wall_phase):g}° · same reference · colors clipped at ±0.25")
        state.wall_receivers = " · ".join(
            f"{r['name']}: {r['change_vs_air_db'][i]:+.1f} dB" for r in data.metadata["receivers"]
        )

    state.change("wall_case", "wall_mode", "wall_phase")(update)

    async def animate(**_):
        if state.wall_playing:
            return
        state.wall_playing = True
        try:
            state.wall_mode = "phase"
            for angle in range(0, 361, 30):
                state.wall_phase = angle
                state.flush()
                await asyncio.sleep(0.15)
        finally:
            state.wall_playing = False

    update()
    state.wall_style = """<style>
      *{box-sizing:border-box}body{margin:0;background:#edf3f6;color:#132d40;font:15px/1.55 Arial,sans-serif}
      main{max-width:1250px;margin:auto;padding:24px}h1{font:34px Georgia,serif;margin:0 0 8px}
      h2{font:23px Georgia,serif;margin:8px 0}p{margin:10px 0;color:#526674}.eyebrow{font:12px ui-monospace,monospace;color:#1574b8}
      .experiment{padding:20px;background:white;border:1px solid #c8d8e2;border-radius:6px}
      .field-scene{height:580px;background:#132d40;border-radius:5px}.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:end;margin:14px 0}
      label{display:grid;gap:5px;font-size:13px}select,button{font:14px Arial;padding:9px 12px;color:#132d40;background:white;border:1px solid #acbdc9;border-radius:4px}
      .controls select{font-size:13px;padding:9px 8px;max-width:100%}
      button{cursor:pointer}button:disabled{opacity:.5}select:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid #1574b8;outline-offset:3px}
      .readout{font:13px ui-monospace,monospace;padding:10px;background:#edf3f6}.small{font-size:13px}.legend{display:flex;gap:18px;font-size:13px;margin:8px 0}
      .scale{height:9px;background:linear-gradient(90deg,#440154,#3b528b,#21918c,#5ec962,#fde725)}
      .phase{background:linear-gradient(90deg,#053061,#f7f7f7,#67001f)}details{margin:16px 0;color:#526674}summary{cursor:pointer;color:#1574b8}
      @media(max-width:760px){main{padding:14px}h1{font-size:28px}.experiment{padding:14px}.field-scene{height:340px}}
      </style>"""
    with DivLayout(server) as layout:
        html.Div(v_html=("wall_style",))
        with html.Main():
            html.Div(f"ACTUAL SOLVER FIELDS · {data.frequency_hz / 1e9:g} GHz", classes="eyebrow")
            html.H1("Material wave lab" if lab else "What gets through a wall?")
            html.P("Explore a 2.4 × 1.6 × 1 m openEMS scene: eight material and structure cases, with a dipole antenna and three receivers."
                   if lab else "A small 3D openEMS experiment, explored in PyVista. Switch between air, a lossy dielectric and an opaque metal wall.")
            with html.Div(classes="experiment"):
                html.H2("{{ wall_caption }}")
                with html.Div(classes="controls"):
                    with html.Label("Case"):
                        with html.Select(v_model=("wall_case", viewer.initial_case)):
                            for key, name in labels.items():
                                html.Option(name, value=key)
                    with html.Label("Display"):
                        with html.Select(v_model=("wall_mode", "magnitude_db")):
                            html.Option("Field strength", value="magnitude_db")
                            html.Option("Wave phase", value="phase")
                with html.Div(classes="field-scene"):
                    viewer.view = PyVistaLocalView(viewer.plotter, namespace="wall_fields",
                                                    style="width:100%;height:100%")
                with html.Div(classes="controls"):
                    for label, factor in (("+ Zoom in", 1.5), ("− Zoom out", 1 / 1.5)):
                        html.Button(label, click=f"() => {{ const v=trame.refs['{viewer.view.ref_name}']; const c=v.getCamera(); v.setCamera({{...c, parallelScale:c.parallelScale/{factor}}}); }}")
                    html.Button("Top view", click=viewer.reset_view)
                    html.Button("Play one cycle", click=animate, disabled=("wall_playing",))
                html.P("{{ wall_material_note }}", classes="small", v_if="wall_material_note")
                with html.Label("Wave phase (degrees)", v_if="wall_mode === 'phase'"):
                    html.Input(type="range", min=0, max=360, step=15,
                               v_model_number=("wall_phase", 0))
                html.Div(classes=("wall_mode === 'phase' ? 'scale phase' : 'scale'",))
                html.P("{{ wall_scale }}", classes="small")
                html.Div("Gold: dipole antenna · cyan: receivers · outline: wall", classes="legend")
                html.P("Drag to rotate · scroll or use the buttons to zoom. This is a horizontal slice at antenna height through a full 3D simulation.", classes="small")
                html.Div("Field change versus air at the marked receivers", classes="small")
                html.Div("{{ wall_receivers }}", classes="readout")
                html.P("These are changes in total electric-field amplitude, not received dBm or pure wall penetration loss. Interfering waves can increase the field at a particular point.", classes="small")
            html.P("Bulk slabs use 1 GHz material-class examples from ITU-R P.2040-4. The glass stack and resistive film use different geometries. These are reference examples, not measured building products."
                   if lab else "80 mm thick finite wall · εr = 4 · conductivity 0.03 S/m · assumed material, not measured concrete. The metal control is a perfect electric conductor.", classes="small")
            with html.Details():
                html.Summary("Source, solver and limits")
                html.P(f"{data.metadata['source_length_m'] * 1000:g} mm numerical dipole with a 50 Ω feed, normalized to a 1 V incident voltage wave. Cases share the same domain, antenna, receiver positions, grid and frequency. A common display reference preserves differences between cases.")
                html.P("The field includes reflection, transmission through the dielectric and diffraction around the finite wall. A field behind the metal wall can arrive around its edges. The phase control cycles saved steady-state phasors; it does not show pulse arrival time.")
                html.P(f"{data.metadata['grid_spacing_m'] * 1000:g} mm base grid; PML absorbing boundaries on six sides; each saved run must reach the −60 dB energy-decay target. Grid sensitivity and raw solver evidence are archived with the example. This remains a numerical experiment, without product measurements or hardware validation.")
                if lab:
                    html.P("Bulk permittivity and conductivity are held constant at their 1 GHz values. This does not implement the full broadband material law. The conducting-sheet case uses openEMS's thin-sheet approximation, rather than resolving a 100 micrometre film in the volume mesh.")
    server._wall_viewer, server._wall_layout = viewer, layout
    return server, viewer


def serve_wall(data=None, *, port=8767):
    """Serve the saved-field experiment on localhost; leave the city server alone."""
    server, viewer = create_wall_app(data)
    try:
        server.start(host="127.0.0.1", port=port, open_browser=False, timeout=0)
    finally:
        viewer.close()
