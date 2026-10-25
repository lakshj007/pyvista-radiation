Getting started
===============

Install from a checkout::

   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e '.[preview,test]'

Launch the interactive comparison::

   pyvista-radiation

Open http://127.0.0.1:8766. Stop the local server with Ctrl+C.
A saved NPZ file can be supplied as the first argument. The browser app currently
requires full-sphere sampling containing the four principal azimuths 0°, 90°,
180° and 270°. Use the general mesh API for other uniform azimuth grids.

For a native PyVista window::

   pyvista-radiation --native

The native frequency sliders use integer indices into the saved frequency axis;
the panel titles show the corresponding GHz value.

Core data loading needs only NumPy. PyVista and browser packages are optional
until a mesh or viewer is created. Most users can install the wheel with
``pip install 'pyvista-radiation[preview]'`` once a release is published.
This checkout has not been published to PyPI.

The sample is installed inside the package, so it works outside this checkout::

   from pyvista_radiation import load_patch
   data = load_patch()
   print(data.frequency_hz)

Raw solver outputs, simulation reproduction and source attribution live in the
repository's ``data/`` and ``simulations/`` directories. Core code is MIT;
the adapted simulation script is GPL-3.0-or-later; generated data is CC0-1.0.
