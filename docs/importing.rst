Importing your radiation data
=================================

The extension accepts saved simulation data through NumPy arrays, a simple CSV
exchange format, or the versioned NPZ contract. The bundled openEMS NPZ remains
the reference example. These adapters do not parse arbitrary HFSS, CST or other
vendor exports, run solvers, infer missing phase or convert antenna gain to fields.
Map solver output to the declared convention explicitly before importing it.

From complex arrays
-----------------------

.. code-block:: python

   import numpy as np
   from pyvista_radiation import from_arrays, radiation_mesh, save

   theta = np.linspace(0, 180, 91)
   phi = np.arange(0, 360, 5)
   e_theta = np.broadcast_to(
       np.sin(np.deg2rad(theta))[:, None], (91, 72)
   ).astype(complex)
   data = from_arrays(
       2.4e9, theta, phi, e_theta, reference_radius_m=1,
       source='Analytic short dipole', angle_unit='deg',
       kind='analytic', solver_version='not applicable',
   )
   mesh = radiation_mesh(data)
   save('dipole.npz', data)

Frequency is in Hz. Angles are theta from +z and phi from +x toward +y, in the
explicitly selected ``angle_unit`` ('rad' by default, or 'deg'). Fields are
unnormalized complex V/m at the supplied reference radius. They are ordered
``(frequency, theta, phi)``; a 2D field and scalar frequency are accepted for a
single frequency. Omitting ``e_phi`` declares it to be zero. Real-only arrays
are rejected; the analytic example deliberately casts its known zero-phase
field to complex. Arbitrarily normalized amplitudes, dB values and gain data
must not be passed as V/m. Full-sphere mesh conversion requires both theta poles
and uniform periodic phi sampling. The data model can retain partial grids,
but the full-sphere mesh/integration operations will reject them.

The helper builds schema metadata and retains source, input angle units, kind
and solver version. ``kind`` is 'simulation' or 'analytic'. Optional original
``radiated_power_w`` and ``directivity_max`` arrays are accepted without inference.
An endpoint at phi=360 degrees (2pi radians) is removed only if the first phi
is zero and both complex components agree at the duplicate endpoint. Conflicting
phase is an error even if magnitudes match. Axes are never silently transposed.

From a CSV export
---------------------

Use one row per frequency/theta/phi combination. With degree input, the required
column names are::

   frequency_hz,theta_deg,phi_deg,e_theta_real_v_m,e_theta_imag_v_m,e_phi_real_v_m,e_phi_imag_v_m

The field columns are the real and imaginary parts of the two complex transverse
electric components in V/m. For radians, use ``theta_rad,phi_rad`` and pass
``angle_unit='rad'``. Column order and row order may vary. Each frequency must
have exactly the same complete rectangular angular grid. Missing/duplicate
samples, nonfinite values, duplicate headers and extra columns are rejected.

.. code-block:: python

   from pyvista_radiation import load_csv, save

   data = load_csv(
       'fields.csv', reference_radius_m=1,
       source='Solver export, run identifier 123', solver_version='record your build',
   )
   save('fields.npz', data)

CSV carries no calibration or reference-radius metadata, so the radius must be
provided. Source defaults to the input path; provide a meaningful source identifier
and solver version for reproducibility. The loader sorts the three axes, rebuilds
the grid and preserves both components' complex phase. It does not reinterpret
latitude/elevation, azimuth handedness, phasor signs or field normalization.

NPZ and mesh exports
------------------------

``load`` / ``save`` are the lossless physical-data path and use only NumPy.
See the :download:`NPZ contract <data-contract.md>` for schema and units.
``mesh.save('radiation.vtp')`` exports the native PyVista visualization mesh;
its normalized display coordinates do not replace the original complex fields.
