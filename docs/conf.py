"""Sphinx configuration; builds without an openEMS installation."""
project='pyvista-radiation'
author='Laksh Jain'
release='0.2.0'
extensions=['sphinx.ext.autodoc','sphinx.ext.napoleon','sphinx.ext.viewcode']
html_theme='alabaster'
exclude_patterns=['_build']
autodoc_member_order='bysource'
