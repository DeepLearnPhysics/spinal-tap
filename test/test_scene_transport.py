"""Tests for compact renderer-neutral scene transport."""

import json
import struct
from types import SimpleNamespace

import numpy as np
import pytest
from flask import Flask

from spinal_tap.app import register_scene_routes
from spinal_tap.scene import SceneEncoder, SceneStore, _json_value, scene_store
from spine.vis import (
    BoxLayer,
    LineLayer,
    MarkerLayer,
    MeshLayer,
    PointLayer,
    Scene,
    SceneView,
    VectorLayer,
)


def decode_header(payload):
    """Decode the JSON header from a compact scene payload."""
    length = struct.unpack_from("<I", payload)[0]
    return json.loads(payload[4 : 4 + length])


def complete_scene():
    """Build a scene containing every portable primitive."""
    points = PointLayer(
        np.arange(18, dtype=np.float32).reshape(6, 3),
        name="objects",
        values=np.arange(6, dtype=np.float32),
        hovertext=np.asarray(["first"] * 3 + ["second"] * 3),
        object_ids=[10, 10, 10, 20, 20, 20],
        object_offsets=[0, 3, 6],
        attributes={"pid": np.asarray([1, 1, 1, 2, 2, 2])},
    )
    layers = [
        points,
        MarkerLayer(np.zeros((1, 3)), values="green", hovertext=["vertex"]),
        LineLayer(np.zeros((1, 2, 3)), values=2.0, hovertext="line"),
        VectorLayer(np.zeros((1, 3)), np.ones((1, 3)), values=[4], object_ids=[0]),
        MeshLayer(
            np.asarray([[0, 0, 0], [1, 0, 0], [0, 1, 0]]),
            [[0, 1, 2]],
            values=[0, 1, 2],
        ),
        BoxLayer(np.asarray([[[0, 0, 0], [1, 1, 1]]]), object_ids=[0]),
    ]
    return Scene([SceneView("event", layers)], metadata={"numpy": np.int32(3)})


def test_scene_encoder_describes_all_primitives_and_arrays():
    """The payload should preserve all geometry and compact object metadata."""
    encoder = SceneEncoder()
    payload = encoder.encode(complete_scene())
    header = decode_header(payload)
    layers = header["views"][0]["layers"]

    assert header["version"] == 1
    assert header["metadata"] == {"numpy": 3}
    assert [layer["type"] for layer in layers] == [
        "point",
        "marker",
        "line",
        "vector",
        "mesh",
        "box",
    ]
    assert layers[0]["hovertext"] == ["first", "second"]
    assert layers[0]["attributes"]["pid"]["dtype"] == "float32"
    assert layers[1]["symbol"] == "circle"
    assert layers[3]["values"]["dtype"] == "float32"
    assert len(payload) % 4 == 0

    # Reusing an encoder must produce the same self-contained payload
    assert encoder.encode(complete_scene()) == payload


def test_scene_store_is_bounded_and_refreshes_entries():
    """Scene payloads should be retained in bounded least-recently-used order."""
    with pytest.raises(ValueError, match="at least one"):
        SceneStore(0)

    store = SceneStore(2)
    first = store.put(complete_scene())
    second = store.put(complete_scene())
    assert store.get(first) is not None
    third = store.put(complete_scene())

    assert store.get(first) is not None
    assert store.get(second) is None
    assert store.get(third) is not None
    store.clear()
    assert store.get(first) is None


def test_scene_route_serves_payload_and_missing_tokens():
    """The binary endpoint should serve private cached payloads by opaque token."""
    server = Flask(__name__)
    register_scene_routes(server)
    token = scene_store.put(complete_scene())
    client = server.test_client()

    response = client.get(f"/scene/{token}.bin")

    assert response.status_code == 200
    assert response.mimetype == "application/octet-stream"
    assert response.headers["Cache-Control"] == "private, max-age=300"
    assert decode_header(response.data)["views"][0]["name"] == "event"
    assert client.get("/scene/does-not-exist.bin").status_code == 404


def test_scene_json_conversion_and_unsupported_layers():
    """Nested mappings and unsupported primitives should have deterministic behavior."""
    assert _json_value((np.int32(2), {3: np.asarray([4, 5])})) == [
        2,
        {"3": [4, 5]},
    ]
    assert _json_value(object()).startswith("<object object")
    encoder = SceneEncoder()
    with pytest.raises(TypeError, match="Unsupported scene layer"):
        encoder.encode_layer(
            SimpleNamespace(name="unknown", metadata={}, hovertext=None)
        )
