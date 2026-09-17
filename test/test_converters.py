"""Tests for installed spine-prod conversion-bundle discovery."""

import os

import pytest

from spinal_tap.converters import (
    available_larcv_converters,
    resolve_larcv_converter,
)


def test_converter_discovery_and_resolution(monkeypatch, tmp_path):
    """Dated bundles should be listed and resolved by stable relative IDs."""
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first = first_root / "convert" / "2x2" / "truth_240819.yaml"
    duplicate = second_root / "convert" / "2x2" / "truth_240819.yaml"
    second = second_root / "convert" / "icarus" / "truth_240812.yaml"
    ignored = second_root / "convert" / "icarus" / "data_240812.yaml"
    for path in (first, duplicate, second, ignored):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")

    monkeypatch.delenv("SPINAL_TAP_LARCV_CONFIG_ROOT", raising=False)
    monkeypatch.setenv(
        "SPINE_CONFIG_PATH", os.pathsep.join((str(first_root), str(second_root)))
    )

    assert available_larcv_converters() == [
        {"label": "2x2 · truth_240819", "value": "2x2/truth_240819"},
        {"label": "icarus · truth_240812", "value": "icarus/truth_240812"},
    ]
    assert resolve_larcv_converter("2x2/truth_240819") == str(first.resolve())
    assert resolve_larcv_converter("icarus/truth_240812.yaml") == str(second.resolve())
    assert resolve_larcv_converter(str(second)) == str(second.resolve())


def test_converter_root_override_and_missing_error(monkeypatch, tmp_path):
    """The spinal-tap-specific root should override generic SPINE lookup."""
    monkeypatch.setenv("SPINE_CONFIG_PATH", str(tmp_path / "ignored"))
    monkeypatch.setenv("SPINAL_TAP_LARCV_CONFIG_ROOT", str(tmp_path / "selected"))

    assert available_larcv_converters() == []
    with pytest.raises(FileNotFoundError, match="missing/truth_000000"):
        resolve_larcv_converter("missing/truth_000000")
