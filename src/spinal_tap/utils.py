"""Defines basic functions used by the Spinal Tap application."""

import glob
import os
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Iterable, Optional, Tuple

from spine.construct import BuildManager
from spine.io.read import HDF5Reader

from .source import detect_source_file, read_file_manifest

S3DF_DATA_ROOT = "/sdf/data/neutrino"
CONTAINER_DATA_ROOT = "/data"
READER_CACHE_SIZE = int(os.getenv("SPINAL_TAP_READER_CACHE_SIZE", "8"))
EVENT_CACHE_SIZE = int(os.getenv("SPINAL_TAP_EVENT_CACHE_SIZE", "2"))

_CACHE_LOCK = RLock()


def canonicalize_data_path(file_path: str) -> str:
    """Canonicalize equivalent S3DF and container data paths.

    Parameters
    ----------
    file_path : str
        File path using either the S3DF or container data root.

    Returns
    -------
    str
        Normalized path expressed under the container data root.
    """
    file_path = file_path.strip()
    if file_path.startswith(("http://", "https://")):
        return file_path
    file_path = os.path.normpath(file_path)

    if file_path == S3DF_DATA_ROOT:
        return CONTAINER_DATA_ROOT
    if file_path.startswith(S3DF_DATA_ROOT + os.sep):
        suffix = file_path[len(S3DF_DATA_ROOT) :]
        return CONTAINER_DATA_ROOT + suffix

    return file_path


def get_data_path_candidates(file_path: str) -> list[str]:
    """Return equivalent filesystem paths in preferred order.

    Parameters
    ----------
    file_path : str
        File path or glob using either the S3DF or container data root.

    Returns
    -------
    list[str]
        Original path followed by its alias, when applicable.
    """
    file_path = os.path.normpath(file_path.strip())
    candidates = [file_path]

    # Keep the path supplied by the user as the first choice
    if file_path == S3DF_DATA_ROOT:
        candidates.append(CONTAINER_DATA_ROOT)
    elif file_path.startswith(S3DF_DATA_ROOT + os.sep):
        suffix = file_path[len(S3DF_DATA_ROOT) :]
        candidates.append(CONTAINER_DATA_ROOT + suffix)
    elif file_path == CONTAINER_DATA_ROOT:
        candidates.append(S3DF_DATA_ROOT)
    elif file_path.startswith(CONTAINER_DATA_ROOT + os.sep):
        suffix = file_path[len(CONTAINER_DATA_ROOT) :]
        candidates.append(S3DF_DATA_ROOT + suffix)

    return candidates


def resolve_data_path(file_path: str) -> str:
    """Resolve an S3DF data path through either equivalent mount point.

    Parameters
    ----------
    file_path : str
        File path or glob using either the S3DF or container data root.

    Returns
    -------
    str
        First equivalent path which matches at least one file. If neither
        matches, return the original normalized path so the reader reports it.
    """
    candidates = get_data_path_candidates(file_path)
    for candidate in candidates:
        if glob.glob(candidate):
            return candidate

    return candidates[0]


def get_file_signature(
    file_path: str | Iterable[str],
) -> tuple[tuple[str, int, int], ...]:
    """Return metadata used to invalidate cached readers for changed files.

    Parameters
    ----------
    file_path : str
        Resolved file path or glob.

    Returns
    -------
    tuple
        Sorted ``(path, size, modification time)`` records for matching files.
    """
    file_keys = [file_path] if isinstance(file_path, str) else list(file_path)
    paths = {path for key in file_keys for path in glob.glob(key)}
    signature = []
    for path in sorted(paths):
        stat = os.stat(path)
        signature.append((path, stat.st_size, stat.st_mtime_ns))

    return tuple(signature)


@lru_cache(maxsize=READER_CACHE_SIZE)
def _initialize_reader_cached(
    file_keys: tuple[str, ...],
    use_run: bool,
    file_signature: tuple[tuple[str, int, int], ...],
) -> HDF5Reader:
    """Construct one cached reader for an unchanged file collection."""
    keys = file_keys[0] if len(file_keys) == 1 else list(file_keys)
    return HDF5Reader(keys, create_run_map=use_run, skip_unknown_attrs=True)


def resolve_source_path(source: str) -> str:
    """Materialize a URL or resolve an equivalent local data path."""
    if source.strip().startswith(("http://", "https://")):
        from .cache import cache_manager

        return cache_manager.fetch_url(source.strip())
    return resolve_data_path(source)


def classify_source(source: str) -> tuple[str, str]:
    """Return the content kind and resolved path for one source expression."""
    resolved = resolve_source_path(source)
    if glob.has_magic(resolved) and not os.path.isfile(resolved):
        return "hdf5", resolved
    if not os.path.isfile(resolved):
        # Preserve the reader's useful missing-path diagnostics for path/glob
        # expressions which do not currently resolve to an exact file.
        return "hdf5", resolved
    return detect_source_file(resolved), resolved


def resolve_reader_keys(source: str) -> tuple[tuple[str, ...], tuple]:
    """Resolve an HDF5 expression or content-detected path manifest."""
    kind, resolved = classify_source(source)
    if kind == "json":
        raise ValueError("A shared-view JSON document is not an HDF5 data source.")
    if kind == "manifest":
        manifest_root = Path(resolved).parent
        keys = []
        for record in read_file_manifest(resolved):
            if record.startswith(("http://", "https://")):
                keys.append(resolve_source_path(record))
            else:
                path = Path(record).expanduser()
                if not path.is_absolute():
                    path = manifest_root / path
                keys.append(resolve_data_path(str(path)))
        signature = (
            (resolved, os.path.getsize(resolved), os.stat(resolved).st_mtime_ns),
            *get_file_signature(keys),
        )
        return tuple(keys), tuple(signature)
    keys = (resolved,)
    return keys, get_file_signature(keys)


def initialize_reader(file_path: str, use_run: bool = False) -> HDF5Reader:
    """Initialize the HDF5 reader.

    TODO: add option to read from LArCV files (more tricky)

    Parameters
    ----------
    file_path : str
        Path to the file to load
    use_run : bool
        If `True`, build the run map to fetch the entries by (run, subrun, event)

    Returns
    -------
    HDF5Reader
        File reader
    """
    file_keys, signature = resolve_reader_keys(file_path)

    # Reader construction and persistent HDF5 handles are shared per process
    with _CACHE_LOCK:
        return _initialize_reader_cached(file_keys, use_run, signature)


def get_reader_products(reader: HDF5Reader) -> set[str]:
    """Return the event products advertised by a SPINE reader configuration.

    Parameters
    ----------
    reader : HDF5Reader
        Initialized reader for the selected file collection.

    Returns
    -------
    set[str]
        Product names expected in each event.
    """
    cfg = reader.cfg or {}
    writer = cfg.get("io", {}).get("writer", {})
    products = set(writer.get("keys", []))
    if products:
        return products

    # Older files may not embed their writer configuration. Reading the root
    # product names is metadata-only and avoids loading an expensive event just
    # to configure the controls.
    try:
        import h5py

        product_sets = []
        for path in reader.file_paths:
            if reader.is_remote_path(path):
                break
            with h5py.File(path, "r") as file:
                product_sets.append(set(file.keys()).difference({"events", "info"}))
        if product_sets:
            return set.intersection(*product_sets)
    except (OSError, ImportError):
        pass

    # Unknown metadata should not disable valid controls preemptively.
    return {
        f"{prefix}_{obj}"
        for prefix in ("reco", "truth")
        for obj in ("fragments", "particles", "interactions")
    } | {"points", "depositions", "flashes", "crthits"}


@lru_cache(maxsize=EVENT_CACHE_SIZE)
def _load_data_cached(reader: HDF5Reader, entry: int, mode: str, obj: str) -> Tuple[
    Dict[str, Any],
    Optional[Dict[str, str]],
    Optional[int],
    Optional[int],
    Optional[int],
]:
    """Read and build one event for reuse by presentation callbacks."""
    return _load_data(reader, entry, mode, obj)


def load_data(reader: HDF5Reader, entry: int, mode: str, obj: str) -> Tuple[
    Dict[str, Any],
    Optional[Dict[str, str]],
    Optional[int],
    Optional[int],
    Optional[int],
]:
    """Loads one entry from an HDF5 SPINE reconstruction file.

    Parameters
    ----------
    reader : HDF5Reader
        Path to the file reader
    entry : int
        Entry to load within the file
    mode : str
        Run mode (one of 'reco', 'truth' or 'both')
    obj : str
        Type of object to load

    Returns
    -------
    dict
        Data product dictionary
    dict
        Geometry configuration, if available in the file
    int
        Run number
    int
        Subrun number
    int
        Event number
    """
    # Serialize cache misses because readers retain process-local HDF5 handles
    with _CACHE_LOCK:
        return _load_data_cached(reader, entry, mode, obj)


def _load_data(reader: HDF5Reader, entry: int, mode: str, obj: str) -> Tuple[
    Dict[str, Any],
    Optional[Dict[str, str]],
    Optional[int],
    Optional[int],
    Optional[int],
]:
    """Read and build one uncached event."""
    # Load the entry as a dictionary
    data = reader.get(entry)

    # Initialize the builder
    builder = BuildManager(
        obj == "fragments",
        obj in ["particles", "interactions"],
        obj == "interactions",
        mode=mode,
    )

    # Process the entry through the builder
    builder(data)

    # Return geometry configuration if available
    geo = None
    if reader.cfg is not None:
        geo = reader.cfg.get("geo", None)

    # Return run info if available
    run, subrun, event = None, None, None
    if "run_info" in data:
        run_info = data["run_info"]
        run, subrun, event = run_info.run, run_info.subrun, run_info.event

    # Return
    return data, geo, run, subrun, event


def clear_data_caches() -> None:
    """Clear process-local reader and built-event caches."""
    with _CACHE_LOCK:
        _load_data_cached.cache_clear()
        _initialize_reader_cached.cache_clear()


def get_data_cache_info() -> dict[str, Any]:
    """Return process-local reader and event cache statistics."""
    return {
        "readers": _initialize_reader_cached.cache_info(),
        "events": _load_data_cached.cache_info(),
    }
