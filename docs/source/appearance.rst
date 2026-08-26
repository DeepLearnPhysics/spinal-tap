Appearance and Cameras
======================

Point appearance
----------------

Open **Appearance** beside the attribute selector to adjust point size and
opacity. These settings are renderer-neutral and are included in shared and
exported view state.

Continuous color
----------------

When the selected color field is continuous, Appearance also provides:

* a continuous colorscale;
* linear or logarithmic mapping;
* a histogram of the values in the current event;
* an automatic or manual color domain; and
* all values or a restricted visible range.

The color domain controls how values map onto the colorscale. The visible range
filters which points are drawn. They are intentionally independent: use a fixed
domain to compare colors across events, and a visible range to threshold the
current point cloud.

Drag across the histogram to select a range, or use the numeric controls for an
exact boundary. Histogram interaction is committed when the selection
finishes, avoiding repeated server redraws while dragging.

Categorical color
-----------------

Categorical and enumerated fields use discrete category colors rather than a
continuous colorscale. SPINE field metadata determines whether an attribute is
continuous, categorical, an identifier, or unsuitable for color. Integer
physics categories such as PDG code remain valid categorical color sources.

Axes, camera, and theme
-----------------------

Use **Axes** to remove or restore the coordinate frame. **Reset view** returns
to the detector-aware default camera. The header theme switch follows the
browser's preferred color scheme until the user explicitly chooses Light or
Dark.

WebGL and Plotly keep renderer-specific camera state. In split mode, camera
synchronization applies only while **Sync cameras** is active.
