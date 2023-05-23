# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# http://www.sphinx-doc.org/en/master/config

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import subprocess
import sys
sys.path.insert(0, os.path.abspath('.'))


# -- Project information -----------------------------------------------------

project = 'QuickCW'
copyright = '2023, Bence Becsy, Neil Cornish, Matthew Digman'
author = 'Bence Becsy, Neil Cornish, Matthew Digman'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = ["sphinx.ext.autodoc", "sphinx.ext.viewcode"]

# get doctrings for __init__ method
autoclass_content = "both"

# make order or docs 'groupwise'
autodoc_member_order = "groupwise"

# we won't even try installing these
autodoc_mock_imports = ["enterprise"]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
#html_theme = 'alabaster'
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# allows readthedocs to auto-generate docs
def run_apidoc(_):
    output_path = os.path.abspath(os.path.dirname(__file__))
    # make docs from notebooks
    # nb = '_static/notebooks/*.ipynb'
    # subprocess.check_call(['jupyter nbconvert --template nb-rst.tpl --to rst',
    #                           nb, '--output-dir', output_path])

    modules = ["../QuickCW",]
    for module in modules:
        cmd_path = "sphinx-apidoc"
        if hasattr(sys, "real_prefix"):  # Check to see if we are in a virtualenv
            # If we are, assemble the path manually
            cmd_path = os.path.abspath(os.path.join(sys.prefix, "bin", "sphinx-apidoc"))
        subprocess.check_call([cmd_path, "-o", output_path, "-f", "-M", module])


def setup(app):
    app.connect("builder-inited", run_apidoc)


