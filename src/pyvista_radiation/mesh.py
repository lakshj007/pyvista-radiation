"""Convert a sampled full-sphere far field to a welded PyVista triangle mesh."""

import numpy as np

from .numerics import (
    amplitude_db,
    directivity,
    power_db,
    reference_amplitude,
    require_full_sphere,
    spherical_directions,
)
from .numerics import frequency_index as validate_index


def radiation_mesh(
    data,
    frequency_index=0,
    *,
    mode="pattern",
    normalization="per_frequency",
    floor_db=-40,
    quantity="field",
    radial_scale="linear",
):
    """Create a closed spherical topology with unique seam and pole vertices.

    Parameters
    ----------
    data : RadiationData
        Complex transverse far fields on a full sphere.
    frequency_index : int
        Index into the frequency axis.
    mode : {'pattern', 'sphere'}
        Variable display radius or a unit sphere colored by strength.
    normalization : {'per_frequency', 'global'}
        Field reference: peak at this frequency or peak over the entire dataset.
    floor_db : float
        Negative display floor; physical arrays are preserved.
    quantity : {'field', 'directivity'}
        Relative field dB or integrated angular directivity dBi.
    radial_scale : {'linear', 'db'}
        Linear field radius, or (dB-floor)/(-floor) to reveal weaker lobes.
        Directivity uses sqrt(D/Dmax) for linear radius. Radius is always a
        display quantity, never a length or a physical antenna surface.
    """
    import pyvista as pv

    require_full_sphere(data)
    index = validate_index(data, frequency_index)
    if mode not in ("pattern", "sphere"):
        raise ValueError("mode must be pattern or sphere")
    if radial_scale not in ("linear", "db"):
        raise ValueError("radial_scale must be linear or db")
    ref = reference_amplitude(data, index, normalization)
    amplitude = data.field_magnitude[index]
    relative = amplitude / ref
    relative_db = amplitude_db(amplitude, ref, floor_db)
    if quantity == "field":
        colors, scalar_name = relative_db, "Relative field (dB)"
    elif quantity == "directivity":
        d = directivity(data, index)
        colors, scalar_name = power_db(d, 1, floor_db), "Directivity (dBi)"
        relative = np.sqrt(d / d.max())
        relative_db = amplitude_db(relative, 1, floor_db)
    else:
        raise ValueError("quantity must be field or directivity")
    radius = relative if radial_scale == "linear" else (relative_db - floor_db) / (-floor_db)
    if mode == "sphere":
        radius = np.ones_like(radius)
    # A pole has one physical magnitude even though its component basis rotates.
    for values in (amplitude,):
        for row in (values[0], values[-1]):
            if not np.allclose(
                row, row.mean(), rtol=1e-5, atol=max(amplitude.max() * 1e-7, 1e-300)
            ):
                raise ValueError("field magnitude at each pole must be independent of phi")
    directions = spherical_directions(data.theta_rad, data.phi_rad)

    def collapse(a):
        return np.r_[a[0].mean(), a[1:-1].ravel(), a[-1].mean()]

    unit = np.concatenate([[[0, 0, 1]], directions[1:-1].reshape(-1, 3), [[0, 0, -1]]])
    points = unit * collapse(radius)[:, None]
    rings, nphi = len(data.theta_rad) - 2, len(data.phi_rad)
    south = len(points) - 1
    faces = []
    for j in range(nphi):
        nxt = (j + 1) % nphi
        faces.append([3, 0, 1 + j, 1 + nxt])
        for i in range(rings - 1):
            a, b = 1 + i * nphi + j, 1 + i * nphi + nxt
            faces.extend([[3, a, a + nphi, b], [3, b, a + nphi, b + nphi]])
        a, b = 1 + (rings - 1) * nphi + j, 1 + (rings - 1) * nphi + nxt
        faces.append([3, a, south, b])
    mesh = pv.PolyData(points, np.array(faces).ravel())
    mesh.point_data[scalar_name] = collapse(colors)
    mesh.point_data["Field magnitude (V/m)"] = collapse(amplitude)
    mesh.point_data["Display radius"] = collapse(radius)
    mesh.point_data["Direction"] = unit
    mesh.field_data["Frequency (Hz)"] = [data.frequency_hz[index]]
    mesh.field_data["Normalization"] = [normalization]
    mesh.field_data["Reference amplitude (V/m)"] = [ref]
    mesh.field_data["Radius meaning"] = ["display quantity; not a physical length"]
    return mesh


def difference_mesh(data, left, right, *, normalization="per_frequency", floor_db=-40):
    """Unit sphere colored by signed B-minus-A field dB; no geometric distortion."""
    from .metrics import pattern_difference

    mesh = radiation_mesh(data, left, mode="sphere", normalization=normalization, floor_db=floor_db)
    radiation_mesh(data, right, mode="sphere", normalization=normalization, floor_db=floor_db)
    difference = pattern_difference(
        data, left, right, normalization=normalization, floor_db=floor_db
    )
    mesh["B - A (dB)"] = np.r_[
        difference[0].mean(), difference[1:-1].ravel(), difference[-1].mean()
    ]
    mesh.set_active_scalars("B - A (dB)")
    mesh.field_data["Compared frequencies (Hz)"] = data.frequency_hz[[left, right]]
    mesh.field_data["Compared reference amplitudes (V/m)"] = [
        reference_amplitude(data, left, normalization),
        reference_amplitude(data, right, normalization),
    ]
    mesh.field_data["Difference floor (dB)"] = [floor_db]
    mesh.compute_normals(point_normals=True, cell_normals=False, inplace=True)
    return mesh
