"""Classify data sources independently of their filename extensions."""

import json
from pathlib import Path


def read_file_manifest(file_path: str | Path) -> list[str]:
    """Read non-empty, non-commented source records from a text manifest."""
    try:
        lines = Path(file_path).read_text(encoding="utf-8-sig").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError(
            "The source is neither HDF5 nor readable UTF-8 text."
        ) from error
    records = [line.strip() for line in lines]
    records = [line for line in records if line and not line.startswith("#")]
    if not records:
        raise ValueError("The file manifest does not contain any source paths.")
    return records


def detect_source_file(file_path: str | Path) -> str:
    """Identify an exact local file as HDF5, JSON, or a path manifest."""
    import h5py

    file_path = Path(file_path)
    if h5py.is_hdf5(file_path):
        return "hdf5"

    try:
        with open(file_path, encoding="utf-8-sig") as source:
            json.load(source)
        return "json"
    except json.JSONDecodeError:
        read_file_manifest(file_path)
        return "manifest"
    except UnicodeDecodeError as error:
        raise ValueError(
            "The source is not HDF5, JSON, or a UTF-8 file manifest."
        ) from error
