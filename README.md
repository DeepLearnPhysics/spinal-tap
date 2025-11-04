# Spinal Tap

Spinal Tap is a Dash application that provides simple visualization tools for
the Scalable Particle Imaging With Neural Embeddings
([SPINE](https://github.com/DeepLearnPhysics/spine)) package.


## Installation

You can install Spinal Tap and all dependencies (including Dash, Flask, Plotly, and spine-ml) using pip:

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


## Deployment

### Kubernetes

Spinal Tap is deployed on SLAC's S3DF Kubernetes infrastructure and is accessible at:

**[https://spinal-tap.slac.stanford.edu](https://spinal-tap.slac.stanford.edu)**

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
- Docker images are built automatically on version tag pushes (e.g., `v0.1.2`).
- Publishing:
  - On tag push: publishes to Test PyPI (requires `TEST_PYPI_API_TOKEN` secret).
  - On GitHub Release: publishes to PyPI (requires `PYPI_API_TOKEN` secret).
