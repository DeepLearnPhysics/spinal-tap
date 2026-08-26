Troubleshooting
===============

Nothing is drawn
----------------

Open the status control in the upper-right corner of the sidebar. A red status
records source, entry, rendering, and validation errors that would otherwise
appear only in the server log.

Then check:

* the file contains the selected reconstruction/truth product;
* at least one object is enabled in the scene-header filter;
* the visible-value range has not filtered every point;
* the selected truth point source exists in the file; and
* the geometry is not simply larger than the event at the current camera zoom.

A shared view sets controls but waits for Open
----------------------------------------------

Current view JSON and Share links open their referenced source automatically.
If controls are restored but the source is not, confirm that the referenced
Path is visible to this server or the URL is still public. Temporary uploaded
paths are intentionally not portable.

Path aliases at S3DF
--------------------

Both ``/sdf/data/neutrino/...`` and ``/data/...`` are accepted by the configured
S3DF deployment. If neither resolves locally, use the path visible to the
machine running Spinal Tap rather than the path visible to your browser.

An upload is rejected
---------------------

The ingress request limit applies to each chunk, not the total HDF5 size. Check
the per-file cache limit, total cache capacity, allowed-upload setting, and
available ephemeral storage. The default chunks are 32 MiB and the configured
S3DF ingress accepts 64 MiB requests.

The camera or geometry is unexpected
------------------------------------

Select **Reset view** after changing geometry. SPINE geometry metadata controls
the detector bounds and up direction. Clearing the detector intentionally
hides it until it is restored or a different source is opened.

WebGL and Plotly differ
-----------------------

The two renderers share scene content, filters, appearance settings, and view
exports, but they are independent rendering implementations. Use Plotly when
you need its native modebar or standalone HTML, and WebGL when interaction with
large scenes is the priority. Report a parity issue when the same selected
objects or values are missing in only one renderer.

Collecting a useful bug report
------------------------------

Include the Spinal Tap and SPINE versions shown in the header, renderer, object
and run modes, selected overlays, geometry, and the status message. A shared
link or exported view JSON is usually more useful than a screenshot because it
preserves the exact controls and camera.
