Loading Data
============

Source modes
------------

The **Data** panel separates opening a source from navigating within the source.
Choose a source mode, select **Open**, and then use **Go** or the navigation
arrows to load entries.

.. list-table::
   :header-rows: 1
   :widths: 18 38 44

   * - Mode
     - Use it for
     - Behavior
   * - Path / URL
     - A server-visible path or glob, or a public HTTP(S) URL.
     - Opens paths directly. Downloads URLs into the bounded temporary cache
       before opening them.
   * - Browse
     - A local file selected with the operating-system picker.
     - Transfers the selected file into a private temporary cache. This label
       is used by an unauthenticated local deployment.
   * - Upload
     - A workstation file sent to an authenticated hosted deployment.
     - Uses the same private temporary cache as Browse, in retryable chunks.

Pressing Enter in the Path / URL field performs the same action as **Open**.
Pressing Enter in the event selector performs the same action as **Go**.

Accepted source documents
-------------------------

Spinal Tap identifies exact files by content rather than extension. It accepts:

* SPINE HDF5 output;
* LArCV2 ROOT input when running the LArCV container flavor;
* a saved Spinal Tap view JSON document; or
* a UTF-8 file manifest.

LArCV conversion bundles
------------------------

LArCV tree names and detector geometry are producer-specific. Open a ROOT
source first; after Spinal Tap detects its content, it reveals **LArCV
converter** beneath the Open button and waits for a matching dated bundle.
Selecting the bundle resumes the load automatically and dismisses the chooser.
The control stays hidden for other source types.
Spinal Tap then parses and builds the SPINE truth representation in memory; it
does not write an intermediate HDF5 file. A manifest may contain several LArCV
files that use the same bundle, but it cannot mix LArCV and HDF5 files.

Detector conversion knowledge is maintained in ``spine-prod`` and copied into
the LArCV image at build time. Install an additional configuration tree by
setting ``SPINAL_TAP_LARCV_CONFIG_ROOT`` (or ``SPINE_CONFIG_PATH``) to its
``config`` directory. ``SPINAL_TAP_LARCV_CONFIG`` can set a default converter
ID or an explicit bundle path for non-interactive deployments.

Spinal Tap intentionally does not guess a detector or schema from tree names:
different production vintages can use overlapping names with different
semantics. If a bundle reports missing trees, select the matching vintage or
add the required variant in ``spine-prod``.

A manifest contains one source path per line. Blank lines and records beginning
with ``#`` are ignored. Relative records are resolved beside the manifest, and
globs are supported both in the Path field and in manifest records. The file
may be named ``files.txt``, ``files.list``, or have no extension.

Event selection
---------------

Select **Entry** to address the zero-based entry index directly. Select **Run**
to address a run, subrun, and event tuple. The header reports the loaded entry
and the valid final index; for example, ``Entry 4/4`` is the last of five
entries.

If an entry or run tuple is not present, the status control turns red. Open the
status popover to read the error rather than consulting the server terminal.

Temporary and portable sources
------------------------------

Browse, Upload, and URL sources are copied into a temporary server cache. The
default per-file limit is 2 GiB, the total cache limit is 20 GiB, and idle files
expire after 24 hours. Deployments may change these limits.

Uploaded sources are private to the browser session and are not portable.
Consequently a view backed by an upload cannot be shared with another user.
Path and URL sources can be shared when the recipient's deployment can resolve
the same source. See :doc:`sharing`.
