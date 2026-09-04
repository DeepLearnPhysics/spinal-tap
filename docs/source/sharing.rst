Sharing and Exporting
=====================

Share links
-----------

**Share** copies a URL whose fragment contains the current renderer-neutral
view state. The fragment includes the source, entry, display controls,
attributes, appearance, geometry, object filters, renderer, and camera. URL
fragments are not sent in ordinary HTTP requests or server access logs.

The link does not contain HDF5 data. Its source must remain accessible to the
recipient's deployment. Private temporary uploads cannot be shared because
their cache paths belong to one browser session.

View JSON
---------

**Export JSON** downloads the same reproducible view state as a file. Open that
JSON through Path, Browse/Upload, or URL just like any other source. Loading the
view opens its underlying HDF5 source and applies the saved state once the event
is available.

The view is a starting point rather than a lock: after it loads, normal event
navigation preserves the user's current camera behavior instead of repeatedly
restoring the imported camera on every entry.

Images and interactive exports
------------------------------

.. list-table::
   :header-rows: 1
   :widths: 24 18 58

   * - Export
     - Renderer
     - Result
   * - Save PNG
     - Both
     - A static image of the current scene, with optional logos and labels.
   * - Save GIF
     - WebGL
     - A smooth rotation around the geometry's up axis and current camera
       pivot.
   * - Save HTML
     - Plotly
     - A standalone interactive Plotly figure.
   * - Share
     - Both
     - A URL fragment that restores the view in Spinal Tap.
   * - Export JSON
     - Both
     - A portable, human-readable view configuration.

Labels
------

The **Labels** menu controls which annotations are included in PNG and GIF
exports. The available items are the SPINE logo, detector logo, source name,
entry number, and run/subrun/event identifiers. SPINE and the entry number are
enabled by default. Detector branding is selected from the active geometry.
These annotations are applied only to exported media; they do not consume
canvas space while the event is being explored.

Long source names are shortened in the rendered label, and metadata labels are
positioned separately from reconstruction/truth view titles. Label selections
are retained in share links and view JSON.

Use the SPINE watermark when the image represents SPINE reconstruction output.
Detector logos are useful for talks and notes, but should not imply an official
experiment result without the collaboration's normal approval.

For WebGL GIFs, select a rendered point, endpoint, direction, or vertex and use
**Center here** in the inspector before saving to rotate around that feature.
Without a selected pivot, the export uses the normal scene center.
