"""Tests for event-display object filtering."""

from types import SimpleNamespace

import numpy as np
import pytest

from spinal_tap.filtering import (
    build_object_filter_options,
    filter_event_objects,
    get_object_prefixes,
)


def make_object(object_id, point_count):
    """Build a minimal output-object stand-in."""
    return SimpleNamespace(id=object_id, index=np.arange(point_count))


def test_get_object_prefixes():
    """Drawer modes should map to the same ordered prefixes as spine.vis."""
    assert get_object_prefixes("reco") == ["reco"]
    assert get_object_prefixes("truth") == ["truth"]
    assert get_object_prefixes("both") == ["reco", "truth"]
    assert get_object_prefixes("all") == ["reco", "truth"]

    with pytest.raises(ValueError, match="Unsupported"):
        get_object_prefixes("bad")


def test_build_object_filter_options():
    """Filter options should identify prefix, position, ID and point count."""
    data = {
        "reco_particles": [make_object(7, 12)],
        "truth_particles": [make_object(3, 5)],
    }

    options = build_object_filter_options(data, "both", "particles")

    assert options == [
        {"label": "Reco Particle 7 · 12 pts", "value": "reco:0"},
        {"label": "Truth Particle 3 · 5 pts", "value": "truth:0"},
    ]


def test_filter_event_objects():
    """Filtering should copy object collections while sharing event arrays."""
    points = np.ones((3, 3), dtype=np.float32)
    reco = [make_object(1, 1), make_object(2, 2)]
    truth = [make_object(3, 3)]
    data = {
        "points": points,
        "reco_particles": reco,
        "truth_particles": truth,
    }

    unfiltered, visible, total = filter_event_objects(data, "both", "particles", [])
    assert visible == total == 3
    assert unfiltered["reco_particles"] == reco
    assert unfiltered["reco_particles"] is not reco
    assert unfiltered["points"] is points

    filtered, visible, total = filter_event_objects(
        data, "both", "particles", ["reco:0"]
    )
    assert visible == 2
    assert total == 3
    assert filtered["reco_particles"] == [reco[1]]
    assert filtered["truth_particles"] == truth
    assert data["reco_particles"] == reco
