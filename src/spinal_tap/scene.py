"""Binary transport and bounded storage for renderer-neutral SPINE scenes."""

from __future__ import annotations

import json
import os
import struct
import uuid
from collections import OrderedDict
from threading import RLock
from typing import Any

import numpy as np

from spine.vis import (
    BoxLayer,
    LineLayer,
    MarkerLayer,
    MeshLayer,
    PointLayer,
    VectorLayer,
)

SCENE_CACHE_SIZE = int(os.getenv("SPINAL_TAP_SCENE_CACHE_SIZE", "8"))


def _json_value(value: Any) -> Any:
    """Convert common NumPy and Plotly-style values to JSON data."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return str(value)


class SceneEncoder:
    """Encode neutral scene metadata and arrays into one binary payload."""

    def __init__(self) -> None:
        """Initialize an empty raw-buffer collection."""
        self.buffers: list[bytes] = []
        self.offset = 0

    def add_array(self, value: Any, dtype: str) -> dict[str, Any] | None:
        """Append one typed array and return its binary descriptor."""
        if value is None or np.isscalar(value) or isinstance(value, str):
            return None
        array = np.ascontiguousarray(value, dtype=np.dtype(dtype).newbyteorder("<"))
        raw = array.tobytes()
        descriptor = {
            "offset": self.offset,
            "length": len(raw),
            "dtype": dtype,
            "shape": list(array.shape),
        }
        self.buffers.append(raw)
        self.offset += len(raw)
        return descriptor

    @staticmethod
    def encode_hovertext(layer: Any) -> Any:
        """Return compact hover labels without repeating text for every point."""
        hovertext = layer.hovertext
        if hovertext is None or isinstance(hovertext, str):
            return _json_value(hovertext)

        labels = np.asarray(hovertext, dtype=object)
        offsets = getattr(layer, "object_offsets", None)
        if offsets is not None and len(labels) == getattr(layer, "point_count", -1):
            labels = np.asarray(
                [
                    labels[start] if stop > start else ""
                    for start, stop in zip(offsets[:-1], offsets[1:])
                ],
                dtype=object,
            )
        return _json_value(labels)

    def encode_layer(self, layer: Any) -> dict[str, Any]:
        """Encode one supported neutral layer."""
        common = {
            "name": layer.name,
            "metadata": _json_value(layer.metadata),
            "hovertext": self.encode_hovertext(layer),
        }
        if isinstance(layer, PointLayer):
            result = {
                **common,
                "type": "marker" if isinstance(layer, MarkerLayer) else "point",
                "positions": self.add_array(layer.positions, "float32"),
                "values": self.add_array(layer.values, "float32"),
                "shared_value": (
                    _json_value(layer.values)
                    if layer.values is None or np.isscalar(layer.values)
                    else None
                ),
                "object_ids": self.add_array(layer.object_ids, "int32"),
                "object_offsets": self.add_array(layer.object_offsets, "int32"),
                "attributes": {
                    name: self.add_array(values, "float32")
                    for name, values in layer.attributes.items()
                    if np.asarray(values).dtype.kind in "biuf"
                },
                "style": _json_value(vars(layer.style)),
            }
            if isinstance(layer, MarkerLayer):
                result["symbol"] = layer.symbol
            return result
        if isinstance(layer, LineLayer):
            return {
                **common,
                "type": "line",
                "segments": self.add_array(layer.segments, "float32"),
                "values": self.add_array(layer.values, "float32"),
                "shared_value": (
                    _json_value(layer.values)
                    if layer.values is None or np.isscalar(layer.values)
                    else None
                ),
                "object_ids": self.add_array(layer.object_ids, "int32"),
                "style": _json_value(vars(layer.style)),
            }
        if isinstance(layer, VectorLayer):
            return {
                **common,
                "type": "vector",
                "origins": self.add_array(layer.origins, "float32"),
                "vectors": self.add_array(layer.vectors, "float32"),
                "values": self.add_array(layer.values, "float32"),
                "shared_value": (
                    _json_value(layer.values)
                    if layer.values is None or np.isscalar(layer.values)
                    else None
                ),
                "object_ids": self.add_array(layer.object_ids, "int32"),
                "scale": layer.scale,
                "head_size": layer.head_size,
                "style": _json_value(vars(layer.style)),
            }
        if isinstance(layer, MeshLayer):
            return {
                **common,
                "type": "mesh",
                "vertices": self.add_array(layer.vertices, "float32"),
                "faces": self.add_array(layer.faces, "int32"),
                "values": self.add_array(layer.values, "float32"),
                "shared_value": (
                    _json_value(layer.values)
                    if layer.values is None or np.isscalar(layer.values)
                    else None
                ),
                "style": _json_value(vars(layer.style)),
            }
        if isinstance(layer, BoxLayer):
            return {
                **common,
                "type": "box",
                "bounds": self.add_array(layer.bounds, "float32"),
                "values": self.add_array(layer.values, "float32"),
                "object_ids": self.add_array(layer.object_ids, "int32"),
                "draw_faces": layer.draw_faces,
                "line_style": _json_value(vars(layer.line_style)),
                "mesh_style": _json_value(vars(layer.mesh_style)),
            }
        raise TypeError(f"Unsupported scene layer: {type(layer).__name__}.")

    def encode(self, scene: Any) -> bytes:
        """Encode a complete scene as header length, JSON header and arrays."""
        # Allow one encoder instance to be reused without leaking old buffers
        self.buffers.clear()
        self.offset = 0
        header = {
            "version": 1,
            "metadata": _json_value(scene.metadata),
            "views": [
                {
                    "name": view.name,
                    "metadata": _json_value(view.metadata),
                    "layers": [self.encode_layer(layer) for layer in view.layers],
                }
                for view in scene.views
            ],
        }
        header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
        padding = b"\0" * (-(4 + len(header_bytes)) % 4)
        return (
            struct.pack("<I", len(header_bytes))
            + header_bytes
            + padding
            + b"".join(self.buffers)
        )


class SceneStore:
    """Bounded process-local store of immutable binary scene payloads."""

    def __init__(self, max_size: int = SCENE_CACHE_SIZE) -> None:
        """Initialize the store with an LRU entry bound."""
        if max_size < 1:
            raise ValueError("Scene cache size must be at least one.")
        self.max_size = max_size
        self._items: OrderedDict[str, bytes] = OrderedDict()
        self._lock = RLock()

    def put(self, scene: Any) -> str:
        """Encode a scene and return its opaque lookup token."""
        token = uuid.uuid4().hex
        payload = SceneEncoder().encode(scene)
        with self._lock:
            self._items[token] = payload
            while len(self._items) > self.max_size:
                self._items.popitem(last=False)
        return token

    def get(self, token: str) -> bytes | None:
        """Return and refresh one stored payload."""
        with self._lock:
            payload = self._items.get(token)
            if payload is not None:
                self._items.move_to_end(token)
            return payload

    def clear(self) -> None:
        """Drop all stored payloads."""
        with self._lock:
            self._items.clear()


scene_store = SceneStore()
