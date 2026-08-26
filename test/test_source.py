"""Tests for content-based source classification."""

import json

import h5py
import pytest

from spinal_tap.source import detect_source_file, read_file_manifest


def test_read_manifest_strips_comments_and_utf8_bom(tmp_path):
    """Manifest records should be extension-independent and normalized."""
    path = tmp_path / "sources.anything"
    path.write_text("\ufeff# comment\n first.h5 \n\nhttps://example/a.h5\n")
    assert read_file_manifest(path) == ["first.h5", "https://example/a.h5"]


def test_read_manifest_rejects_empty_and_binary_files(tmp_path):
    """Unreadable and empty manifests should provide specific diagnostics."""
    empty = tmp_path / "empty.list"
    empty.write_text("# only comments\n")
    with pytest.raises(ValueError, match="does not contain"):
        read_file_manifest(empty)

    binary = tmp_path / "binary.list"
    binary.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(ValueError, match="readable UTF-8"):
        read_file_manifest(binary)


def test_detect_source_file_by_content(tmp_path):
    """HDF5, JSON and manifest sources should not depend on suffixes."""
    hdf5_path = tmp_path / "hdf5.data"
    with h5py.File(hdf5_path, "w") as output:
        output.create_dataset("events", data=[0])
    json_path = tmp_path / "view.data"
    json_path.write_text(json.dumps({"version": 1}))
    manifest_path = tmp_path / "manifest.data"
    manifest_path.write_text("events.h5\n")

    assert detect_source_file(hdf5_path) == "hdf5"
    assert detect_source_file(json_path) == "json"
    assert detect_source_file(manifest_path) == "manifest"

    invalid = tmp_path / "invalid.data"
    invalid.write_bytes(b"\xff\xfe")
    with pytest.raises(ValueError, match="not HDF5, JSON"):
        detect_source_file(invalid)
