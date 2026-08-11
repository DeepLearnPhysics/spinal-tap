"""Helpers for filtering displayed SPINE objects."""

from __future__ import annotations

from typing import Any

__all__ = [
    "build_object_filter_options",
    "filter_event_objects",
    "get_object_prefixes",
]


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

    # Preserve collection order so option indices match filter identifiers
    for prefix in prefixes:
        objects = data.get(f"{prefix}_{obj_type}", [])
        for index, obj in enumerate(objects):
            object_id = getattr(obj, "id", index)
            point_index = getattr(obj, "index", [])
            point_count = len(point_index) if point_index is not None else 0
            label_prefix = f"{prefix.capitalize()} " if show_prefix else ""
            options.append(
                {
                    "label": (
                        f"{label_prefix}{singular.capitalize()} {object_id} "
                        f"· {point_count:,} pts"
                    ),
                    "value": f"{prefix}:{index}",
                }
            )

    return options


def filter_event_objects(
    data: dict[str, Any],
    mode: str,
    obj_type: str,
    selection: list[str] | None,
) -> tuple[dict[str, Any], int, int]:
    """Return event data with selected object positions hidden.

    An empty selection means that all objects remain visible. The input event
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
        Event-local identifiers to hide, as produced by
        :func:`build_object_filter_options`.

    Returns
    -------
    tuple[dict, int, int]
        Filtered event data, visible object count and total object count.
    """
    prefixes = get_object_prefixes(mode)
    hidden = set(selection or [])
    filtered = dict(data)
    visible_count, total_count = 0, 0

    # Copy filtered object collections while all backing arrays stay shared
    for prefix in prefixes:
        key = f"{prefix}_{obj_type}"
        objects = data.get(key, [])
        total_count += len(objects)
        if not hidden:
            visible = list(objects)
        else:
            visible = [
                obj
                for index, obj in enumerate(objects)
                if f"{prefix}:{index}" not in hidden
            ]
        filtered[key] = visible
        visible_count += len(visible)

    return filtered, visible_count, total_count
