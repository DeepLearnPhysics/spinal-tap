# Spinal Tap documentation

The documentation is built with Sphinx and the Read the Docs theme.

```bash
python -m pip install -r docs/requirements.txt
make -C docs html SPHINXOPTS="-W --keep-going"
```

Open `docs/build/html/index.html` after the build completes. Read the Docs uses
the repository-level `.readthedocs.yaml` file and treats warnings as errors.

The guides deliberately avoid full-page application screenshots. Control names,
workflows, and compact tables are more stable across releases. Add a screenshot
only when it explains a spatial relationship that prose cannot, crop it to the
relevant control, and state the release it represents in its caption.
