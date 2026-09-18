"""Tests for installed spine-prod conversion-bundle discovery."""

import os

import pytest

from spinal_tap.converters import (
    _converter_tags,
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


def test_converter_options_inherit_spine_prod_tags(monkeypatch, tmp_path):
    """Ambiguous detector vintages should use their config metadata labels."""
    root = tmp_path / "config"
    convert = root / "convert" / "sbnd"
    io = root / "infer" / "sbnd" / "io"
    convert.mkdir(parents=True)
    io.mkdir(parents=True)
    (io / "io_240720.yaml").write_text(
        "__meta__:\n  kind: bundle\n  tags: [without-crt, with-xa]\n"
    )
    (convert / "truth_240720.yaml").write_text(
        "__meta__:\n  kind: bundle\ninclude: infer/sbnd/io/io_240720.yaml\n"
    )
    (convert / "truth_250328.yaml").write_text(
        "__meta__:\n  kind: bundle\n  tags: [with-crt, with-xa]\n"
    )
    monkeypatch.setenv("SPINAL_TAP_LARCV_CONFIG_ROOT", str(root))

    assert available_larcv_converters() == [
        {
            "label": "sbnd · truth_240720 · without-crt, with-xa",
            "value": "sbnd/truth_240720",
        },
        {
            "label": "sbnd · truth_250328 · with-crt, with-xa",
            "value": "sbnd/truth_250328",
        },
    ]

    cycle = root / "cycle.yaml"
    cycle.write_text("include: cycle.yaml\n")
    assert _converter_tags(cycle, [root]) == []
    malformed = root / "malformed.yaml"
    malformed.write_text("[not valid yaml")
    assert _converter_tags(malformed, [root]) == []


def test_converter_root_override_and_missing_error(monkeypatch, tmp_path):
    """The spinal-tap-specific root should override generic SPINE lookup."""
    monkeypatch.setenv("SPINE_CONFIG_PATH", str(tmp_path / "ignored"))
    monkeypatch.setenv("SPINAL_TAP_LARCV_CONFIG_ROOT", str(tmp_path / "selected"))

    assert available_larcv_converters() == []
    with pytest.raises(FileNotFoundError, match="missing/truth_000000"):
        resolve_larcv_converter("missing/truth_000000")
