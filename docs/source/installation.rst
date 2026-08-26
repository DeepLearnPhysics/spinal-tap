Installation
============

Python installation
-------------------

Spinal Tap requires Python 3.10 or newer. Install the released package with
its SPINE visualization dependency:

.. code-block:: bash

   python -m pip install spinal-tap

Launch the application on its default address:

.. code-block:: bash

   spinal-tap

The command prints the startup URL. By default, the server listens on all
interfaces at port 8888. Override either value when needed:

.. code-block:: bash

   spinal-tap --host 127.0.0.1 --port 8890

Use ``--debug`` only while developing the application. It enables the Dash
debugger and development reloader. Check the installed version with
``spinal-tap --version``.

Development installation
------------------------

Clone the repository and install it in editable mode:

.. code-block:: bash

   git clone https://github.com/DeepLearnPhysics/spinal-tap.git
   cd spinal-tap
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -e ".[dev]"
   pre-commit install

Run the test and coverage gate with:

.. code-block:: bash

   bash check_coverage.sh

The project enforces 100% Python statement coverage. See :doc:`development`
for the architecture and complete contributor checks.

Container installation
----------------------

Released images are published to the GitHub Container Registry:

.. code-block:: bash

   docker pull ghcr.io/deeplearnphysics/spinal-tap:latest
   docker run --rm -p 8888:8888 \
     ghcr.io/deeplearnphysics/spinal-tap:latest

Mount data into the container when using **Path** sources:

.. code-block:: bash

   docker run --rm -p 8888:8888 \
     -v /host/data:/data:ro \
     ghcr.io/deeplearnphysics/spinal-tap:latest

The browser can also transfer a local file through **Browse** or **Upload**,
subject to the configured temporary-cache limits. See :doc:`deployment` before
exposing the application to multiple users.
