"""Lazy PyVista plotter component; imported only when its namespace is used."""

import pyvista as pv

from .mesh import radiation_mesh
from .numerics import frequency_index


@pv.register_plotter_component("radiation")
class RadiationComponent:
    """Add radiation patterns to an existing PyVista plotter and update them.

    Installed through the ``pyvista.plotter_components`` entry point. Each
    method returns ordinary PyVista actors or datasets. No browser, solver,
    custom plotter subclass, or background process is required.
    """

    def __init__(self, plotter):
        self._plotter = plotter
        self._patterns = {}

    def add_pattern(
        self,
        data,
        index=0,
        *,
        mode="pattern",
        normalization="per_frequency",
        floor_db=-40,
        quantity="field",
        radial_scale="linear",
        **plot_options,
    ):
        """Add a native actor in the current subplot; return ``pyvista.Actor``.

        Mesh options match :func:`pyvista_radiation.radiation_mesh`. Additional
        keywords go to ``Plotter.add_mesh`` (e.g. opacity, cmap, name, clim,
        show_scalar_bar). Use separate scalar-bar titles for independent bars.
        The original complex fields and caller's plotter configuration are
        preserved. Color limits remain fixed when changing frequencies.
        """
        options = dict(
            mode=mode,
            normalization=normalization,
            floor_db=floor_db,
            quantity=quantity,
            radial_scale=radial_scale,
        )
        mesh = radiation_mesh(data, index, **options)
        scalar = mesh.active_scalars_name
        defaults = dict(scalars=scalar, cmap="viridis", smooth_shading=True)
        if quantity == "field":
            defaults["clim"] = (floor_db, 0)
        actor = self._plotter.add_mesh(mesh, **{**defaults, **plot_options})
        self._patterns[id(actor)] = (
            actor,
            data,
            options,
            plot_options.get("smooth_shading", True),
            (mesh, actor.mapper.dataset),
        )
        return actor

    def set_frequency(self, actor, index):
        """Replace a managed actor's mesh, retaining its camera and appearance.

        The actor must have been added through this plotter's component and
        still belong to this plotter. Invalid input leaves the actor unchanged.
        Returns the new PyVista mesh; all original physical arrays stay intact.
        """
        try:
            stored, data, options, smooth, _previous_mesh = self._patterns[id(actor)]
        except KeyError as exc:
            raise ValueError("actor was not added by this plotter's radiation component") from exc
        if stored is not actor or not any(
            any(a is actor for a in renderer.actors.values())
            for renderer in self._plotter.renderers
        ):
            raise ValueError("radiation actor is no longer in this plotter")
        index = frequency_index(data, index)
        mesh = radiation_mesh(data, index, **options)
        if smooth:
            mesh.compute_normals(point_normals=True, cell_normals=False, inplace=True)
        actor.mapper.dataset = mesh
        # Retain the Python dataset as well as the VTK input: its teardown can
        # otherwise discard string field metadata from the mapped dataset.
        self._patterns[id(actor)] = (actor, data, options, smooth, (mesh, actor.mapper.dataset))
        self._plotter.render()
        return mesh

    def remove_pattern(self, actor):
        """Remove a managed actor and its retained data without resetting cameras."""
        if id(actor) not in self._patterns:
            raise ValueError("actor was not added by this plotter's radiation component")
        self._plotter.remove_actor(actor, reset_camera=False)
        del self._patterns[id(actor)]

    def __plotter_close__(self):
        self._patterns.clear()

    def __plotter_deep_clean__(self):
        self._patterns.clear()
