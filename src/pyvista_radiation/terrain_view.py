"""PyVista terrain coverage meshes and a trame panel for the comparison app."""

import numpy as np

from .environments import ENVIRONMENTS, environment_roads, synthetic_environment
from .terrain import coverage_map, path_profile


def building_mesh(buildings, vertical_exaggeration=1):
    """Merge visible building boxes; never infer radio loss from their colors."""
    import pyvista as pv

    if not buildings:
        return None
    meshes = []
    for b in buildings:
        box = pv.Box(bounds=(b.xmin, b.xmax, b.ymin, b.ymax,
                             b.base_m * vertical_exaggeration, b.roof_m * vertical_exaggeration))
        box.cell_data["Building vertical extent (m)"] = np.full(box.n_cells, b.roof_m - b.base_m)
        meshes.append(box)
    return pv.merge(meshes)


def road_meshes(terrain, kind, vertical_exaggeration=1):
    """Drape contextual road ribbons over the exact same ground as coverage."""
    import pyvista as pv

    meshes = []
    for center, width in environment_roads(kind):
        tangent = np.gradient(center, axis=0)
        normal = np.column_stack([-tangent[:, 1], tangent[:, 0]])
        normal /= np.linalg.norm(normal, axis=1)[:, None]
        edges = np.stack([center + width / 2 * normal, center - width / 2 * normal], axis=1)
        xy = edges.reshape(-1, 2)
        xy[:, 0] = np.clip(xy[:, 0], terrain.x_m[0], terrain.x_m[-1])
        xy[:, 1] = np.clip(xy[:, 1], terrain.y_m[0], terrain.y_m[-1])
        z = (terrain.sample(xy[:, 0], xy[:, 1]) + 0.6) * vertical_exaggeration
        i = 2 * np.arange(len(center) - 1)
        faces = np.column_stack([np.full(len(i), 4), i, i + 1, i + 3, i + 2])
        meshes.append(pv.PolyData(np.column_stack([xy, z]), faces))
    return meshes


def terrain_mesh(terrain, result, *, quantity="received", vertical_exaggeration=1):
    """Create a colored terrain surface; vertical exaggeration affects display only."""
    import pyvista as pv

    if not np.isfinite(vertical_exaggeration) or vertical_exaggeration <= 0:
        raise ValueError("vertical exaggeration must be positive")
    xx, yy = np.meshgrid(terrain.x_m, terrain.y_m)
    mesh = pv.StructuredGrid(xx, yy, terrain.elevation_m * vertical_exaggeration)
    options = {
        "received": (np.clip(result.received_dbm, -140, 0), "Estimated received power (dBm)"),
        "diffraction": (result.diffraction_db, "Added terrain loss (dB)"),
        "los": (
            np.where(result.valid, result.line_of_sight.astype(float), np.nan),
            "Geometric line of sight",
        ),
        "elevation": (terrain.elevation_m, "Ground elevation (m)"),
    }
    if quantity not in options:
        raise ValueError("quantity must be received, diffraction, los or elevation")
    values, name = options[quantity]
    mesh[name] = values.ravel(order="F")
    mesh["Ground elevation (m)"] = terrain.elevation_m.ravel(order="F")
    mesh.field_data["Vertical display exaggeration"] = [vertical_exaggeration]
    return mesh


def profile_svg(profile):
    """Plot ground, effective-Earth profile and direct sight line in local metres."""
    left, right, top, bottom = 55, 665, 18, 185
    length = profile.distance_m[-1]
    lo = min(profile.terrain_m.min(), profile.sightline_m.min()) - 10
    hi = max(profile.effective_terrain_m.max(), profile.sightline_m.max()) + 15

    def x(d):
        return left + d / length * (right - left)

    def y(h):
        return bottom - (h - lo) / (hi - lo) * (bottom - top)

    def line(values, color, width, dash=""):
        path = " ".join(
            f"{'M' if i == 0 else 'L'}{x(d):.2f},{y(h):.2f}"
            for i, (d, h) in enumerate(zip(profile.distance_m, values))
        )
        return f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{width}" stroke-dasharray="{dash}"/>'

    svg = [
        '<svg viewBox="0 0 700 220" role="img" aria-label="Terrain path profile and direct sight line">'
    ]
    for h in np.linspace(lo, hi, 4):
        svg.append(
            f'<path d="M{left},{y(h)} H{right}" stroke="#dfe7ec"/><text x="48" y="{y(h) + 4}" text-anchor="end">{h:.0f}</text>'
        )
    for d in np.linspace(0, length, 5):
        svg.append(f'<text x="{x(d)}" y="205" text-anchor="middle">{d:.0f} m</text>')
    svg.extend(
        [
            line(profile.terrain_m, "#81674b", 2.5),
            line(profile.obstruction_m, "#65788b", 2),
            line(profile.effective_terrain_m, "#a38868", 1, "3 3"),
            line(profile.sightline_m, "#1574b8", 2, "6 4"),
        ]
    )
    k = profile.dominant_index
    svg.append(
        f'<circle cx="{x(profile.distance_m[k]):.2f}" cy="{y(profile.effective_terrain_m[k]):.2f}" r="4" fill="#cb5b32"/>'
    )
    return "".join(svg) + "</svg>"


class TerrainPanel:
    """Live approximate propagation controls; independent of saved pattern meshes."""

    def __init__(self, server, data, terrain=None, *, initial_kind="ridge"):
        import pyvista as pv

        self.server = server
        self.data = data
        self.custom_terrain = terrain
        self.plotter = pv.Plotter(off_screen=True, window_size=(1100, 500))
        self.plotter.set_background("#132d40")
        self.plotter.add_axes(color="white")
        self.mesh = None
        self.result = None
        self.unavailable = not np.any(data.field_magnitude > 0)
        self.actor = None
        self.view = None
        self.context_meshes = []
        s = server.state
        defaults = dict(
            kind=initial_kind,
            position="west",
            frequency=1 if len(data.frequency_hz) > 1 else 0,
            tx_height=30,
            rx_height=2,
            power=30,
            peak_gain=0,
            heading=0,
            elevation=0,
            model="diffraction",
            quantity="received",
            exaggeration=1 if initial_kind == "hillside_city" else 3,
            receiver="far",
            threshold=-90,
        )
        for key, value in defaults.items():
            s[f"terrain_{key}"] = value
        s.terrain_error = ""
        if self.unavailable:
            s.terrain_error = "Coverage needs a nonzero saved antenna pattern. Radiation comparisons remain available below."
        else:
            usable = np.flatnonzero(np.max(data.field_magnitude, axis=(1, 2)) > 0)
            if int(s.terrain_frequency) not in usable:
                s.terrain_frequency = int(usable[0])
            self.calculate(reset=True)

    def calculate(self, reset=False, **_):
        try:
            self._calculate(reset=reset)
        except ValueError as exc:
            self.server.state.terrain_error = (
                f"Could not calculate: {exc}. Check the terrain, frequency and gain. "
                + (
                    "Previous map is retained."
                    if self.result is not None
                    else "No coverage result is available."
                )
            )
        else:
            self.server.state.terrain_error = ""

    def reset_view(self, push=True, **_):
        """Frame the currently calculated scene without applying pending settings."""
        if self.mesh is None:
            return
        t = self.terrain
        span = max(np.ptp(t.x_m), np.ptp(t.y_m))
        target = (np.mean(t.x_m), np.mean(t.y_m), 0.2 * np.max(self.mesh.points[:, 2]))
        self.plotter.camera_position = [
            (target[0] - 0.85 * span, target[1] - 1.1 * span, 0.85 * span),
            target, (0, 0, 1),
        ]
        self.plotter.camera.parallel_projection = True
        self.plotter.camera.parallel_scale = 0.68 * span
        self.plotter.reset_camera_clipping_range()
        self.plotter.render()
        if push and self.view is not None:
            self.view.update_camera()

    def _calculate(self, reset=False):
        import pyvista as pv

        s = self.server.state
        scene_key = "custom" if self.custom_terrain is not None else s.terrain_kind
        reset = reset or getattr(self, "scene_key", None) != scene_key
        if self.custom_terrain is not None:
            self.terrain, self.buildings = self.custom_terrain, ()
        else:
            self.terrain, self.buildings = synthetic_environment(s.terrain_kind)
        t = self.terrain
        position = {"west": 0.1, "center": 0.5, "east": 0.9}[s.terrain_position]
        self.tx_xy = (t.x_m[0] + position * np.ptp(t.x_m), (t.y_m[0] + t.y_m[-1]) / 2)
        self.index = int(s.terrain_frequency)
        self.result = coverage_map(
            t,
            self.data.frequency_hz[self.index],
            tx_xy=self.tx_xy,
            tx_height_m=float(s.terrain_tx_height),
            rx_height_m=float(s.terrain_rx_height),
            tx_power_dbm=float(s.terrain_power),
            tx_peak_gain_dbi=float(s.terrain_peak_gain),
            pattern=self.data,
            pattern_index=self.index,
            heading_deg=float(s.terrain_heading),
            elevation_deg=float(s.terrain_elevation),
            diffraction=s.terrain_model == "diffraction",
            buildings=self.buildings,
        )
        self.scene_key = scene_key
        scale = float(s.terrain_exaggeration)
        self.mesh = terrain_mesh(
            t, self.result, quantity=s.terrain_quantity, vertical_exaggeration=scale
        )
        name = self.mesh.active_scalars_name
        clim, cmap = (
            {
                "received": ((-120, -40), "viridis"),
                "diffraction": ((0, 50), "magma"),
                "los": ((0, 1), "RdYlGn"),
                "elevation": ((float(t.elevation_m.min()),
                               max(float(t.elevation_m.max()), float(t.elevation_m.min()) + 1)),
                              "gist_earth"),
            }
        )[s.terrain_quantity]
        # Retain mesh ownership; rebuilding actors must not reset the camera.
        self.plotter.remove_actor("terrain", reset_camera=False, render=False)
        self.actor = self.plotter.add_mesh(
            self.mesh,
            scalars=name,
            cmap=cmap,
            clim=clim,
            name="terrain",
            show_scalar_bar=False,
            nan_color="#7a8790",
            smooth_shading=True,
        )
        self.plotter.remove_actor("buildings", reset_camera=False, render=False)
        for name in getattr(self, "context_actor_names", []):
            self.plotter.remove_actor(name, reset_camera=False, render=False)
        self.context_actor_names = []
        self.context_meshes = []
        boxes = building_mesh(self.buildings, scale)
        if boxes is not None:
            self.context_meshes.append(boxes)
            self.plotter.add_mesh(
                boxes, scalars="Building vertical extent (m)",
                cmap=["#8198aa", "#c0cbd1", "#f1eee4"], clim=(0, 200),
                show_scalar_bar=False, show_edges=True, edge_color="#4c667b",
                name="buildings", reset_camera=False,
            )
        if self.custom_terrain is None:
            for i, road in enumerate(road_meshes(t, s.terrain_kind, scale)):
                name = f"context_road_{i}"
                self.context_meshes.append(road)
                self.context_actor_names.append(name)
                self.plotter.add_mesh(road, color="#364857", name=name, reset_camera=False,
                                     show_scalar_bar=False, lighting=False)
        xyz = np.array(self.result.metadata["tx_xyz_m"])
        ground = float(t.sample(*self.tx_xy))
        self.plotter.add_mesh(
            pv.Line([xyz[0], xyz[1], ground * scale], [xyz[0], xyz[1], xyz[2] * scale]),
            color="#ffffff",
            line_width=6,
            name="transmitter_mast",
            reset_camera=False,
        )
        self.plotter.add_mesh(
            pv.Sphere(radius=0.007 * np.ptp(t.x_m), center=[xyz[0], xyz[1], xyz[2] * scale]),
            color="#fdc85c",
            name="transmitter",
            reset_camera=False,
        )
        fraction = {
            "far": (0.9, 0.5),
            "near": (0.3, 0.5),
            "north": (0.85, 0.9),
            "south": (0.85, 0.1),
        }[s.terrain_receiver]
        if self.buildings:
            fraction = {
                "far": (0.9 if position < 0.9 else 0.1, 0.5),
                "near": (0.3, 0.5), "north": (0.875, 0.875), "south": (0.875, 0.125),
            }[s.terrain_receiver]
        elif position == 0.9 and s.terrain_receiver == "far":
            fraction = (0.1, 0.5)
        if position == 0.5 and s.terrain_receiver == "near":
            fraction = (0.3, 0.5)
        rx_xy = (t.x_m[0] + fraction[0] * np.ptp(t.x_m), t.y_m[0] + fraction[1] * np.ptp(t.y_m))
        rx = np.r_[rx_xy, float(t.sample(*rx_xy)) + float(s.terrain_rx_height)]
        profile = path_profile(t, xyz, rx, self.data.frequency_hz[self.index], buildings=self.buildings)
        self.plotter.add_mesh(
            pv.Line([*xyz[:2], xyz[2] * scale], [*rx[:2], rx[2] * scale]),
            color="#f8c763",
            line_width=3,
            name="inspected_path",
            reset_camera=False,
        )
        self.plotter.add_mesh(
            pv.Sphere(radius=12, center=[*rx[:2], rx[2] * scale]),
            color="#f8c763",
            name="receiver",
            reset_camera=False,
        )
        valid = self.result.valid
        covered = np.count_nonzero(
            valid & (self.result.received_dbm >= float(s.terrain_threshold))
        ) / max(1, np.count_nonzero(valid))
        s.terrain_status = f"{100 * covered:.1f}% of sampled outdoor receivers above {float(s.terrain_threshold):g} dBm · {100 * np.mean(self.result.line_of_sight[valid]):.1f}% clear sight lines"
        s.terrain_source = t.source
        s.terrain_profile_svg = profile_svg(profile)
        s.terrain_path_note = f"Inspected path: {profile.distance_m[-1]:.0f} m · {'Clear sight line' if profile.line_of_sight else 'Terrain or buildings block direct sight line'} · dominant-edge loss {profile.diffraction_db:.1f} dB"
        s.terrain_applied = f"Calculated at {self.data.frequency_hz[self.index] / 1e9:g} GHz · Tx {float(s.terrain_power):g} dBm · assumed peak gain {float(s.terrain_peak_gain):g} dBi · Rx gain 0 dBi · Tx/Rx heights {float(s.terrain_tx_height):g}/{float(s.terrain_rx_height):g} m above ground"
        s.terrain_model_note = (
            "Terrain and rooftop diffraction included."
            if s.terrain_model == "diffraction"
            else "Obstruction loss disabled for comparison; terrain still sets receiver elevations."
        )
        s.terrain_steep_note = f"{100 * np.mean(self.result.large_angle[valid]):.1f}% of sampled paths exceed the approximate 12° diffraction-angle range; those estimates are less reliable."
        s.terrain_display_note = f"Local metric coordinates · vertical display exaggeration ×{scale:g} · mast markers not to scale · receivers inside 10 m excluded"
        s.terrain_environment_note = (
            f"{len(self.buildings)} synthetic buildings · gold marker: transmitter · pale boxes: buildings · ground colors: selected map quantity. Buildings and terrain affect coverage; roads are visual context. Building footprints are excluded from outdoor reception."
            if self.buildings else
            "Synthetic landscape; ground colors show estimated reception above local ground. Multiple ridges are reduced to one dominant obstacle per path."
        )
        labels = {
            "received": ("-120 dBm or less", "-40 dBm or more"),
            "diffraction": ("0 dB", "50 dB or more"),
            "los": ("Blocked", "Clear"),
            "elevation": (f"{t.elevation_m.min():.0f} m", f"{t.elevation_m.max():.0f} m"),
        }
        s.terrain_low, s.terrain_high = labels[s.terrain_quantity]
        s.terrain_key_class = "terrain-ramp-" + s.terrain_quantity
        if reset:
            self.reset_view(push=False)
        self.plotter.reset_camera_clipping_range()
        self.plotter.render()
        if self.view is not None:
            self.view.update()
            if reset:
                self.view.update_camera()

    def ui(self):
        from trame.widgets import html
        from trame_pyvista.widgets import PyVistaLocalView

        s = self.server.state
        with html.Div(classes="cut terrain-panel", id="coverage"):
            html.H2("City and landscape")
            html.Div(
                "{{ terrain_error }}", v_if="terrain_error", classes="terrain-error", role="alert"
            )
            if self.unavailable or self.result is None:
                return
            html.Div("{{ terrain_source }}", classes="note")
            with html.Div(classes="terrain-scene"):
                self.view = PyVistaLocalView(
                    self.plotter, namespace="terrain_coverage", style="width:100%;height:100%"
                )
            with html.Div(classes="terrain-camera-controls"):
                # Read the browser camera so zoom preserves local rotation and pan.
                # Pushing the Python camera here would restore its stale pose.
                for label, factor in (("+ Zoom in", 1.5), ("− Zoom out", 1 / 1.5)):
                    html.Button(
                        label,
                        click=(
                            f"() => {{ const view = trame.refs['{self.view.ref_name}']; "
                            "const camera = view.getCamera(); "
                            f"const factor = {factor}; "
                            "view.setCamera({ ...camera, "
                            "parallelScale: camera.parallelScale / factor, "
                            "position: camera.parallelProjection ? camera.position : "
                            "camera.position.map((v, i) => "
                            "camera.focalPoint[i] + (v - camera.focalPoint[i]) / factor) "
                            "}); }"
                        ),
                        type="button",
                    )
                html.Button("Reset view", click=self.reset_view, type="button")
            with html.Div(classes="color-key"):
                html.Span("{{ terrain_low }}")
                html.Div(classes=("terrain_key_class",))
                html.Span("{{ terrain_high }}")
            html.Div(
                "Drag to rotate · scroll or right-drag to zoom · Shift-drag to pan. "
                "Zoom buttons also work without a mouse. Gold marks the transmitter.",
                classes="note",
            )
            html.Div("{{ terrain_applied }}", classes="note")
            items = [
                (
                    "Environment",
                    "kind",
                    ENVIRONMENTS,
                ),
                ("Transmitter location", "position", [
                    ("west", "West side"), ("center", "Center"), ("east", "East side"),
                ]),
                (
                    "Coverage frequency",
                    "frequency",
                    [(str(i), f"{f / 1e9:g} GHz") for i, f in enumerate(self.data.frequency_hz)],
                ),
                (
                    "Tx height AGL",
                    "tx_height",
                    [(str(v), f"{v} m") for v in (10, 30, 60, 150, 300, 500)],
                ),
                ("Rx height AGL", "rx_height", [(str(v), f"{v} m") for v in (2, 10, 30)]),
                ("Transmit power", "power", [(str(v), f"{v} dBm") for v in (0, 10, 20, 30)]),
                (
                    "Assumed peak gain",
                    "peak_gain",
                    [(str(v), f"{v} dBi") for v in (0, 3, 6)],
                ),
                (
                    "Antenna heading",
                    "heading",
                    [(str(v), f"{v}° from +x") for v in (0, 45, 90, 180, 270)],
                ),
                (
                    "Antenna elevation",
                    "elevation",
                    [(str(v), f"{v}°") for v in (-5, 0, 5, 15, 90)],
                ),
                (
                    "Propagation",
                    "model",
                    [
                        ("diffraction", "Terrain / roof diffraction"),
                        ("free_space", "Ignore obstruction loss"),
                    ],
                ),
                (
                    "Map colors",
                    "quantity",
                    [
                        ("received", "Estimated received power"),
                        ("diffraction", "Added terrain loss"),
                        ("los", "Geometric sight lines"),
                        ("elevation", "Terrain elevation"),
                    ],
                ),
                (
                    "Inspect receiver",
                    "receiver",
                    [
                        ("far", "Far side"),
                        ("near", "Near side"),
                        ("north", "North flank"),
                        ("south", "South flank"),
                    ],
                ),
                (
                    "Display height scale",
                    "exaggeration",
                    [(str(v), f"×{v}") for v in (1, 2, 3)],
                ),
                (
                    "Coverage threshold",
                    "threshold",
                    [(str(v), f"{v} dBm") for v in (-70, -80, -90, -100)],
                ),
            ]
            primary = {"kind", "position", "tx_height", "quantity"}

            def control(label, key, options):
                if key == "kind" and self.custom_terrain is not None:
                    return
                with html.Label(label):
                    with html.Select(
                        v_model=("terrain_" + key, s["terrain_" + key]), aria_label=label
                    ):
                        for value, text in options:
                            html.Option(text, value=value)

            with html.Div(classes="controls"):
                for label, key, options in items:
                    if key in primary:
                        control(label, key, options)
            with html.Details(classes="terrain-settings"):
                html.Summary("More settings: power, pointing and display")
                with html.Div(classes="controls"):
                    for label, key, options in items:
                        if key not in primary:
                            control(label, key, options)
            html.Button("Calculate coverage", click=self.calculate, classes="calculate-coverage")
            html.Div("Change settings, then calculate to apply them.", classes="note")
            html.Div("{{ terrain_environment_note }}", classes="explanation")
            html.Div(
                "Illustrative coverage · one dominant terrain/roof edge per path. "
                "Reflections, street-corner propagation and indoor reception are not simulated.",
                classes="explanation",
            )
            with html.Details(classes="terrain-settings"):
                html.Summary("Inspect the path, coverage estimates and model limits")
                html.Div("{{ terrain_status }}", classes="summary")
                html.Div("{{ terrain_display_note }}", classes="note")
                html.Div("{{ terrain_model_note }} Clear sight line does not guarantee a clear Fresnel zone.", classes="note")
                html.Div("{{ terrain_steep_note }}", classes="note")
                html.Div("{{ terrain_path_note }}", classes="summary")
                html.Div(v_html=("terrain_profile_svg",), classes="terrain-profile")
                html.Div(
                    "Profile: ground (brown), ground and roofs (gray), effective-Earth obstruction profile (dotted), direct sight line (blue), dominant obstacle (orange). Heights in metres.",
                    classes="note",
                )
                html.Div(
                    "Single-edge approximation; no multiple-edge interactions, reflections, wall/rock penetration, foliage or fading. Equipment gains and thresholds are assumptions. No measurement validation.",
                    classes="explanation",
                )
