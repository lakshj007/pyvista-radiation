# Two-floor openEMS recordings

Actual 3D openEMS outputs for the compact 500 MHz two-floor example. See
[the example documentation](../../docs/house.rst) for scope and reproduction.
Numerical outputs are CC0-1.0; solver scripts are MIT under the repository license.

`raw/*.h5.gz` are lossless gzip archives of the original HDF5 files, not rewritten
HDF5 datasets. `metadata.json` records hashes of both compressed and original
bytes, exact recipe, source normalization, run evidence and generator hashes.
The pulse stores real time-domain Ey; steady slices store complex vector fields.
The packaged NumPy archive is `src/pyvista_radiation/data/two_floor_house.npz`.
No house-specific mesh convergence or measurement validation is claimed.
