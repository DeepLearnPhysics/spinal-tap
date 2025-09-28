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


## Development & CI/CD

- Code style is enforced with black, isort, and flake8 (pre-commit and CI).
- The GitHub Actions workflow builds and tests on every commit, PR, tag, and release.
- Publishing:
  - On tag push: publishes to Test PyPI (requires `TEST_PYPI_API_TOKEN` secret).
  - On GitHub Release: publishes to PyPI (requires `PYPI_API_TOKEN` secret).


## Roadmap

In the near future, the application will be hosted at
[https://k8s.slac.stanford.edu/spinal-tap](https://k8s.slac.stanford.edu/spinal-tap)
