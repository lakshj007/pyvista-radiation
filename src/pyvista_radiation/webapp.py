"""Live browser comparison backed by a Python PyVista plotter and trame."""

from .charts import cut_chart, metrics_table, summary
from .mesh import difference_mesh
from .numerics import principal_cut
from .plotting import compare_patterns
from .samples import load_patch

CSS = """
*{box-sizing:border-box}body{margin:0;background:#edf3f6;color:#132d40;font:15px Arial,sans-serif}
.app{max-width:1800px;margin:auto;padding:22px 28px}header{display:flex;align-items:baseline;gap:24px;border-bottom:1px solid #bccbd5;padding-bottom:15px}
h1{font:36px Georgia,serif;margin:0}header span,.note{color:#526674;font-size:13px}
.controls{display:flex;gap:18px;align-items:end;flex-wrap:wrap;padding:18px 0}
label{display:grid;gap:6px;font:12px ui-monospace,monospace;color:#526674}
select,button{font:14px Arial;padding:9px 12px;border:1px solid #acbdc9;background:white;color:#132d40;border-radius:4px}
button{cursor:pointer}select:focus-visible,button:focus-visible{outline:3px solid #1574b8;outline-offset:3px}
.scene{height:440px;position:relative;background:#132d40;border-radius:6px;overflow:hidden}
.scene-labels{position:absolute;inset:16px 20px auto;display:grid;grid-template-columns:1fr 1fr;z-index:2;pointer-events:none;color:white;font-size:24px}
.scene-labels>div:last-child{padding-left:20px}.scene-note{color:#526674;font-size:12px;margin-top:9px}.color-key{display:flex;align-items:center;gap:12px;font:12px ui-monospace,monospace;margin-top:12px}.color-ramp{height:10px;flex:1;background:linear-gradient(90deg,#440154,#3b528b,#21918c,#5ec962,#fde725);border-radius:2px}
.explanation{padding:13px 0;color:#526674;font-size:13px;line-height:1.6}.cuts{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.cut{background:white;padding:16px 18px;border:1px solid #d1dee6;border-radius:6px}.cut h2{font:19px Georgia,serif;margin:0 0 5px}
.cut svg{width:100%;display:block;font:11px Arial;fill:#526674}.legend{display:flex;gap:24px;font:12px ui-monospace,monospace;margin-bottom:8px}
.metrics{margin:18px 0}.metrics table{width:100%;border-collapse:collapse;text-align:left;font:13px ui-monospace,monospace}.metrics th,.metrics td{padding:10px;border-bottom:1px solid #cad7e0}.metrics caption{text-align:left;margin-bottom:10px;font:16px Georgia,serif}.difference-ramp{height:10px;flex:1;background:linear-gradient(90deg,#3b4cc0,#ddd,#b40426)}.difference{margin-top:18px}.a{color:#1574b8}.b{color:#cb5b32}.summary{font:13px ui-monospace,monospace;padding-top:14px}footer{padding:18px 0;color:#526674;font-size:12px}
@media(max-width:760px){.app{padding:14px}header{display:block}h1{font-size:29px}.cuts{grid-template-columns:1fr}.scene{height:340px}.controls{gap:10px}.scene-labels{font-size:19px}}
"""


def create_app(data=None, *, server_name="radiation-comparison"):
    """Build a trame server and viewer; no listening socket until server.start()."""
    import pyvista as pv
    from trame.app import get_server
    from trame.ui.html import DivLayout
    from trame.widgets import html
    from trame_pyvista.widgets import PyVistaLocalView

    data = load_patch() if data is None else data
    # Reject unsupported browser cuts before allocating a plotter or server.
    principal_cut(data, 0, "xz")
    principal_cut(data, 0, "yz")
    server = get_server(server_name, client_type="vue3")
    server.state.trame__title = "Patch antenna · radiation comparison"
    state = server.state
    state.style_html = "<style>" + CSS + "</style>"
    state.left_index = 0
    state.right_index = len(data.frequency_hz) - 1
    state.display_mode = "pattern"
    state.radial_scale = "db"
    state.normalization = "per_frequency"
    state.floor_db = -30
    viewer = compare_patterns(
        data,
        (state.left_index, state.right_index),
        off_screen=True,
        radial_scale="db",
        floor_db=-30,
    )
    for panel in range(2):
        viewer.plotter.remove_scalar_bar(f"Panel {panel + 1}: relative field (dB)", render=False)

    viewer.camera_preset("back")
    diff_plotter = pv.Plotter(off_screen=True, window_size=(900, 350))
    diff_plotter.set_background("#132d40")
    diff_mesh = difference_mesh(data, 0, len(data.frequency_hz) - 1, floor_db=-30)
    diff_actor = diff_plotter.add_mesh(
        diff_mesh,
        scalars="B - A (dB)",
        cmap="coolwarm",
        clim=(-20, 20),
        smooth_shading=True,
        show_scalar_bar=False,
    )
    diff_plotter.add_axes(color="white")
    diff_plotter.camera_position = viewer.plotter.camera_position
    diff_plotter.camera.parallel_projection = True
    diff_plotter.camera.parallel_scale = 1.3

    def text_state():
        indices = viewer.indices
        state.left_label = f"{data.frequency_hz[indices[0]] / 1e9:g} GHz"
        state.right_label = f"{data.frequency_hz[indices[1]] / 1e9:g} GHz"
        state.xz_svg = cut_chart(
            data, indices, "xz", viewer.options["normalization"], viewer.options["floor_db"]
        )
        state.yz_svg = cut_chart(
            data, indices, "yz", viewer.options["normalization"], viewer.options["floor_db"]
        )
        state.summary = summary(data, indices)
        state.metrics_html = metrics_table(data, indices)
        state.floor_label = f"{viewer.options['floor_db']:g} dB"
        state.reference_note = (
            "Each frequency uses its own peak. Compare pattern shape."
            if viewer.options["normalization"] == "per_frequency"
            else "Shared reference: maximum saved field over all frequencies. This is not gain or efficiency."
        )
        state.radius_note = (
            "Unit sphere: color shows the angular field."
            if viewer.options["mode"] == "sphere"
            else "Radius: relative field amplitude (display only)."
            if viewer.options["radial_scale"] == "linear"
            else "Radius: (relative dB − floor) / (−floor). A display scale that reveals weaker lobes."
        )

    text_state()
    with DivLayout(server) as layout:
        html.Div(v_html=("style_html",))
        with html.Div(classes="app"):
            with html.Header():
                html.H1("Patch antenna / frequency study")
                html.Span("openEMS reference · 32 × 40 mm patch · PyVista")
            with html.Div(classes="controls"):
                for label, key in [
                    ("Left frequency", "left_index"),
                    ("Right frequency", "right_index"),
                ]:
                    with html.Label(label):
                        with html.Select(v_model=(key, state[key]), aria_label=label):
                            for i, f in enumerate(data.frequency_hz):
                                html.Option(f"{f / 1e9:g} GHz", value=str(i))
                for label, key, items in [
                    (
                        "View",
                        "display_mode",
                        [("pattern", "Radiation surface"), ("sphere", "Colored unit sphere")],
                    ),
                    (
                        "Radius scale",
                        "radial_scale",
                        [
                            ("db", "Decibels · reveal weak lobes"),
                            ("linear", "Linear field amplitude"),
                        ],
                    ),
                    (
                        "Normalization",
                        "normalization",
                        [
                            ("per_frequency", "Peak at each frequency"),
                            ("global", "Shared peak across dataset"),
                        ],
                    ),
                    (
                        "Color floor",
                        "floor_db",
                        [
                            ("-20", "−20 dB"),
                            ("-30", "−30 dB"),
                            ("-40", "−40 dB"),
                            ("-60", "−60 dB"),
                        ],
                    ),
                ]:
                    with html.Label(label):
                        with html.Select(v_model=(key, state[key]), aria_label=label):
                            for value, text in items:
                                html.Option(text, value=value)
                html.Button("Reset camera", click=server.controller.reset_camera)
                for name in ("front", "back", "side", "isometric"):
                    html.Button(
                        name.title(), click=(server.controller.camera_preset, f"['{name}']")
                    )
            with html.Div(classes="scene"):
                with html.Div(classes="scene-labels"):
                    html.Div("{{ left_label }}")
                    html.Div("{{ right_label }}")
                view = PyVistaLocalView(viewer.plotter, style="width:100%;height:100%")
            with html.Div(classes="color-key"):
                html.Span("{{ floor_label }}")
                html.Div(classes="color-ramp")
                html.Span("0 dB")
            html.Div("Drag to rotate · Scroll to zoom · Views share a camera", classes="scene-note")
            with html.Div(classes="explanation"):
                html.Div("{{ reference_note }}")
                html.Div(
                    "{{ radius_note }} Color and cuts: relative electric field in dB, with shared limits."
                )
            with html.Div(classes="legend"):
                html.Span("━━ {{ left_label }}", classes="a")
                html.Span("━━ {{ right_label }}", classes="b")
            with html.Div(classes="cuts"):
                for plane, key, title in [
                    ("xz", "xz_svg", "xz plane · φ = 0° / 180°"),
                    ("yz", "yz_svg", "yz plane · φ = 90° / 270°"),
                ]:
                    with html.Div(classes="cut"):
                        html.H2(title)
                        html.Div("Relative field (dB) vs signed θ", classes="note")
                        html.Div(v_html=(key,))
            with html.Div(classes="metrics"):
                html.Div(v_html=("metrics_html",))
            with html.Div(classes="cut difference"):
                html.H2("Difference map · right minus left")
                html.Div(
                    "Red: right frequency is stronger · Blue: left is stronger. Uses the selected normalization and floor.",
                    classes="note",
                )
                diff_view = PyVistaLocalView(
                    diff_plotter, style="width:100%;height:300px", namespace="pattern_difference"
                )
                with html.Div(classes="color-key"):
                    html.Span("−20 dB or less")
                    html.Div(classes="difference-ramp")
                    html.Span("+20 dB or more")
                html.Div(
                    "Unit sphere; values outside ±20 dB saturate. Both fields at the floor give zero difference.",
                    classes="note",
                )
            html.Footer(
                "Saved solver fields remain unchanged. Numerical integration and principal cuts are tested against analytic patterns and independent openEMS outputs."
            )

    @state.change(
        "left_index", "right_index", "display_mode", "radial_scale", "normalization", "floor_db"
    )
    def update(**_):
        indices = (int(state.left_index), int(state.right_index))
        viewer.configure(
            mode=state.display_mode,
            radial_scale=state.radial_scale,
            normalization=state.normalization,
            floor_db=float(state.floor_db),
        )
        for panel, index in enumerate(indices):
            if viewer.indices[panel] != index:
                viewer.set_frequency(panel, index)
        updated = difference_mesh(
            data, *indices, normalization=state.normalization, floor_db=float(state.floor_db)
        )
        server._difference_mesh = updated
        diff_actor.mapper.dataset = updated
        text_state()
        view.update()
        diff_view.update()

    def reset_camera():
        viewer.reset_camera()
        view.update_camera()
        diff_plotter.camera_position = viewer.plotter.camera_position
        diff_view.update_camera()

    def camera_preset(name):
        viewer.camera_preset(name)
        diff_plotter.camera_position = viewer.plotter.camera_position
        view.update_camera()
        diff_view.update_camera()

    server.controller.camera_preset = camera_preset
    server.controller.reset_camera = reset_camera
    # Retain UI and scene while the server is running.
    server._difference_plotter = diff_plotter
    server._difference_mesh = diff_mesh
    server._radiation_viewer = viewer
    server._radiation_layout = layout
    return server, viewer


def serve(data=None, *, port=8766):
    """Run a localhost-only comparison app; Ctrl+C stops it."""
    server, viewer = create_app(data)
    try:
        server.start(host="127.0.0.1", port=port, open_browser=False)
    finally:
        viewer.close()
        server._difference_plotter.close()
