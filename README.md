# Spinal Tap

Spinal Tap is Dash application which provides simple visualization tools for
the Scalable Particle Imaging With Neural Embeddings
([SPINE](https://github.com/DeepLearnPhysics/spine) package).

## Installation

We recommend using a Singularity or Docker containers pulled from
[`deeplearnphysics/larcv2`](https://hub.docker.com/r/deeplearnphysics/larcv2),
which contains all the necessary dependancy to run this package.

This package does not need to be installed. Simply pull this repository and make
sure to use the `--recurse-submodules` option to pull the SPINE submodule
automatically, i.e.

```python
git clone --recurse-submodules https://github.com/DeepLearnPhysics/spinal_tap
```

## Usage

In order to use this package locally, simply execute the `app.py` script:

```bash
python3 app.py
```

And open the app in a browser by opening `http://0.0.0.0:8888/`. Done!


In the near future, the application with be hosted at
[https://k8s.slac.stanford.edu/spinal-tap](https://k8s.slac.stanford.edu/spinal-tap)
