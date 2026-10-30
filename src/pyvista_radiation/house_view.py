"""Native PyVista cutaways, floor planes and recorded pulse playback."""

import numpy as np

from .house_fields import house_slice_mesh, load_house


class HouseViewer:
    """Stable actors for every recording grid; changing views never reruns FDTD."""

    def __init__(self, data=None, *, off_screen=True):
        import pyvista as pv

        self.data = load_house() if data is None else data
        self.plotter = pv.Plotter(off_screen=off_screen, window_size=(1100, 800))
        self.plotter.set_background("#132d40")
        self.plotter.add_axes(color="white")
        self.view = None
        self.meshes, self.field_actors, self.geometry, self.case_actors = {}, {}, [], {}
        self.case, self.plane, self.mode = self.data.case_names[0], "vertical", "pulse"
        self.frame = int(np.argmin(abs(self.data.time_s[self.case] - 28e-9)))
        for key in ("pulse", "vertical", "downstairs", "upstairs"):
            mesh = house_slice_mesh(self.data, self.case, "vertical" if key == "pulse" else key,
                                    mode="pulse" if key == "pulse" else "phase", frame=self.frame)
            self.meshes[key] = mesh
            actor = self.plotter.add_mesh(mesh, scalars="Displayed field", name="field_" + key,
                                          cmap="RdBu_r", clim=(-.25, .25), lighting=False,
                                          show_scalar_bar=False, reset_camera=False)
            actor.SetVisibility(key == "pulse")
            self.field_actors[key] = actor
        for case in self.data.metadata["recipe"]["cases"]:
            actors = []
            for i, box in enumerate(case["boxes"]):
                mesh = pv.Box(bounds=box["bounds_m"])
                self.geometry.append(mesh)
                color = "#d2b47b" if box["material"] == "timber" else "#9bb1c4"
                actor = self.plotter.add_mesh(mesh, color=color, opacity=.08,
                                              show_edges=True, edge_color=color, line_width=1.5,
                                              name=f"house_{case['key']}_{i}", reset_camera=False)
                actors.append((actor, box["role"]))
            self.case_actors[case["key"]] = actors
        recipe = self.data.metadata["recipe"]
        source = np.array(recipe["source_xyz_m"])
        a, b = source.copy(), source.copy()
        a[1] -= recipe["source_length_m"] / 2
        b[1] += recipe["source_length_m"] / 2
        antenna = pv.Line(a, b)
        marker = pv.Sphere(radius=.055, center=source)
        self.geometry.extend([antenna, marker])
        self.plotter.add_mesh(antenna, color="#ffc857", line_width=6, name="antenna", reset_camera=False)
        self.plotter.add_mesh(marker, color="#ffc857", name="source", reset_camera=False)
        for i, receiver in enumerate(recipe["receiver_xyz_m"]):
            mesh = pv.Sphere(radius=.045, center=receiver)
            self.geometry.append(mesh)
            self.plotter.add_mesh(mesh, color="#67d3e5", name=f"receiver_{i}", reset_camera=False)
        self.update(self.case, "vertical", "pulse", self.frame)
        self.camera("section")

    def update(self, case, plane, mode, frame=0, phase=90, exterior=False):
        if mode == "pulse":
            plane = "vertical"
            frame = max(0, min(int(frame), len(self.data.time_s[case]) - 1))
        key = "pulse" if mode == "pulse" else plane
        updated = house_slice_mesh(self.data, case, plane, mode=mode, frame=frame, phase_deg=phase)
        mesh = self.meshes[key]
        for name in updated.point_data.keys():
            mesh[name][:] = updated[name]
        if mode == "pulse":
            mesh.field_data["Recorded time (s)"] = [self.data.time_s[case][frame]]
        for name, actor in self.field_actors.items():
            actor.SetVisibility(name == key)
        actor = self.field_actors[key]
        actor.mapper.lookup_table.cmap = "viridis" if mode == "magnitude_db" else "RdBu_r"
        actor.mapper.scalar_range = (-60, 0) if mode == "magnitude_db" else (-.25, .25)
        for name, actors in self.case_actors.items():
            for building, role in actors:
                building.SetVisibility(name == case and (exterior or role not in ("front", "back", "roof")))
        plane_changed = plane != self.plane
        self.case, self.plane, self.mode, self.frame = case, plane, mode, frame
        self.plotter.reset_camera_clipping_range()
        self.plotter.render()
        if self.view is not None:
            self.view.update()
            if plane_changed:
                self.camera("section")

    def camera(self, preset="section", **_):
        if preset == "house":
            position = [(7, -8, 6), (0, 0, 2.25), (0, 0, 1)]
            scale = 4.3
        elif self.plane == "vertical":
            position = [(0, -12, 2.35), (0, 0, 2.35), (0, 0, 1)]
            scale = 3.3
        else:
            z = self.data.planes[self.plane].fixed_m
            position = [(0, 0, z + 12), (0, 0, z), (0, 1, 0)]
            scale = 3.1
        self.plotter.camera_position = position
        self.plotter.camera.parallel_projection = True
        self.plotter.camera.parallel_scale = scale
        self.plotter.reset_camera_clipping_range()
        if self.view is not None:
            self.view.update_camera()

    def close(self):
        self.plotter.close()


def create_house_app(data=None, *, server_name="two-floor-wave-house"):
    """Explore saved house records on a separate page; never calculate fake pulses."""
    import asyncio

    from trame.app import get_server
    from trame.ui.html import DivLayout
    from trame.widgets import html
    from trame_pyvista.widgets import PyVistaLocalView

    viewer = HouseViewer(data)
    data = viewer.data
    server = get_server(server_name, client_type="vue3")
    s = server.state
    s.trame__title = "Two-floor wave house · openEMS × PyVista"
    s.house_case, s.house_mode, s.house_plane = viewer.case, "pulse", "vertical"
    s.house_frame, s.house_phase, s.house_exterior, s.house_playing = viewer.frame, 90, False, False
    labels = {c["key"]: c["label"] for c in data.metadata["recipe"]["cases"]}

    def update(**_):
        if s.house_mode == "pulse":
            s.house_plane = "vertical"
        s.house_frame_max = len(data.time_s[s.house_case]) - 1
        s.house_frame = max(0, min(int(s.house_frame), s.house_frame_max))
        viewer.update(s.house_case, s.house_plane, s.house_mode, int(s.house_frame),
                      float(s.house_phase), bool(s.house_exterior))
        s.house_caption = labels[s.house_case]
        if s.house_mode == "pulse":
            t = data.time_s[s.house_case][int(s.house_frame)] * 1e9
            s.house_time_label = f"Recorded time: {t:.2f} ns"
            s.house_scale = f"Recorded Ey(t) · {t:.2f} ns · shared air reference; colors clip at ±0.25"
        elif s.house_mode == "phase":
            s.house_scale = f"Steady Re(Ey) at {float(s.house_phase):g}° · 500 MHz · shared air reference"
        else:
            s.house_scale = "Steady electric-field magnitude · −60 to 0 dB · shared air reference"
        i = data.case_names.index(s.house_case)
        s.house_receivers = " · ".join(f"{r['name']}: {r['change_vs_air_db'][i]:+.1f} dB"
                                       for r in data.metadata["receivers"])

    s.change("house_case", "house_mode", "house_plane", "house_frame", "house_phase", "house_exterior")(update)

    server._house_animation = None

    async def animate():
        try:
            if s.house_mode == "pulse":
                values, key = range(len(data.time_s[s.house_case])), "house_frame"
            else:
                s.house_mode = "phase"
                values, key = range(0, 361, 15), "house_phase"
            for value in values:
                if not s.house_playing:
                    break
                s[key] = value
                s.flush()
                await asyncio.sleep(.065)
        finally:
            s.house_playing = False
            s.flush()

    def play(**_):
        # Return immediately so the browser can send a pause command while the
        # animation task runs. Awaiting animation inside the RPC queues pause.
        task = server._house_animation
        if task is not None and not task.done():
            task.cancel()
            s.house_playing = False
            s.flush()
            return
        s.house_playing = True
        s.flush()
        server._house_animation = asyncio.create_task(animate())

    server.controller.house_play = play
    update()
    s.house_css = """<style>
      *{box-sizing:border-box}body{margin:0;background:#edf3f6;color:#132d40;font:15px/1.55 Arial,sans-serif}
      main{max-width:1350px;margin:auto;padding:24px}h1{font:34px Georgia,serif;margin:0 0 8px}h2{font:23px Georgia,serif;margin:8px 0}
      p{margin:10px 0;color:#526674}.eyebrow{font:12px ui-monospace,monospace;color:#1574b8}.experiment{padding:20px;background:white;border:1px solid #c8d8e2;border-radius:6px}
      .house-scene{height:680px;background:#132d40;border-radius:5px}.controls{display:flex;flex-wrap:wrap;gap:10px;align-items:end;margin:12px 0}
      label{display:grid;gap:5px;font-size:13px}select,button{font:13px Arial;padding:9px 8px;color:#132d40;background:white;border:1px solid #acbdc9;border-radius:4px;max-width:100%}
      button{cursor:pointer}button:disabled,select:disabled{opacity:.6}select:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid #1574b8;outline-offset:3px}
      .small{font-size:13px}.readout{font:13px ui-monospace,monospace;background:#edf3f6;padding:10px}.scale{height:9px;background:linear-gradient(90deg,#053061,#f7f7f7,#67001f)}
      .magnitude{background:linear-gradient(90deg,#440154,#3b528b,#21918c,#5ec962,#fde725)}details{margin:16px 0;color:#526674}summary{cursor:pointer;color:#1574b8}
      @media(max-width:760px){main{padding:14px}h1{font-size:28px}.experiment{padding:14px}.house-scene{height:420px}}
      </style>"""
    with DivLayout(server) as layout:
        html.Div(v_html=("house_css",))
        with html.Main():
            html.Div("ACTUAL 3D SOLVER FIELDS · 500 MHz", classes="eyebrow")
            html.H1("Two-floor wave house")
            html.P("A compact 4 × 3 m, two-level structure. Follow a downstairs transmitter through floors, rooms and a stairwell opening.")
            with html.Div(classes="experiment"):
                html.H2("{{ house_caption }}")
                with html.Div(classes="controls"):
                    with html.Label("Case"):
                        with html.Select(v_model=("house_case", viewer.case), disabled=("house_playing",)):
                            for key, label in labels.items():
                                html.Option(label, value=key)
                    with html.Label("Display"):
                        with html.Select(v_model=("house_mode", "pulse"), disabled=("house_playing",)):
                            html.Option("Recorded pulse", value="pulse")
                            html.Option("Steady field strength", value="magnitude_db")
                            html.Option("Steady wave phase", value="phase")
                    with html.Label("Slice", v_if="house_mode !== 'pulse'"):
                        with html.Select(v_model=("house_plane", "vertical"), disabled=("house_playing",)):
                            for p in data.metadata["recipe"]["slices"]:
                                html.Option(p["label"], value=p["key"])
                with html.Div(classes="house-scene"):
                    viewer.view = PyVistaLocalView(viewer.plotter, namespace="house_fields", style="width:100%;height:100%")
                with html.Div(classes="controls"):
                    html.Button("{{ house_playing ? 'Pause' : (house_mode === 'pulse' ? 'Play recorded pulse' : 'Play one cycle') }}", click=play)
                    html.Button("Section view", click=lambda **_: viewer.camera("section"))
                    html.Button("3D house", click=lambda **_: viewer.camera("house"))
                    for label, factor in (("+ Zoom", 1.5), ("− Zoom", 1 / 1.5)):
                        html.Button(label, click=f"() => {{ const v=trame.refs['{viewer.view.ref_name}']; const c=v.getCamera(); v.setCamera({{...c, parallelScale:c.parallelScale/{factor}}}); }}")
                with html.Label("{{ house_time_label }}", v_if="house_mode === 'pulse'"):
                    html.Input(type="range", min=0, max=("house_frame_max",), step=1,
                               v_model_number=("house_frame", viewer.frame), disabled=("house_playing",))
                with html.Label("Wave phase (degrees)", v_if="house_mode === 'phase'"):
                    html.Input(type="range", min=0, max=360, step=15,
                               v_model_number=("house_phase", 90), disabled=("house_playing",))
                html.Div(classes=("house_mode === 'magnitude_db' ? 'scale magnitude' : 'scale'",))
                html.P("{{ house_scale }}", classes="small")
                with html.Label():
                    html.Input(type="checkbox", v_model=("house_exterior", False))
                    html.Span("Show full exterior (display only)")
                html.P("Gold: horizontal dipole · cyan: receivers · warm outlines: timber slabs · cool outlines: partitions. Drag to rotate.", classes="small")
                html.P("Pulse playback uses actual recorded Ey samples on the vertical cut. Choose a steady display to inspect either floor. Red and blue indicate opposite field directions.", classes="small")
                html.Div("Steady 500 MHz field change versus air", v_if="house_mode !== 'pulse'", classes="small")
                html.Div("{{ house_receivers }}", v_if="house_mode !== 'pulse'", classes="readout")
            html.P("The stairwell is an air opening; stairs, furniture and glazing are not modeled. Filling the opening changes the simulated floor. Hiding exterior walls only changes the picture.", classes="small")
            with html.Details():
                html.Summary("Source, recordings and limits")
                html.P("Full 3D openEMS FDTD with a 250 mm y-directed dipole and 50 Ω feed. The horizontal antenna radiates in the vertical cut. Wood-class slab parameters and assumed homogeneous partitions are held constant at 500 MHz; this is not a Wi-Fi-band or measured-house prediction.")
                html.P("The 25 mm solver grid has not undergone a house-specific mesh convergence study. All accepted runs reach −60 dB residual energy. Pulse recording is spatially sampled every 50 mm and ends at 55 ns or earlier solver termination. Original per-case timestamps are retained without interpolation or padding.")
                html.P("Recorded pulse Ey values use the original Gaussian port drive. Steady fields use a 1 V incident feed wave at 500 MHz. Each mode has its own shared air display reference; pulse amplitude and steady magnitude are different quantities.")
                html.P("Total fields include transmission, reflections and interference. A stronger point field does not imply more total radiated power. No feed-to-device received dBm, reinforcement, construction variability or hardware validation is provided.")
    server._house_viewer, server._house_layout = viewer, layout
    return server, viewer


def serve_house(data=None, *, port=8769):
    """Serve saved two-floor fields on localhost without rerunning openEMS."""
    server, viewer = create_house_app(data)
    try:
        server.start(host="127.0.0.1", port=port, open_browser=False, timeout=0)
    finally:
        if server._house_animation is not None:
            server._house_animation.cancel()
        viewer.close()
