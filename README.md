<h1 align="center">
<img src="https://raw.githubusercontent.com/DeepLearnPhysics/spinal-tap/main/src/spinal_tap/assets/spinal-tap-logo-black.png" alt="Spinal Tap" width="400">
</h1><br>

[![CI](https://github.com/DeepLearnPhysics/spinal-tap/actions/workflows/ci.yml/badge.svg)](https://github.com/DeepLearnPhysics/spinal-tap/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/DeepLearnPhysics/spinal-tap/branch/main/graph/badge.svg)](https://codecov.io/gh/DeepLearnPhysics/spinal-tap)
[![Documentation Status](https://readthedocs.org/projects/spinal-tap/badge/?version=latest)](https://spinal-tap.readthedocs.io/en/latest/?badge=latest)
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

Launch the application and open
[http://localhost:8888](http://localhost:8888) in a browser:

```bash
spinal-tap
```

Check the installed version with:

```bash
spinal-tap --version
```

Spinal Tap provides fast WebGL and Plotly renderers, reconstruction/truth
comparison, object filtering and inspection, configurable appearance, and
portable exports. The complete user guide covers:

- [opening files, manifests, uploads, URLs, and shared views](https://spinal-tap.readthedocs.io/en/latest/sources.html),
- [display controls and object inspection](https://spinal-tap.readthedocs.io/en/latest/display.html),
- [appearance and camera controls](https://spinal-tap.readthedocs.io/en/latest/appearance.html), and
- [sharing and export formats](https://spinal-tap.readthedocs.io/en/latest/sharing.html).

See the [Spinal Tap documentation](https://spinal-tap.readthedocs.io/) for the
full installation, usage, deployment, and development guides.


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
