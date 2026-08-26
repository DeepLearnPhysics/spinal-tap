"""Tests for renderer-independent object inspection summaries."""

from types import SimpleNamespace

import numpy as np
import pytest

from spinal_tap.inspection import _format_value, inspect_object, object_collection_key


class Inspectable(SimpleNamespace):
    """Minimal SPINE-like object used by inspector tests."""

    enum_values = {"shape": {0: "SHOWER", 1: "TRACK"}}
    field_units = {"length": "cm", "calo_ke": "MeV"}

    def as_dict(self):
        """Return representative scalar and compact vector attributes."""
        return {
            "id": self.id,
            "size": 42,
            "shape": 1,
            "is_primary": True,
            "start_point": np.array([1.25, 2.5, 3.75]),
            "length": 12.5,
            "calo_ke": np.inf,
            "match_ids": np.array([7, 9]),
            "match_overlaps": np.array([0.9, 0.4]),
            "scores": np.arange(12),
        }


def test_object_collection_key_validates_selection_domains():
    """Inspection keys should name only supported output collections."""
    assert object_collection_key("truth", "particles") == "truth_particles"
    with pytest.raises(ValueError, match="prefix"):
        object_collection_key("raw", "particles")
    with pytest.raises(ValueError, match="family"):
        object_collection_key("reco", "hits")


def test_inspect_object_groups_and_formats_attributes():
    """Summaries should preserve enums, units, booleans and compact arrays."""
    summary = inspect_object(Inspectable(id=5), "reco", "particles", 3)

    assert summary["key"] == "reco:3"
    assert summary["title"] == "Reco Particle 5"
    rows = {
        row["name"]: row["value"]
        for group in summary["groups"].values()
        for row in group
    }
    assert rows["shape"] == "Track (1)"
    assert rows["is_primary"] == "True"
    assert rows["start_point"] == "[1.25, 2.5, 3.75]"
    assert rows["length"] == "12.5 cm"
    assert rows["calo_ke"] == "∞ MeV"
    assert rows["match_ids"] == "[7, 9]"
    assert rows["scores"] == "12 values · 0–11"


@pytest.mark.parametrize(
    "value,expected",
    [
        (np.nan, "—"),
        (-np.inf, "−∞"),
        ("", "—"),
        (None, "—"),
        (np.asarray(4), "4"),
        (np.asarray([]), "—"),
        (np.full(9, np.inf), "9 values"),
        (np.asarray(["value"] * 9), "9 values"),
    ],
)
def test_inspection_formats_missing_and_nonfinite_values(value, expected):
    """Unusual stored values should remain compact and human-readable."""
    assert _format_value(value) == expected


def test_inspect_object_supports_plain_objects_and_private_fields():
    """Plain objects should use public instance attributes as a fallback."""
    obj = SimpleNamespace(id=2, note="ready", _cache="ignored")

    summary = inspect_object(obj, "truth", "interactions", 0)

    assert summary["title"] == "Truth Interaction 2"
    rows = summary["groups"]["details"]
    assert rows == [{"name": "note", "label": "Note", "value": "ready"}]


def test_inspect_object_groups_schema_references_as_identifiers():
    """SPINE reference metadata should classify truth IDs without name lists."""
    obj = Inspectable(id=4)
    values = obj.as_dict()
    values["orig_parent_id"] = 12
    obj.as_dict = lambda: values
    obj.attr_metadata = lambda name: SimpleNamespace(
        index=name == "id",
        reference="particle" if name == "orig_parent_id" else None,
    )

    summary = inspect_object(obj, "truth", "particles", 0)
    identifiers = {row["name"] for row in summary["groups"]["identifiers"]}

    assert identifiers == {"id", "orig_parent_id"}


@pytest.mark.parametrize(
    "name,metadata,group",
    [
        ("flash_score", None, "detector_matching"),
        ("axis", SimpleNamespace(vector=True), "geometry"),
        ("visible_energy", SimpleNamespace(units="MeV"), "energy"),
        ("trigger_time", SimpleNamespace(units="ns"), "timing"),
    ],
)
def test_inspect_object_uses_metadata_for_semantic_groups(name, metadata, group):
    """Schema flags and units should place unfamiliar fields predictably."""
    obj = SimpleNamespace(id=1)
    obj.as_dict = lambda: {"id": 1, name: 2}
    if metadata is not None:
        obj.attr_metadata = lambda field: metadata if field == name else None

    summary = inspect_object(obj, "truth", "particles", 0)

    assert [row["name"] for row in summary["groups"][group]] == [name]
