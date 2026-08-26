Deployment
==========

Local service
-------------

The default local command is unauthenticated and may read paths available to
the user running the process:

.. code-block:: bash

   spinal-tap --host 127.0.0.1 --port 8888

Do not expose this development-style service directly to an untrusted network.
Use an authenticated deployment with a production WSGI server and ingress for
shared installations.

Authentication
--------------

Set ``SPINAL_TAP_AUTH=true`` to require an experiment and shared password. The
authenticated landing page follows the browser's light or dark preference and
shows only the sign-in interface. After login, path access is restricted to the
experiment and configured shared folders.

The repository's ``k8s/AUTHENTICATION.md`` guide describes secret generation,
experiment mappings, and local authentication testing. Passwords, Flask session
keys, and other secrets must remain outside version control.

Temporary source cache
----------------------

Uploads and URL downloads use a bounded server-side cache. The relevant
environment variables are:

.. list-table::
   :header-rows: 1
   :widths: 48 22 30

   * - Variable
     - Default
     - Purpose
   * - ``SPINAL_TAP_CACHE_DIR``
     - ``/tmp/spinal-tap-cache``
     - Cache root.
   * - ``SPINAL_TAP_CACHE_MAX_BYTES``
     - 20 GiB
     - Total cache size.
   * - ``SPINAL_TAP_CACHE_FILE_MAX_BYTES``
     - 2 GiB
     - Maximum source size.
   * - ``SPINAL_TAP_CACHE_TTL_SECONDS``
     - 86400
     - Idle lifetime in seconds.
   * - ``SPINAL_TAP_UPLOAD_CHUNK_BYTES``
     - 32 MiB
     - Browser upload request size.
   * - ``SPINAL_TAP_UPLOAD_MAX_CHUNK_BYTES``
     - 64 MiB
     - Maximum accepted request chunk.
   * - ``SPINAL_TAP_ALLOW_UPLOADS``
     - true
     - Enable browser uploads.
   * - ``SPINAL_TAP_ALLOW_URLS``
     - true
     - Enable public URL downloads.

URL downloads reject private, loopback, and special network destinations. This
prevents the source field from becoming a server-side request forgery path.

Process-local caches
--------------------

Readers, built events, and compact binary scenes are cached per application
process. Configure their bounds with ``SPINAL_TAP_READER_CACHE_SIZE`` (default
8), ``SPINAL_TAP_EVENT_CACHE_SIZE`` (default 2), and
``SPINAL_TAP_SCENE_CACHE_SIZE`` (default 8, minimum 1).

Kubernetes and S3DF
-------------------

The ``k8s/`` directory contains the deployment, service, ingress, cache volume,
and authentication manifests used at S3DF. Consult ``k8s/README.md`` and
``k8s/SLAC_CONFIG.md`` before applying them.

The S3DF deployment accepts both ``/sdf/data/neutrino/...`` host paths and
``/data/...`` container aliases. Browser filesystem browsing is not exposed in
authenticated mode; users may upload a selected local file without learning
or traversing the server filesystem.
