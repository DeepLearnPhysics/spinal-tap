Exploring an Event
==================

Run mode and object level
-------------------------

**Run mode** selects reconstructed objects, truth objects, or both. Unavailable
modes are disabled when the file does not contain their products. When truth is
visible, **Point source** selects the truth coordinate representation supported
by the file: label, adapted, or Geant4 points.

**Object** selects fragments, particles, or interactions. The application uses
SPINE's object metadata to expose only valid hover and color attributes for the
current mode and object level.

Scene overlays
--------------

The **Show** controls add auxiliary layers:

* **End points** displays particle start and end positions;
* **Directions** displays direction vectors;
* **Vertices** displays interaction vertices;
* **Raw** displays raw input points while retaining object association on
  hover when available;
* **Flash** and **CRT** select off, all, or matched detector overlays.

Controls that do not apply to the current object level are disabled. For
example, interactions do not have particle end-point attributes.

Object filtering and matching
-----------------------------

The object selectors in the scene header replace Plotly's large per-object
legend. They are available in both renderers and update the existing WebGL
scene without rebuilding it.

When reconstruction and truth are displayed together, the chain control links
the two selectors. A change on one side applies to its immediate SPINE matches
on the other side. Matching is deliberately one hop only; it does not recurse
through the bipartite match graph.

Split scenes and cameras
------------------------

In **Both** mode, **Split scenes** places reconstruction and truth side by side.
Disable it to overlay both collections in one viewport. **Sync cameras** keeps
the split viewports at the same camera pose. Disable synchronization to inspect
the two sides independently.

Geometry and orientation
------------------------

When the HDF5 metadata identifies a detector geometry, Spinal Tap selects it
automatically. Clearing the detector hides it for the current source. The
detector selector still remembers the detected value, so it can be restored
without knowing the geometry name.

SPINE geometry metadata also specifies the detector's up direction. Horizontal
drift detectors normally use ``y`` as up, while supported vertical-drift
detectors use ``x``.

Hover and object inspection
---------------------------

Choose fields in **Attributes** to add them to hover information, and select one
compatible scalar or categorical field for color. Per-point fields such as
depositions update with the exact point under the cursor.

Click an object to open the inspector. In **Both** mode, the inspector also
identifies direct matches on the opposite side. **Show only** isolates the
selected object and its immediate matches; selecting it again restores the
previous visibility set.

Keyboard shortcuts
------------------

Shortcuts are active when focus is outside a text field or menu.

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Key
     - Action
   * - Left / Right
     - Load the previous or next entry.
   * - R
     - Reset the camera.
   * - A
     - Toggle axes.
   * - S
     - Save a PNG.
   * - E
     - Export the current view as JSON.
   * - Escape
     - Close the object inspector.
   * - ?
     - Open or close the shortcut reference in the application header.
