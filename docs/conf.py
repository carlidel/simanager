# conf.py

import os
import sys

import sphinx_rtd_theme

# Add your package directory to sys.path
this_file_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(this_file_path, "../.."))

# -- Project information -----------------------------------------------------
project = "simanager"
author = "Carlo Emilio MONTANARI"

# The full version, including alpha/beta/rc tags
release = "0.0.4"

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",  # Enable autodoc extension for docstring extraction
    "sphinx.ext.napoleon",  # Enable napoleon extension for parsing Google-style docstrings
    "sphinx_mdinclude",  # Enable recommonmark extension for parsing markdown files
]

# The master toctree document.
master_doc = "index"

# -- Options for HTML output -------------------------------------------------
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

# Specify the path to your README.md file relative to the 'docs' directory.
index_filename = "README.md"
