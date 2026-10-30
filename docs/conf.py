"""Sphinx configuration; builds without an openEMS installation."""
project='pyvista-radiation'
author='Laksh Jain'
release='0.2.0'
extensions=['sphinx.ext.autodoc','sphinx.ext.napoleon','sphinx.ext.viewcode',
            'sphinx_gallery.gen_gallery']
html_theme='alabaster'
exclude_patterns=['_build']
autodoc_member_order='bysource'

# Execute only the focused, solver-free example, using PyVista's native scraper.
import pyvista as pv
from pyvista.plotting.utilities.sphinx_gallery import Scraper

pv.OFF_SCREEN = True
pv.BUILDING_GALLERY = True
sphinx_gallery_conf = {
    "examples_dirs": "../examples/house_showcase",
    "gallery_dirs": "auto_examples",
    "filename_pattern": r"plot_house_pulse\.py$",
    "ignore_pattern": r"render_preview\.py$",
    "image_scrapers": (Scraper(),),
    "download_all_examples": False,
    "abort_on_example_error": True,
    "copyfile_regex": r".*\.(vtm|vts|vtu|vtp|json)$|LICENSE$",
    "within_subsection_order": "FileNameSortKey",
}
