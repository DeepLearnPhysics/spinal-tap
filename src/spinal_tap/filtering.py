"""Helpers for filtering displayed SPINE objects."""

from __future__ import annotations

from typing import Any

__all__ = [
    "build_object_filter_options",
    "build_object_match_links",
    "attach_object_filter_metadata",
    "filter_event_objects",
    "get_object_prefixes",
]


def _compact_count(value: int) -> str:
    """Return a short human-readable count for dropdown option labels."""
    if value < 1_000:
        return str(value)
    if value < 1_000_000:
        return f"{value / 1_000:.1f}".rstrip("0").rstrip(".") + "k"
    return f"{value / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"


def attach_object_filter_metadata(
    figure: Any, scene: Any, revision: int | str, selection: list[str] | None = None
) -> None:
    """Attach compact object boundaries to combined point-cloud traces.

    Parameters
    ----------
    figure : plotly.graph_objs.Figure
        Figure containing combined reconstruction and truth point traces.
    scene : spine.vis.Scene
        Renderer-neutral scene used to construct object point buffers.
    revision : int or str
        Unique render revision used to invalidate browser-side array caches.
    selection : list[str], optional
        Object-filter selection associated with this figure render.

    Raises
    ------
    RuntimeError
        If a combined object trace cannot be identified unambiguously.
    """
    layout_metadata = dict(figure.layout.meta or {})
    layout_metadata.update(
        {
            "spinal_tap_filter_revision": revision,
            "spinal_tap_filter_selection": selection or [],
        }
    )
    figure.update_layout(meta=layout_metadata)

    for view in scene.views:
        for layer in view.layers:
            object_name = layer.metadata.get("object_name")
            if object_name is None or layer.object_offsets is None:
                continue

            prefix = object_name.split("_", 1)[0]
            matches = [
                trace
                for trace in figure.data
                if trace.name == layer.name and len(trace.x) == layer.point_count
            ]
            if layer.point_count == 0 and not matches:
                continue
            if len(matches) != 1:
                raise RuntimeError(
                    f"Expected one combined `{layer.name}` trace, "
                    f"found {len(matches)}."
                )

            object_count = len(layer.object_offsets) - 1
            keys = [key for key in (selection or []) if key.startswith(f"{prefix}:")]
            keys.sort(key=lambda key: int(key.split(":", 1)[1]))
            if len(keys) != object_count:
                keys = [f"{prefix}:{index}" for index in range(object_count)]

            trace_metadata = dict(matches[0].meta or {})
            trace_metadata["spinal_tap_filter"] = {
                "prefix": prefix,
                "family": object_name.split("_", 1)[1],
                "offsets": layer.object_offsets.tolist(),
                "keys": keys,
            }
            matches[0].meta = trace_metadata


def get_object_prefixes(mode: str) -> list[str]:
    """Return object prefixes included in a drawer mode.

    Parameters
    ----------
    mode : str
        Drawer mode, one of ``"reco"``, ``"truth"``, ``"both"`` or
        ``"all"``.

    Returns
    -------
    list[str]
        Ordered truth/reconstruction prefixes.

    Raises
    ------
    ValueError
        If ``mode`` is not supported.
    """
    if mode not in ("reco", "truth", "both", "all"):
        raise ValueError(f"Unsupported drawer mode: {mode}")

    # Match the prefix ordering used by spine.vis.Drawer
    prefixes = []
    if mode != "truth":
        prefixes.append("reco")
    if mode != "reco":
        prefixes.append("truth")

    return prefixes


def build_object_filter_options(
    data: dict[str, Any], mode: str, obj_type: str
) -> list[dict[str, str]]:
    """Build searchable dropdown options for displayed domain objects.

    Parameters
    ----------
    data : dict
        Event data containing built output-object collections.
    mode : str
        Drawer mode controlling which object prefixes are visible.
    obj_type : str
        Object family, such as ``"particles"`` or ``"interactions"``.

    Returns
    -------
    list[dict[str, str]]
        Dash dropdown options with stable event-local values.
    """
    prefixes = get_object_prefixes(mode)
    show_prefix = len(prefixes) > 1
    singular = obj_type[:-1] if obj_type.endswith("s") else obj_type
    options = []

    for prefix in prefixes:
        objects = data.get(f"{prefix}_{obj_type}", [])
        for index, obj in enumerate(objects):
            obj = objects[index]
            object_id = getattr(obj, "id", index)
            point_index = getattr(obj, "index", [])
            point_count = len(point_index) if point_index is not None else 0
            label_prefix = f"{prefix.capitalize()} " if show_prefix else ""
            options.append(
                {
                    "label": (
                        f"{label_prefix}{singular.capitalize()} {object_id} "
                        f"· {_compact_count(point_count)} pts"
                    ),
                    "value": f"{prefix}:{index}",
                }
            )

    return options


def build_object_match_links(
    data: dict[str, Any], obj_type: str
) -> dict[str, list[str]]:
    """Build symmetric one-hop reconstruction/truth visibility links.

    Match IDs stored on SPINE objects are domain IDs, while browser filters use
    collection positions. This function translates between them and combines
    match information recorded in either direction without recursively walking
    the resulting graph.

    Parameters
    ----------
    data : dict
        Event data containing reconstruction and truth object collections.
    obj_type : str
        Object family, such as ``"particles"`` or ``"interactions"``.

    Returns
    -------
    dict[str, list[str]]
        Direct opposite-prefix filter keys for every matched object key.
    """
    collections = {
        prefix: data.get(f"{prefix}_{obj_type}", []) for prefix in ("reco", "truth")
    }
    positions = {
        prefix: {
            int(getattr(obj, "id", index)): index for index, obj in enumerate(objects)
        }
        for prefix, objects in collections.items()
    }
    links: dict[str, set[str]] = {}

    for prefix, target_prefix in (("reco", "truth"), ("truth", "reco")):
        for index, obj in enumerate(collections[prefix]):
            source_key = f"{prefix}:{index}"
            for match_id in getattr(obj, "match_ids", []):
                target_index = positions[target_prefix].get(int(match_id))
                if target_index is None:
                    continue
                target_key = f"{target_prefix}:{target_index}"
                links.setdefault(source_key, set()).add(target_key)
                links.setdefault(target_key, set()).add(source_key)

    return {key: sorted(values) for key, values in links.items()}


def filter_event_objects(
    data: dict[str, Any],
    mode: str,
    obj_type: str,
    selection: list[str] | None,
) -> tuple[dict[str, Any], int, int]:
    """Return event data containing only selected object positions.

    An empty selection means that no objects remain visible. The input event
    dictionary and its object collections are never modified.

    Parameters
    ----------
    data : dict
        Event data containing built output-object collections.
    mode : str
        Drawer mode controlling which object prefixes are visible.
    obj_type : str
        Object family to filter.
    selection : list[str], optional
        Event-local identifiers to show, as produced by
        :func:`build_object_filter_options`.

    Returns
    -------
    tuple[dict, int, int]
        Filtered event data, visible object count and total object count.
    """
    prefixes = get_object_prefixes(mode)
    selected = set(selection or [])
    filtered = dict(data)
    visible_count, total_count = 0, 0

    # Copy filtered object collections while all backing arrays stay shared
    for prefix in prefixes:
        key = f"{prefix}_{obj_type}"
        objects = data.get(key, [])
        total_count += len(objects)
        visible = [
            obj for index, obj in enumerate(objects) if f"{prefix}:{index}" in selected
        ]
        filtered[key] = visible
        visible_count += len(visible)

    return filtered, visible_count, total_count
