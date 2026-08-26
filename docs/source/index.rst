Spinal Tap Documentation
========================

.. rst-class:: lead

Spinal Tap is the interactive event display for files produced by
`SPINE <https://github.com/DeepLearnPhysics/spine>`_. It combines a fast,
dedicated WebGL viewer with a Plotly compatibility renderer and keeps source
selection, event navigation, filtering, appearance, inspection, and export in
one browser application.

The application is intended for three common workflows:

* inspect a SPINE HDF5 file on the same machine as the server;
* share a reproducible event view with another collaborator; and
* deploy a controlled, authenticated display beside experiment data.

.. note::

   This guide favors stable control names and workflows over full-page
   screenshots. The application changes faster than static screenshots, and a
   live event is the best way to learn its camera and hover interactions.

.. toctree::
   :maxdepth: 2
   :caption: User guide
   :hidden:

   installation
   sources
   display
   appearance
   sharing
   troubleshooting

.. toctree::
   :maxdepth: 2
   :caption: Operations and development
   :hidden:

   deployment
   development

Quick start
-----------

Install and launch Spinal Tap:

.. code-block:: bash

   python -m pip install spinal-tap
   spinal-tap

Open ``http://localhost:8888``, enter an HDF5 path in **Path**, select **Open**,
and navigate with **Go** or the left/right arrows. See :doc:`sources` for
manifests, uploads, URLs, and shared view JSON files.

Choosing a renderer
-------------------

.. list-table::
   :header-rows: 1
   :widths: 18 41 41

   * - Renderer
     - Strengths
     - Renderer-specific exports
   * - WebGL
     - Fast interaction with large scenes, responsive filtering, object
       inspection, and synchronized split views.
     - Rotating GIF.
   * - Plotly
     - Familiar Plotly controls and a portable interactive figure.
     - Standalone HTML.

PNG, share links, and view JSON are available from either renderer. Switch
renderers from the application header without reopening the source.

Where to go next
----------------

* :doc:`display` explains reconstruction/truth views, object filters, matching,
  hover attributes, geometry, and inspection.
* :doc:`appearance` covers continuous color ranges, visibility thresholds,
  point styling, axes, cameras, and themes.
* :doc:`sharing` describes portable links and every export format.
* :doc:`deployment` covers authentication, temporary source caches, Docker,
  and Kubernetes.
