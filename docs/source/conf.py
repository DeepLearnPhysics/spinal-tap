"""Sphinx configuration for the Spinal Tap documentation."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

project = "Spinal Tap"
copyright = "2026, DeepLearningPhysics Collaboration"
author = "DeepLearningPhysics Collaboration"

try:
    from spinal_tap.version import __version__

    release = __version__
    version = __version__
except ImportError:
    release = "development"
    version = "development"

extensions = [
    "sphinx.ext.autosectionlabel",
    "sphinx_copybutton",
    "sphinx_rtd_theme",
]

autosectionlabel_prefix_document = True
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
templates_path = ["_templates"]

html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "collapse_navigation": False,
    "sticky_navigation": True,
    "navigation_depth": 3,
    "includehidden": True,
    "titles_only": False,
    "logo_only": True,
}
html_logo = "_static/img/spinal-tap-logo-white.png"
html_favicon = "_static/img/favicon.ico"
html_static_path = ["_static"]
html_css_files = ["css/custom.css"]

epub_exclude_files = [
    "_static/favicon.ico",
    "_static/img/favicon.ico",
]

master_doc = "index"
