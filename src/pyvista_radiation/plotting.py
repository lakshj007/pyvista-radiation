"""Reusable PyVista plotting with frequency updates that retain camera state."""

from .mesh import radiation_mesh
from .numerics import frequency_index


class RadiationViewer:
    """One or more linked PyVista panels for one saved dataset.

    Updating a frequency replaces the mapper's mesh; actors, camera position,
    lights and scalar limits stay intact. Use ``show()`` for a native window or
    attach ``plotter`` to a trame view for browser interaction.
    """

    def __init__(
        self,
        data,
        indices=(0,),
        *,
        mode="pattern",
        normalization="per_frequency",
        radial_scale="linear",
        floor_db=-40,
        off_screen=False,
    ):
        import pyvista as pv

        self.data = data
        self.indices = [frequency_index(data, i) for i in indices]
        if not self.indices:
            raise ValueError("at least one frequency is required")
        self.options = dict(
            mode=mode, normalization=normalization, radial_scale=radial_scale, floor_db=floor_db
        )
        # Validate meshes before allocating a window.
        meshes = [radiation_mesh(data, i, **self.options) for i in self.indices]
        self.plotter = pv.Plotter(
            shape=(1, len(self.indices)),
            off_screen=off_screen,
            window_size=(650 * len(self.indices), 650),
        )
        self.meshes = meshes
        self.actors = []
        self.labels = []
        self.notes = []
        for panel, mesh in enumerate(meshes):
            self.plotter.subplot(0, panel)
            self.plotter.set_background("#132d40")
            self.actors.append(
                self.plotter.add_mesh(
                    mesh,
                    scalars="Relative field (dB)",
                    cmap="viridis",
                    clim=(floor_db, 0),
                    smooth_shading=True,
                    scalar_bar_args=dict(
                        title=f"Panel {panel + 1}: relative field (dB)",
                        color="white",
                        vertical=False,
                        position_x=0.16,
                        position_y=0.08,
                        width=0.72,
                        title_font_size=12,
                        label_font_size=10,
                    ),
                )
            )
            self.labels.append(
                self.plotter.add_text(
                    self._label(panel), position=(12, 610), font_size=14, color="white"
                )
            )
            self.notes.append(
                self.plotter.add_text(
                    self._description(), position=(12, 12), font_size=9, color="white"
                )
            )
            self.plotter.add_axes(color="white")
        self.plotter.link_views()
        self.reset_camera()

    def _label(self, panel):
        return f"{self.data.frequency_hz[self.indices[panel]] / 1e9:g} GHz"

    def _description(self):
        reference = (
            "peak at each frequency"
            if self.options["normalization"] == "per_frequency"
            else "shared peak over dataset"
        )
        radius = (
            "unit sphere"
            if self.options["mode"] == "sphere"
            else "relative field amplitude"
            if self.options["radial_scale"] == "linear"
            else "(relative dB - floor) / (-floor)"
        )
        return f"Radius: {radius} (display only)\nReference: {reference}"

    def set_frequency(self, panel, index):
        """Select an integer frequency index without resetting scene settings."""
        if not isinstance(panel, int) or not 0 <= panel < len(self.indices):
            raise ValueError("panel index is out of range")
        index = frequency_index(self.data, index)
        mesh = radiation_mesh(self.data, index, **self.options)
        self.indices[panel] = index
        mesh.compute_normals(point_normals=True, cell_normals=False, inplace=True)
        self.meshes[panel] = mesh
        self.actors[panel].mapper.dataset = mesh
        self.labels[panel].SetInput(self._label(panel))
        self.plotter.render()

    def configure(self, **options):
        """Update display settings in all panels, retaining the camera."""
        if options.keys() - self.options.keys():
            raise ValueError("unsupported display setting")
        candidate = {**self.options, **options}
        meshes = [radiation_mesh(self.data, i, **candidate) for i in self.indices]
        self.options = candidate
        self.meshes = meshes
        for actor, mesh in zip(self.actors, meshes):
            mesh.compute_normals(point_normals=True, cell_normals=False, inplace=True)
            actor.mapper.dataset = mesh
            actor.mapper.scalar_range = (candidate["floor_db"], 0)
        for note in self.notes:
            note.SetInput(self._description())
        self.plotter.render()

    def camera_preset(self, name):
        """View from +z (front), -z (back), +x (side), or an isometric angle."""
        poses = {
            "front": [(0, 0, 5), (0, 0, 0), (0, 1, 0)],
            "back": [(0, 0, -5), (0, 0, 0), (0, 1, 0)],
            "side": [(5, 0, 0), (0, 0, 0), (0, 0, 1)],
            "isometric": [(2.7, -3.8, 2.3), (0, 0, 0), (0, 0, 1)],
        }
        if name not in poses:
            raise ValueError("camera preset must be front, back, side or isometric")
        self.plotter.camera_position = poses[name]
        self.plotter.reset_camera_clipping_range()
        self.plotter.render()

    def reset_camera(self):
        """Restore a fixed scale so normalization changes remain comparable."""
        self.plotter.camera_position = [(2.7, -3.8, 2.3), (0, 0, 0), (0, 0, 1)]
        self.plotter.camera.parallel_projection = True
        self.plotter.camera.parallel_scale = 1.35
        self.plotter.reset_camera_clipping_range()
        self.plotter.render()

    def show(self, *, sliders=True):
        """Open the native PyVista window with one frequency slider per panel."""
        if sliders and len(self.data.frequency_hz) > 1:
            for panel, index in enumerate(self.indices):
                self.plotter.subplot(0, panel)
                self.plotter.add_slider_widget(
                    lambda value, p=panel: self.set_frequency(p, round(value)),
                    [0, len(self.data.frequency_hz) - 1],
                    value=index,
                    title="Frequency index",
                    pointa=(0.2, 0.18),
                    pointb=(0.8, 0.18),
                    interaction_event="always",
                    color="white",
                    fmt="%.0f",
                )
        self.plotter.show()

    def close(self):
        self.plotter.close()


def plot_pattern(data, index=0, **options):
    """Return a single-panel RadiationViewer; call .show() to display it."""
    return RadiationViewer(data, (index,), **options)


def compare_patterns(data, indices=(0, 1), **options):
    """Return linked panels with shared color limits and normalization policy."""
    return RadiationViewer(data, indices, **options)
