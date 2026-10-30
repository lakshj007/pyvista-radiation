"""Small packaged examples that do not require openEMS or a repository checkout."""

from importlib.resources import as_file, files

from .model import load


def load_patch():
    """Load the bundled openEMS 32 × 40 mm patch at 2.2, 2.4 and 2.6 GHz."""
    with as_file(files("pyvista_radiation").joinpath("data/patch_reference.npz")) as path:
        return load(path)
