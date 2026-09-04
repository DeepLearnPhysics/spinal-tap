"""Tests for event-display object filtering."""

from types import SimpleNamespace

import numpy as np
import pytest
from plotly import graph_objects as go

from spinal_tap.filtering import (
    _compact_count,
    attach_object_filter_metadata,
    build_object_filter_options,
    build_object_match_links,
    filter_event_objects,
    get_object_prefixes,
)


def test_compact_count_formats_large_values():
    """Dropdown counts should remain compact across thousand and million scales."""
    assert _compact_count(1_200) == "1.2k"
    assert _compact_count(2_000_000) == "2M"


def make_object(object_id, point_count, match_ids=()):
    """Build a minimal output-object stand-in."""
    return SimpleNamespace(
        id=object_id,
        index=np.arange(point_count),
        match_ids=np.asarray(match_ids, dtype=np.int32),
    )


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
        "reco_particles": [make_object(7, 12), make_object(8, 6)],
        "truth_particles": [make_object(3, 5), make_object(4, 2)],
    }

    options = build_object_filter_options(data, "both", "particles")

    assert options == [
        {"label": "Reco Particle 7 · 12 pts", "value": "reco:0"},
        {"label": "Reco Particle 8 · 6 pts", "value": "reco:1"},
        {"label": "Truth Particle 3 · 5 pts", "value": "truth:0"},
        {"label": "Truth Particle 4 · 2 pts", "value": "truth:1"},
    ]


def test_build_object_filter_options_compacts_large_point_counts():
    """Large point counts should remain useful without dominating the menu."""
    data = {"reco_particles": [make_object(4, 8386)]}

    assert build_object_filter_options(data, "reco", "particles") == [
        {"label": "Particle 4 · 8.4k pts", "value": "reco:0"}
    ]


def test_build_object_match_links_is_symmetric_and_one_hop():
    """Match links should translate IDs to positions without graph expansion."""
    data = {
        "reco_particles": [
            make_object(10, 2, [21, 22]),
            make_object(11, 2, [22]),
        ],
        "truth_particles": [
            make_object(21, 2, [10]),
            make_object(22, 2, [10, 11]),
        ],
    }

    assert build_object_match_links(data, "particles") == {
        "reco:0": ["truth:0", "truth:1"],
        "reco:1": ["truth:1"],
        "truth:0": ["reco:0"],
        "truth:1": ["reco:0", "reco:1"],
    }

    data["reco_particles"][0].match_ids = np.asarray([999], dtype=np.int32)
    data["truth_particles"][0].match_ids = np.asarray([], dtype=np.int32)
    data["truth_particles"][1].match_ids = np.asarray([11], dtype=np.int32)
    assert "reco:0" not in build_object_match_links(data, "particles")


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

    empty, visible, total = filter_event_objects(data, "both", "particles", [])
    assert visible == 0
    assert total == 3
    assert empty["reco_particles"] == []
    assert empty["truth_particles"] == []
    assert empty["points"] is points

    filtered, visible, total = filter_event_objects(
        data, "both", "particles", ["reco:1", "truth:0"]
    )
    assert visible == 2
    assert total == 3
    assert filtered["reco_particles"] == [reco[1]]
    assert filtered["truth_particles"] == truth
    assert filtered["reco_particles"] is not reco
    assert data["reco_particles"] == reco


def test_attach_object_filter_metadata():
    """Combined traces should receive compact browser filter boundaries."""
    layer = SimpleNamespace(
        name="Reco particles",
        point_count=5,
        object_offsets=np.array([0, 2, 5]),
        metadata={"object_name": "reco_particles"},
    )
    scene = SimpleNamespace(views=[SimpleNamespace(layers=[layer])])
    figure = go.Figure(
        data=[
            go.Scatter3d(
                name="Reco particles",
                x=np.arange(5),
                y=np.arange(5),
                z=np.arange(5),
            )
        ]
    )
    figure.update_layout(meta={"appearance_histogram": {"values": [1, 2]}})

    attach_object_filter_metadata(
        figure, scene, revision="render-42", selection=["reco:4", "reco:9"]
    )

    assert figure.layout.meta == {
        "appearance_histogram": {"values": [1, 2]},
        "spinal_tap_filter_revision": "render-42",
        "spinal_tap_filter_selection": ["reco:4", "reco:9"],
    }
    assert figure.data[0].meta == {
        "spinal_tap_filter": {
            "prefix": "reco",
            "family": "particles",
            "offsets": [0, 2, 5],
            "keys": ["reco:4", "reco:9"],
        }
    }


def test_attach_filter_metadata_skips_irrelevant_layers_and_checks_traces():
    """Only combined object layers should require one matching Plotly trace."""
    irrelevant = SimpleNamespace(
        name="Detector", point_count=0, object_offsets=None, metadata={}
    )
    auxiliary = SimpleNamespace(
        name="Reco particle directions",
        metadata={"kind": "directions", "object_name": "reco_particles"},
    )
    empty = SimpleNamespace(
        name="Empty",
        point_count=0,
        object_offsets=np.asarray([0]),
        metadata={"object_name": "reco_particles"},
    )
    scene = SimpleNamespace(
        views=[SimpleNamespace(layers=[irrelevant, auxiliary, empty])]
    )
    attach_object_filter_metadata(go.Figure(), scene, revision=1)

    nonempty = SimpleNamespace(
        name="Missing",
        point_count=2,
        object_offsets=np.asarray([0, 2]),
        metadata={"object_name": "reco_particles"},
    )
    scene = SimpleNamespace(views=[SimpleNamespace(layers=[nonempty])])
    with pytest.raises(RuntimeError, match="Expected one combined"):
        attach_object_filter_metadata(go.Figure(), scene, revision=2)


def test_attach_filter_metadata_falls_back_to_contiguous_keys():
    """Incomplete selections should not corrupt the trace-to-object mapping."""
    layer = SimpleNamespace(
        name="Reco particles",
        point_count=2,
        object_offsets=np.asarray([0, 1, 2]),
        metadata={"object_name": "reco_particles"},
    )
    figure = go.Figure(go.Scatter3d(name=layer.name, x=[0, 1], y=[0, 1], z=[0, 1]))

    attach_object_filter_metadata(
        figure,
        SimpleNamespace(views=[SimpleNamespace(layers=[layer])]),
        revision=1,
        selection=["reco:8"],
    )

    assert figure.data[0].meta["spinal_tap_filter"]["keys"] == [
        "reco:0",
        "reco:1",
    ]


def test_attach_filter_metadata_maps_plotly_auxiliary_features():
    """Plotly markers, arrow shafts and tips should retain semantic parents."""
    marker = SimpleNamespace(
        name="Reco particle start point",
        positions=np.asarray([[1, 2, 3], [4, 5, 6]], dtype=float),
        object_ids=np.asarray([0, 1]),
        metadata={"kind": "start_point", "object_name": "reco_particles"},
    )
    direction = SimpleNamespace(
        name="Reco particle directions",
        origins=np.asarray([[0, 0, 0], [10, 0, 0]], dtype=float),
        vectors=np.asarray([[1, 0, 0], [0, 1, 0]], dtype=float),
        object_ids=np.asarray([0, 1]),
        scale=10,
        head_size=0.25,
        metadata={"kind": "directions", "object_name": "reco_particles"},
    )
    vertex = SimpleNamespace(
        name="Reco interaction vertex",
        positions=np.asarray([[7, 8, 9]], dtype=float),
        object_ids=np.asarray([5]),
        metadata={"kind": "vertex", "object_name": "reco_interactions"},
    )
    figure = go.Figure(
        data=[
            go.Scatter3d(
                name=marker.name,
                mode="markers",
                x=marker.positions[:, 0],
                y=marker.positions[:, 1],
                z=marker.positions[:, 2],
            ),
            go.Scatter3d(
                name=direction.name,
                mode="lines",
                x=[0, 10, None, 10, 10, None],
                y=[0, 0, None, 0, 10, None],
                z=[0, 0, None, 0, 0, None],
            ),
            go.Cone(
                name=direction.name,
                x=[10, 8.75],
                y=[8.75, 0],
                z=[0, 0],
                u=[0, 2.5],
                v=[2.5, 0],
                w=[0, 0],
            ),
            go.Scatter3d(
                name=direction.name,
                mode="markers",
                x=[0],
                y=[0],
                z=[0],
            ),
            go.Scatter3d(
                name=vertex.name,
                mode="markers",
                x=vertex.positions[:, 0],
                y=vertex.positions[:, 1],
                z=vertex.positions[:, 2],
            ),
        ]
    )
    scene = SimpleNamespace(views=[SimpleNamespace(layers=[marker, direction, vertex])])

    attach_object_filter_metadata(
        figure,
        scene,
        revision=1,
        selection=["reco:4", "reco:9"],
        filter_family="particles",
    )

    marker_config = figure.data[0].meta["spinal_tap_feature"]
    assert marker_config == {
        "kind": "start_point",
        "prefix": "reco",
        "family": "particles",
        "records": [
            {"position": 4, "point": [1.0, 2.0, 3.0]},
            {"position": 9, "point": [4.0, 5.0, 6.0]},
        ],
    }
    shaft_records = figure.data[1].meta["spinal_tap_feature"]["records"]
    assert [record["position"] for record in shaft_records] == [4, 4, 4, 9, 9, 9]
    assert shaft_records[0]["point"] == [0.0, 0.0, 0.0]
    assert shaft_records[0]["vector"] == [1.0, 0.0, 0.0]
    tip_records = figure.data[2].meta["spinal_tap_feature"]["records"]
    assert [record["position"] for record in tip_records] == [9, 4]
    assert figure.data[3].meta is None
    assert figure.data[4].meta["spinal_tap_feature"]["records"] == [
        {"position": 5, "point": [7.0, 8.0, 9.0]}
    ]
