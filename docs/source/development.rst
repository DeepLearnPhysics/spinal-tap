Development
===========

Architecture
------------

Spinal Tap separates domain drawing from browser rendering:

#. SPINE reads and builds one event.
#. :mod:`spine.vis` produces a renderer-neutral scene containing points,
   lines, boxes, vectors, styles, hover metadata, bounds, and detector
   orientation.
#. Spinal Tap caches the reader, built event, and compact scene payload.
#. The WebGL client decodes the binary payload and applies frequent camera,
   visibility, hover, and appearance operations in the browser.
#. The Plotly path renders the same SPINE scene through its Plotly backend.

This boundary keeps detector and reconstruction semantics in SPINE while the
application owns sessions, controls, caching, transport, sharing, and
browser-specific interaction.

Repository layout
-----------------

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - Path
     - Responsibility
   * - ``src/spinal_tap/app.py``
     - Flask/Dash creation, authentication, routes, and command-line startup.
   * - ``src/spinal_tap/layout.py``
     - Application controls and page layout.
   * - ``src/spinal_tap/callbacks.py``
     - Server and clientside callback registration.
   * - ``src/spinal_tap/scene.py``
     - Compact scene serialization and process-local transport storage.
   * - ``src/spinal_tap/filtering.py``
     - Reconstruction/truth object filters and one-hop match behavior.
   * - ``src/spinal_tap/inspection.py``
     - Object-inspector metadata and semantic grouping.
   * - ``src/spinal_tap/cache.py``
     - Bounded, session-aware upload and URL cache.
   * - ``src/spinal_tap/assets/``
     - WebGL renderer and browser interaction modules.
   * - ``test/``
     - Unit and callback tests enforcing complete Python statement coverage.

Quality gates
-------------

Install the development dependencies and hooks:

.. code-block:: bash

   python -m pip install -e ".[dev]"
   pre-commit install

Run the same checks used by CI:

.. code-block:: bash

   pre-commit run --all-files
   bash check_coverage.sh

Build the documentation with warnings treated as errors:

.. code-block:: bash

   python -m pip install -r docs/requirements.txt
   make -C docs html SPHINXOPTS="-W --keep-going"

Documentation policy
--------------------

Write task-oriented documentation for stable user workflows. Avoid documenting
every Dash callback as public API: callbacks are application plumbing and may
change without constituting a user-facing compatibility break.

Prefer control names, tables, and small state-flow diagrams to full-page
screenshots. When a screenshot is essential, crop it to the relationship being
explained, optimize it, and include the represented Spinal Tap release in the
caption.
