# Spinal Tap

[![CI](https://github.com/DeepLearnPhysics/spinal-tap/actions/workflows/ci.yml/badge.svg)](https://github.com/DeepLearnPhysics/spinal-tap/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/DeepLearnPhysics/spinal-tap/branch/main/graph/badge.svg)](https://codecov.io/gh/DeepLearnPhysics/spinal-tap)
[![PyPI version](https://badge.fury.io/py/spinal-tap.svg)](https://badge.fury.io/py/spinal-tap)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/downloads/)

Spinal Tap is a Dash application that provides simple visualization tools for
the Scalable Particle Imaging With Neural Embeddings
([SPINE](https://github.com/DeepLearnPhysics/spine)) package.


## Installation

You can install Spinal Tap and all dependencies (including Dash, Flask, Plotly, and spine) using pip:

```bash
pip install .
```

Or, for editable development mode:

```bash
pip install -e .
```

## Usage

After installation, launch the app using the provided CLI:

```bash
spinal-tap
```

You can also check the installed version with:

```bash
spinal-tap --version
# or
spinal-tap -v
```

Then open your browser to [http://0.0.0.0:8888/](http://0.0.0.0:8888/).

The default renderer is Spinal Tap's compact WebGL viewer. It downloads a
binary renderer-neutral SPINE scene, keeps one shared camera across split
reconstruction/truth viewports, and applies ordinary object visibility, color,
and theme changes without rebuilding the event on the server. Drag to orbit,
shift-drag or right-drag to pan, scroll to zoom, double-click to reset, and
click a displayed object for its label. The viewer also provides reset and PNG
buttons. Use the renderer switch in the header when Plotly's full modebar or
compatibility behavior is preferred.

Display, object, color, and geometry selections refresh the loaded event
automatically. Multi-select scene controls apply once their menu is closed, so
several hover attributes or overlays can be chosen without repeated rebuilds.
Opening a source and navigating within it are separate actions: use **Open
source** after changing the input, then use **Go** or the arrow buttons to move
between entries.

The viewer toolbar provides independent reconstruction and truth object filters.
Its chain button optionally links direct SPINE matches: changing an object on
one side applies the same visibility change to its immediate matches on the
other side, without recursively following further matches.

The Data panel accepts four kinds of source:

- **Path** opens an HDF5 path or glob already visible to the server.
- **Browse** opens the standard operating-system file picker when running
  locally. Because web browsers do not expose absolute client paths, the
  selected file is copied into Spinal Tap's temporary local cache. Use Path to
  open a known host path without copying it.
- **Upload** transfers a workstation file to a private temporary cache in the
  hosted deployment. Browse and Upload are sent as retryable 32 MiB requests,
  so the 64
  MiB ingress request limit does not limit the total file size. The configured
  S3DF deployment accepts files up to 2 GiB and keeps at most 20 GiB for 24
  hours, extending the lifetime while a source remains active.
- **URL** downloads a public HTTP(S) source into the same bounded cache.

Exact files are identified by content, not extension: Spinal Tap checks for an
HDF5 signature, then JSON, then a UTF-8 file manifest. Consequently `files.txt`,
`files.list`, or an extensionless manifest all work. Blank lines and lines
starting with `#` are ignored; relative records are resolved beside the
manifest. Globs remain supported in paths and manifest records.

An exported view JSON can be opened through any applicable source mode. The
renderer-independent action tray provides Reset view, Save PNG and Share for
both WebGL and Plotly. Use Share after loading an event to copy a self-contained
view link; its adjacent menu exports the same state as JSON. The restored state
includes the file and entry, display options, attributes, geometry, object
filters, renderer and camera while leaving the recipient free to continue
exploring. Link state lives in the URL fragment and is therefore not included
in normal server requests or access logs; the referenced file must still be
accessible to the recipient's Spinal Tap deployment. Temporary uploaded
sources cannot be shared or exported because their private cache paths are not
portable to another browser session.

Keyboard shortcuts are available whenever focus is outside an input or menu:
Left/Right loads the previous/next entry, `R` resets the view, `A` toggles the
axes, `S` saves a PNG, `E` exports the view as JSON, and `?` opens the shortcut
reference in the application header.


## Deployment

### Kubernetes

Spinal Tap is deployed on SLAC's S3DF Kubernetes infrastructure and is accessible at:

**[https://spinal-tap.slac.stanford.edu](https://spinal-tap.slac.stanford.edu)**

S3DF input paths may use either the host form `/sdf/data/neutrino/...` or the
container form `/data/...`; Spinal Tap resolves both forms automatically.

Readers and built events are cached per application process. The bounds can be
configured with `SPINAL_TAP_READER_CACHE_SIZE` (default 8) and
`SPINAL_TAP_EVENT_CACHE_SIZE` (default 2); set either to 0 to disable that
cache. Compact binary scenes are held in an eight-entry process-local LRU while
the browser fetches them; configure this bound with
`SPINAL_TAP_SCENE_CACHE_SIZE` (minimum 1).

The Kubernetes configuration files are located in the `k8s/` directory. For deployment instructions and SLAC-specific configuration details, see:
- [`k8s/README.md`](k8s/README.md) - Deployment guide
- [`k8s/SLAC_CONFIG.md`](k8s/SLAC_CONFIG.md) - Detailed SLAC S3DF configuration

### Docker

Docker images are automatically built and published to GitHub Container Registry when version tags are pushed:

```bash
docker pull ghcr.io/deeplearnphysics/spinal-tap:latest
```

To run locally with Docker:

```bash
docker run -p 8888:8888 ghcr.io/deeplearnphysics/spinal-tap:latest
```

## Development & CI/CD

- Code style is enforced with black, isort, and flake8 (pre-commit and CI).
- The GitHub Actions workflow builds and tests on every commit, PR, tag, and release.
- The complete test suite enforces 100% statement coverage and publishes its
  report to [Codecov](https://codecov.io/gh/DeepLearnPhysics/spinal-tap).
- Docker images are built automatically on version tag pushes (e.g., `v0.1.2`).
- Publishing:
  - On tag push: publishes to Test PyPI (requires `TEST_PYPI_API_TOKEN` secret).
  - On GitHub Release: publishes to PyPI (requires `PYPI_API_TOKEN` secret).
