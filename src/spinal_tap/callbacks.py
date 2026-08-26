"""Defines the callbacks of the Spinal Tap application."""

import json
import uuid
from dataclasses import replace
from pathlib import Path

import numpy as np
from dash import ctx, dcc, html, no_update
from dash.dependencies import Input, Output, State

import spine.data.out
from spine.geo import GeoManager
from spine.vis import Drawer, colorable_attributes, object_color_kind

from .filtering import (
    attach_object_filter_metadata,
    build_object_filter_options,
    build_object_match_links,
    filter_event_objects,
)
from .inspection import inspect_object, object_collection_key
from .scene import scene_store
from .source import read_file_manifest
from .utils import (
    canonicalize_data_path,
    classify_source,
    get_reader_products,
    initialize_reader,
    load_data,
    resolve_source_path,
)

GRAPH_CONFIG = {
    "responsive": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": ["toImage", "resetCameraDefault3d"],
    "toImageButtonOptions": {
        "format": "png",
        "filename": "spinal_tap_event_display",
        "scale": 2,
    },
}

FILTER_DEPENDENT_DRAW_MODES = {
    "flash",
    "flash_match_only",
    "crt",
    "crt_match_only",
}

PLOTLY_FILTER_DEPENDENT_DRAW_MODES = FILTER_DEPENDENT_DRAW_MODES | {
    "point",
    "direction",
    "vertex",
}

SOURCE_OPEN_TRIGGERS = {
    "button-load",
    "input-file-path",
    "store-source-request",
}
EVENT_NAVIGATION_TRIGGERS = {
    "button-go",
    "button-previous",
    "button-next",
    "input-entry",
    "input-run",
    "input-subrun",
    "input-event",
}
NAVIGATION_TRIGGERS = SOURCE_OPEN_TRIGGERS | EVENT_NAVIGATION_TRIGGERS
FILTER_RESET_TRIGGERS = NAVIGATION_TRIGGERS | {
    "radio-object-mode",
    "radio-run-mode",
    "store-share-pending",
}
AUTO_REFRESH_TRIGGERS = {
    "checklist-draw-mode-1",
    "checklist-draw-mode-2",
    "dropdown-geo",
    "dropdown-geo-tag",
    "dropdown-colorscale",
    "input-color-max",
    "input-color-min",
    "input-point-opacity",
    "input-point-size",
    "input-visible-max",
    "input-visible-min",
    "radio-color-domain",
    "radio-color-transform",
    "radio-visible-range",
    "radio-crt-mode",
    "radio-flash-mode",
    "radio-object-mode",
    "radio-run-mode",
    "radio-truth-point-mode",
    "renderer-toggle",
    "store-dropdown-commit",
    "store-appearance-render-request",
}

TRUTH_POINT_MODES = {
    "points": {
        "label": "Label",
        "point_key": "points_label",
        "index_key": "index",
        "dep_mode": "depositions",
        "pointwise": {"depositions", "depositions_q", "sources"},
    },
    "points_adapt": {
        "label": "Adapted",
        "point_key": "points",
        "index_key": "index_adapt",
        "dep_mode": "depositions_adapt_q",
        "pointwise": {
            "depositions_adapt",
            "depositions_adapt_q",
            "sources_adapt",
        },
    },
    "points_g4": {
        "label": "Geant4",
        "point_key": "points_g4",
        "index_key": "index_g4",
        "dep_mode": "depositions_g4",
        "pointwise": {"depositions_g4"},
    },
}
TRUTH_POINTWISE_ATTRIBUTES = set().union(
    *(config["pointwise"] for config in TRUTH_POINT_MODES.values())
)

RUN_MODE_LABELS = {
    "reco": "Reco",
    "truth": "Truth",
    "both": "Both",
}
OBJECT_MODE_LABELS = {
    "fragments": "Fragments",
    "particles": "Particles",
    "interactions": "Interactions",
}
DRAW_MODE_OPTIONS = [
    ("End points", "point"),
    ("Directions", "direction"),
    ("Vertices", "vertex"),
    ("Raw", "raw"),
    ("Flashes", "flash"),
    ("Only matched flashes", "flash_match_only"),
    ("CRT hits", "crt"),
    ("Only matched CRT hits", "crt_match_only"),
]
CORE_DRAW_MODES = {"point", "direction", "vertex", "raw"}

SHARED_VIEW_VERSION = 1


def validate_view_state(state):
    """Validate a shared-view state document.

    Parameters
    ----------
    state : object
        Decoded shared-view JSON value.

    Returns
    -------
    dict
        Validated view state with a unique restore revision.

    Raises
    ------
    ValueError
        If the document is malformed or uses an unsupported schema.
    """
    if not isinstance(state, dict):
        raise ValueError("The view state must be a JSON object.")
    if state.get("version") != SHARED_VIEW_VERSION:
        raise ValueError(
            "Unsupported view-state version "
            f"{state.get('version')!r}; expected {SHARED_VIEW_VERSION}."
        )
    if not isinstance(state.get("file"), str) or not state["file"]:
        raise ValueError("The view state does not contain a file path.")
    try:
        entry = int(state.get("entry"))
    except (TypeError, ValueError) as error:
        raise ValueError("The view state contains an invalid entry number.") from error
    if entry < 0:
        raise ValueError("The view state contains an invalid entry number.")

    display = state.get("display") or {}
    attributes = state.get("attributes") or {}
    objects = state.get("objects") or {}
    if not all(isinstance(value, dict) for value in (display, attributes, objects)):
        raise ValueError("The view-state control groups are malformed.")
    for value in (
        display.get("overlays"),
        display.get("view"),
        attributes.get("hover"),
    ):
        if value is not None and not isinstance(value, list):
            raise ValueError("A view-state option list is malformed.")
    for value in (objects.get("reco"), objects.get("truth")):
        if value is not None and value != "all" and not isinstance(value, list):
            raise ValueError("A view-state object selection is malformed.")
    truth_points = display.get("truth_points")
    if truth_points is not None and truth_points not in TRUTH_POINT_MODES:
        raise ValueError("The view state contains an invalid truth point source.")
    axes = display.get("axes")
    if axes is not None and not isinstance(axes, bool):
        raise ValueError("The view state contains an invalid axes setting.")
    colorscale = attributes.get("colorscale")
    if colorscale is not None and not isinstance(colorscale, str):
        raise ValueError("The view state contains an invalid continuous colorscale.")
    appearance = attributes.get("appearance")
    if appearance is not None and not isinstance(appearance, dict):
        raise ValueError("The view state contains invalid appearance settings.")
    if appearance:
        if appearance.get("transform", "linear") not in {"linear", "log"}:
            raise ValueError("The view state contains an invalid color transform.")
        if appearance.get("domain_mode", "auto") not in {"auto", "manual"}:
            raise ValueError("The view state contains an invalid color domain.")
        if appearance.get("range_mode", "all") not in {"all", "range"}:
            raise ValueError("The view state contains an invalid visible range.")
        for name in (
            "point_size",
            "opacity",
            "color_min",
            "color_max",
            "visible_min",
            "visible_max",
        ):
            value = appearance.get(name)
            if value is not None and not isinstance(value, (int, float)):
                raise ValueError(f"The view state contains an invalid `{name}` value.")
        point_size = appearance.get("point_size", 1.0)
        opacity = appearance.get("opacity", 1.0)
        if not 0.5 <= point_size <= 3.0:
            raise ValueError("The view state contains an invalid `point_size` value.")
        if not 0.1 <= opacity <= 1.0:
            raise ValueError("The view state contains an invalid `opacity` value.")

    state = dict(state)
    state["entry"] = entry
    state["restore_nonce"] = uuid.uuid4().hex
    return state


def load_view_state(file_path):
    """Read and validate a shared-view JSON file from a server path.

    Parameters
    ----------
    file_path : str
        Path to the shared-view JSON document. Equivalent S3DF mount aliases
        are resolved in the same way as HDF5 input paths.

    Returns
    -------
    dict
        Validated view state with a unique restore revision.

    Raises
    ------
    OSError
        If the document cannot be read.
    ValueError
        If the document is not valid UTF-8 JSON or has an invalid schema.
    """
    resolved_path = resolve_source_path(file_path)
    try:
        with open(resolved_path, encoding="utf-8-sig") as view_file:
            state = json.load(view_file)
    except UnicodeDecodeError as error:
        raise ValueError("The selected file is not valid UTF-8 JSON.") from error
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON at line {error.lineno}, column {error.colno}."
        ) from error

    return validate_view_state(state)


def validate_file_access(file_path):
    """Validate that the user can access the requested file path.

    Parameters
    ----------
    file_path : str
        Path to the file to validate

    Returns
    -------
    tuple
        (is_valid, error_message) where is_valid is bool and
        error_message is str or None
    """
    # Import here to avoid circular dependency
    import os

    from .app import EXPERIMENT_PATHS, REQUIRE_AUTH, SHARED_FOLDERS, get_experiment
    from .cache import ALLOW_URLS, cache_manager

    if not REQUIRE_AUTH:
        return True, None

    experiment = get_experiment()
    if not experiment:
        return False, "Not authenticated. Please log in."

    if file_path.strip().startswith(("http://", "https://")):
        if ALLOW_URLS:
            return True, None
        return False, "URL sources are disabled on this deployment."

    if cache_manager.owns_path(file_path):
        return True, None

    # Treat the host and container views of S3DF neutrino data identically
    file_path = canonicalize_data_path(file_path)

    # Check if path is in a shared folder
    for shared in SHARED_FOLDERS:
        shared = canonicalize_data_path(shared)
        if file_path == shared or file_path.startswith(shared + os.sep):
            return True, None

    # Check if path is within any of the allowed experiment directories
    allowed_paths = EXPERIMENT_PATHS.get(experiment, [])
    for allowed_path in allowed_paths:
        allowed_path = canonicalize_data_path(allowed_path)
        if file_path == allowed_path or file_path.startswith(allowed_path + os.sep):
            return True, None

    # Build error message
    paths_str = ", ".join(allowed_paths) if allowed_paths else "no paths"
    shared_info = (
        f" or shared folders: {', '.join(SHARED_FOLDERS)}" if SHARED_FOLDERS else ""
    )
    return (
        False,
        f"Access denied. {experiment.upper()} users can only access "
        f"files in {paths_str}{shared_info}",
    )


def validate_manifest_access(file_path):
    """Validate every server-side source referenced by a file manifest."""
    root = Path(file_path).parent
    for record in read_file_manifest(file_path):
        if record.startswith(("http://", "https://")):
            candidate = record
        else:
            path = Path(record).expanduser()
            candidate = str(path if path.is_absolute() else root / path)
        is_valid, error = validate_file_access(candidate)
        if not is_valid:
            return False, f"Manifest entry {record!r} is not accessible: {error}"
    return True, None


def parse_optional_int(value):
    """Parse an optional integer input value."""
    if value is None or value == "":
        return None
    return int(value)


def format_entry_label(entry: int, total: int) -> str:
    """Format the current and maximum zero-based file entry indexes."""
    return f"Entry {entry}/{total - 1}"


def navigation_file_path(file_path, source_mode, trigger, loaded_event):
    """Resolve the data source used by an event-navigation action.

    Source controls are draft editors applied by Open. Navigation must always
    continue through the HDF5 source of the event currently displayed.
    """
    navigation = trigger in EVENT_NAVIGATION_TRIGGERS
    if navigation and loaded_event:
        return loaded_event["file_path"]

    return file_path


def display_capabilities(data, truth_point_mode="points"):
    """Return the object and overlay capabilities present in an event."""
    objects = {
        prefix: {obj for obj in OBJECT_MODE_LABELS if f"{prefix}_{obj}" in data}
        for prefix in ("reco", "truth")
    }
    truth_config = TRUTH_POINT_MODES[truth_point_mode]
    truth_dep_key = {
        "depositions": "depositions_label",
        "depositions_adapt_q": "depositions",
        "depositions_g4": "depositions_g4",
    }[truth_config["dep_mode"]]
    return {
        "objects": objects,
        "raw": {
            "reco": "points" in data and "depositions" in data,
            "truth": (truth_config["point_key"] in data and truth_dep_key in data),
        },
        "flashes": "flashes" in data,
        "crthits": "crthits" in data,
    }


def display_control_state(data, mode, obj, draw_modes=None, truth_point_mode="points"):
    """Resolve valid display selections and disabled control options."""
    capabilities = display_capabilities(data, truth_point_mode)
    objects = capabilities["objects"]

    def modes_for(object_type):
        modes = []
        if object_type in objects["reco"]:
            modes.append("reco")
        if object_type in objects["truth"]:
            modes.append("truth")
        if object_type in objects["reco"] and object_type in objects["truth"]:
            modes.append("both")
        return modes

    # Preserve the selected object when another run mode can display it. If
    # that object is absent altogether, prefer particles before other families.
    if not modes_for(obj):
        obj = next(
            (
                candidate
                for candidate in ("particles", "interactions", "fragments")
                if modes_for(candidate)
            ),
            obj,
        )

    available_modes = modes_for(obj)
    if mode not in available_modes and available_modes:
        mode = "truth" if available_modes == ["truth"] else available_modes[0]

    def object_enabled(object_type):
        if mode == "both":
            return object_type in objects["reco"] and object_type in objects["truth"]
        return object_type in objects.get(mode, set())

    object_options = [
        {
            "label": label,
            "value": value,
            "disabled": not object_enabled(value),
        }
        for value, label in OBJECT_MODE_LABELS.items()
    ]

    available_modes = set(modes_for(obj))
    run_options = [
        {
            "label": label,
            "value": value,
            "disabled": value not in available_modes,
        }
        for value, label in RUN_MODE_LABELS.items()
    ]

    particle_like = obj in {"fragments", "particles"}
    if mode == "both":
        has_interactions = all(
            "interactions" in objects[prefix] for prefix in ("reco", "truth")
        )
    else:
        has_interactions = "interactions" in objects.get(mode, set())
    raw_modes = capabilities["raw"]
    has_raw = (
        raw_modes["reco"] and raw_modes["truth"]
        if mode == "both"
        else raw_modes.get(mode, False)
    )
    disabled_draw_modes = {
        "point": not particle_like,
        "direction": not particle_like,
        "vertex": not has_interactions,
        "raw": not has_raw,
        "flash": not (has_interactions and capabilities["flashes"]),
        "flash_match_only": not (has_interactions and capabilities["flashes"]),
        "crt": not capabilities["crthits"],
        "crt_match_only": not capabilities["crthits"],
    }
    draw_options = [
        {
            "label": label,
            "value": value,
            "disabled": disabled_draw_modes[value],
        }
        for label, value in DRAW_MODE_OPTIONS
    ]
    draw_modes = [
        value
        for value in (draw_modes or [])
        if not disabled_draw_modes.get(value, False)
    ]

    return run_options, mode, object_options, obj, draw_options, draw_modes


def truth_point_control_state(data, mode, obj, selected="points"):
    """Resolve truth point-source availability for the loaded event."""
    truth_objects = data.get(f"truth_{obj}", [])
    options = []
    available = []
    for value, config in TRUTH_POINT_MODES.items():
        has_points = config["point_key"] in data
        has_indexes = not truth_objects or any(
            len(getattr(item, config["index_key"], [])) for item in truth_objects
        )
        enabled = has_points and has_indexes
        options.append(
            {
                "label": config["label"],
                "value": value,
                "disabled": not enabled,
            }
        )
        if enabled:
            available.append(value)

    if selected not in available:
        selected = (
            "points" if "points" in available else next(iter(available), "points")
        )
    style = {"display": "block" if mode != "reco" else "none"}
    return options, selected, style


def compose_draw_modes(core_modes, flash_mode="off", crt_mode="off"):
    """Combine the visible overlay controls into SPINE draw-mode values."""
    modes = [mode for mode in (core_modes or []) if mode in CORE_DRAW_MODES]
    for prefix, selection in (("flash", flash_mode), ("crt", crt_mode)):
        if selection in {"all", "matched"}:
            modes.append(prefix)
        if selection == "matched":
            modes.append(f"{prefix}_match_only")
    return modes


def overlay_control_state(options, values):
    """Split SPINE draw modes into core, flash and CRT control states."""
    option_map = {option["value"]: option for option in options}
    values = set(values or [])
    core_options = [option for option in options if option["value"] in CORE_DRAW_MODES]
    core_values = [
        option["value"]
        for option in core_options
        if option["value"] in values and not option["disabled"]
    ]

    def mode_state(prefix):
        base = option_map[prefix]
        matched = option_map[f"{prefix}_match_only"]
        choices = [
            {"label": "Off", "value": "off", "disabled": False},
            {"label": "On", "value": "all", "disabled": base["disabled"]},
            {
                "label": "Matched",
                "value": "matched",
                "disabled": matched["disabled"],
            },
        ]
        if f"{prefix}_match_only" in values and not matched["disabled"]:
            value = "matched"
        elif prefix in values and not base["disabled"]:
            value = "all"
        else:
            value = "off"
        return choices, value

    flash_options, flash_value = mode_state("flash")
    crt_options, crt_value = mode_state("crt")
    return (
        core_options,
        core_values,
        flash_options,
        flash_value,
        crt_options,
        crt_value,
    )


def object_attributes(mode, obj, truth_point_mode="points"):
    """Return attributes available for the requested object display.

    Parameters
    ----------
    mode : str
        Drawer run mode ('reco', 'truth' or 'both').
    obj : str
        Objects to be drawn ('fragments', 'particles' or 'interactions').

    Returns
    -------
    numpy.ndarray
        Sorted union of attributes available on the requested object classes.
    """
    attrs = set()
    reco_attrs = set()
    truth_attrs = set()
    if mode != "truth":
        cls_name = f"Reco{obj[:-1].capitalize()}"
        cls_obj = getattr(spine.data.out, cls_name)()
        reco_attrs.update(
            attr for attr in cls_obj.attr_names() if not attr.startswith("points")
        )
        attrs.update(reco_attrs)

    if mode != "reco":
        cls_name = f"Truth{obj[:-1].capitalize()}"
        cls_obj = getattr(spine.data.out, cls_name)()
        truth_attrs.update(
            attr for attr in cls_obj.attr_names() if not attr.startswith("points")
        )
        allowed = TRUTH_POINT_MODES[truth_point_mode]["pointwise"]
        truth_attrs.difference_update(TRUTH_POINTWISE_ATTRIBUTES - allowed)
        attrs.update(truth_attrs)

    # A shared hover/color field must exist on both sides. Reco always uses
    # its regular point cloud, so non-label truth pointwise fields have no
    # meaningful counterpart in a combined scene.
    if mode == "both":
        pointwise = TRUTH_POINTWISE_ATTRIBUTES & attrs
        attrs.difference_update(pointwise - (reco_attrs & truth_attrs))

    return np.sort(list(attrs))


def colorable_object_attributes(mode, obj, truth_point_mode="points"):
    """Return the schema-supported color attributes for an object display."""
    attrs = []
    if mode != "truth":
        cls_name = f"Reco{obj[:-1].capitalize()}"
        attrs.append(set(colorable_attributes(getattr(spine.data.out, cls_name))))
    if mode != "reco":
        cls_name = f"Truth{obj[:-1].capitalize()}"
        attrs.append(set(colorable_attributes(getattr(spine.data.out, cls_name))))
    colorable = set.intersection(*attrs) if attrs else set()
    if mode != "reco":
        allowed = TRUTH_POINT_MODES[truth_point_mode]["pointwise"]
        colorable.difference_update(TRUTH_POINTWISE_ATTRIBUTES - allowed)
    return colorable


def continuous_color_attribute(mode, obj, attr, truth_point_mode="points"):
    """Check whether an attribute is continuous for every visible object type."""
    if not attr:
        return False
    kinds = []
    if mode != "truth":
        cls_name = f"Reco{obj[:-1].capitalize()}"
        kinds.append(object_color_kind(getattr(spine.data.out, cls_name), attr))
    if mode != "reco":
        cls_name = f"Truth{obj[:-1].capitalize()}"
        kinds.append(object_color_kind(getattr(spine.data.out, cls_name), attr))
    return bool(kinds) and all(kind == "continuous" for kind in kinds)


def apply_continuous_colorscale(scene, colorscale):
    """Replace named continuous scales while preserving categorical palettes."""
    layer_names = set()
    for view in getattr(scene, "views", []):
        for layer in view.layers:
            style = getattr(layer, "style", None)
            if style is not None and isinstance(style.colorscale, str):
                layer_names.add(layer.name)
                layer.style = replace(style, colorscale=colorscale)

            attribute_styles = layer.metadata.get("attribute_styles")
            if attribute_styles:
                for config in attribute_styles.values():
                    if isinstance(config.get("colorscale"), str):
                        config["colorscale"] = colorscale
    return layer_names


def apply_plotly_colorscale(figure, colorscale, layer_names):
    """Replace named continuous trace scales without touching discrete colors."""
    for trace in figure.data:
        if trace.name not in layer_names:
            continue
        marker = getattr(trace, "marker", None)
        if marker is not None and marker.colorscale is not None:
            marker.colorscale = colorscale
        line = getattr(trace, "line", None)
        if line is not None and line.colorscale is not None:
            line.colorscale = colorscale
        if getattr(trace, "colorscale", None) is not None:
            trace.colorscale = colorscale


def apply_plotly_appearance(figure, layer_names, appearance):
    """Apply point styling and continuous scalar bounds to a Plotly figure."""
    size_scale = float(appearance.get("point_size") or 1.0)
    opacity_scale = float(appearance.get("opacity") or 1.0)
    transform = appearance.get("transform") or "linear"
    domain_mode = appearance.get("domain_mode") or "auto"
    range_mode = appearance.get("range_mode") or "all"
    histogram_values = []

    for trace in figure.data:
        marker = getattr(trace, "marker", None)
        if marker is None or "markers" not in (getattr(trace, "mode", "") or ""):
            continue
        metadata = getattr(trace, "meta", None)
        kind = metadata.get("kind") if isinstance(metadata, dict) else None
        if kind in {"start_point", "end_point", "vertex"}:
            continue

        marker.size = (marker.size or 2.0) * size_scale
        marker.opacity = (
            marker.opacity if marker.opacity is not None else 1.0
        ) * opacity_scale
        if trace.name not in layer_names or marker.color is None:
            continue

        source_cmin = marker.cmin
        source_cmax = marker.cmax
        raw = np.asarray(marker.color)
        if raw.ndim != 1 or raw.dtype.kind not in "biuf":
            continue
        raw = raw.astype(float, copy=False)
        mask = np.isfinite(raw)
        histogram = raw[mask]
        if transform == "log":
            histogram = histogram[histogram > 0]
            histogram = np.log10(histogram)
        if len(histogram):
            histogram_values.append(histogram)
        if range_mode == "range":
            lower = appearance.get("visible_min")
            upper = appearance.get("visible_max")
            if lower is not None:
                mask &= raw >= float(lower)
            if upper is not None:
                mask &= raw <= float(upper)

        values = raw.copy()
        if transform == "log":
            mask &= raw > 0
            values = np.where(raw > 0, np.log10(raw), np.nan)

        if not np.all(mask):
            for name in ("x", "y", "z", "text", "customdata", "ids"):
                value = getattr(trace, name, None)
                if value is None or isinstance(value, str):
                    continue
                array = np.asarray(value)
                if array.ndim and len(array) == len(mask):
                    setattr(trace, name, array[mask])
            values = values[mask]
        marker.color = values

        if domain_mode == "manual":
            lower = appearance.get("color_min")
            upper = appearance.get("color_max")
            if transform == "log":
                lower = np.log10(lower) if lower is not None and lower > 0 else None
                upper = np.log10(upper) if upper is not None and upper > 0 else None
            marker.cmin = lower
            marker.cmax = upper
        else:
            finite = values[np.isfinite(values)]
            lower = source_cmin
            upper = source_cmax
            if transform == "log":
                lower = (
                    np.log10(lower)
                    if lower is not None and lower > 0
                    else (float(np.min(finite)) if len(finite) else None)
                )
                upper = (
                    np.log10(upper)
                    if upper is not None and upper > 0
                    else (float(np.max(finite)) if len(finite) else None)
                )
            marker.cmin = (
                lower
                if lower is not None
                else (float(np.min(finite)) if len(finite) else None)
            )
            marker.cmax = (
                upper
                if upper is not None
                else (float(np.max(finite)) if len(finite) else None)
            )

    metadata = dict(figure.layout.meta or {})
    metadata["appearance_histogram"] = _appearance_histogram(
        histogram_values, transform
    )
    figure.layout.meta = metadata


def _appearance_histogram(value_arrays, transform, num_bins=36):
    """Build compact histogram metadata for the Plotly appearance panel."""
    if not value_arrays:
        return {"bins": [], "count": 0, "transform": transform}

    minimum = min(float(np.min(values)) for values in value_arrays)
    maximum = max(float(np.max(values)) for values in value_arrays)
    if minimum == maximum:
        edges = np.linspace(minimum - 0.5, maximum + 0.5, num_bins + 1)
    else:
        edges = np.linspace(minimum, maximum, num_bins + 1)

    bins = np.zeros(num_bins, dtype=np.int64)
    for values in value_arrays:
        bins += np.histogram(values, bins=edges)[0]

    return {
        "bins": bins.tolist(),
        "count": int(np.sum(bins)),
        "min": minimum,
        "max": maximum,
        "transform": transform,
    }


def attribute_options(mode, obj, search=None, truth_point_mode="points"):
    """Build aligned hover and color options for the attribute picker."""
    query = (search or "").strip().lower()
    attrs = [
        "id",
        *(
            attr
            for attr in object_attributes(mode, obj, truth_point_mode)
            if attr != "id"
        ),
    ]
    attrs = [
        attr
        for attr in attrs
        if not query
        or query in attr.lower()
        or query in attr.replace("_", " ").lower()
        or (attr == "id" and query in "object id")
    ]
    colorable = colorable_object_attributes(mode, obj, truth_point_mode)
    hover = [
        {
            "label": (
                "Object ID" if attr == "id" else attr.replace("_", " ").capitalize()
            ),
            "value": attr,
        }
        for attr in attrs
    ]
    color = [
        {
            "label": "",
            "value": "" if attr == "id" else attr,
            "disabled": attr != "id" and attr not in colorable,
            "title": (
                "Object ID"
                if attr == "id"
                else (
                    f"Color by {attr.replace('_', ' ')}"
                    if attr in colorable
                    else "This attribute cannot define colors"
                )
            ),
        }
        for attr in attrs
    ]
    return hover, color


def configure_geometry(detector, detector_tag, embedded_geo, geometry_choice):
    """Configure geometry while preserving an explicit user opt-out.

    Parameters
    ----------
    detector : str, optional
        Detector explicitly selected in the geometry control.
    detector_tag : str, optional
        Version tag associated with the explicit detector selection.
    embedded_geo : dict, optional
        Geometry configuration stored in the input SPINE file.
    geometry_choice : str
        Selection state, either ``"auto"``, ``"manual"`` or ``"disabled"``.
    """
    if detector is not None:
        GeoManager().initialize_or_get(detector, detector_tag)
    elif geometry_choice == "disabled":
        GeoManager().reset()
    elif embedded_geo is not None:
        GeoManager().initialize_or_get(**embedded_geo)
    else:
        GeoManager().reset()


def geometry_choice_for_file(file_path, entry_state, geometry_choice):
    """Return the file-scoped geometry choice and canonical path."""
    canonical_path = canonicalize_data_path(file_path)
    previous_path = (entry_state or {}).get("file_path")
    file_changed = previous_path is not None and previous_path != canonical_path
    choice = "auto" if previous_path is None or file_changed else geometry_choice
    return canonical_path, choice, file_changed


def is_embedded_geometry_selection(detector, detector_tag, entry_state):
    """Check whether controls merely reflect the file's automatic geometry.

    Parameters
    ----------
    detector : str, optional
        Detector shown in the geometry dropdown.
    detector_tag : str, optional
        Tag shown in the geometry-tag dropdown.
    entry_state : dict, optional
        Loaded-file state containing its embedded geometry configuration.

    Returns
    -------
    bool
        ``True`` when the controls match the embedded detector and tag. A
        temporarily empty tag is accepted while Dash populates tag options.
    """
    embedded = (entry_state or {}).get("geometry") or {}
    embedded_detector = embedded.get("detector")
    if detector is None or embedded_detector is None:
        return False
    if detector.lower() != embedded_detector.lower():
        return False

    embedded_tag = embedded.get("tag") or embedded.get("version")
    return detector_tag is None or detector_tag == embedded_tag


def register_callbacks(app):
    """Registers the callbacks to the Dash application.

    Parameters
    ----------
    app : dash.Dash
         Dash application
    """

    app.clientside_callback(
        """
        function(clickData, closeClicks, loadedEvent) {
            const trigger = window.dash_clientside.callback_context.triggered_id;
            if (trigger === 'button-close-inspector' ||
                    trigger === 'store-loaded-event') {
                document.querySelectorAll('.webgl-viewer').forEach(root =>
                    root._spinalTapViewer?.clearInspection?.()
                );
                return null;
            }
            if (trigger !== 'graph-evd' || !clickData?.points?.length) {
                return window.dash_clientside.no_update;
            }

            const point = clickData.points[0];
            const plot = document.querySelector('#graph-evd .js-plotly-plot');
            const trace = plot?.data?.[point.curveNumber];
            const config = trace?.meta?.spinal_tap_filter;
            if (!config || point.pointNumber == null) {
                return window.dash_clientside.no_update;
            }

            const offsets = config.offsets || [];
            let objectIndex = -1;
            for (let index = 0; index + 1 < offsets.length; index++) {
                if (point.pointNumber >= offsets[index] &&
                        point.pointNumber < offsets[index + 1]) {
                    objectIndex = index;
                    break;
                }
            }
            if (objectIndex < 0) return window.dash_clientside.no_update;

            const key = (config.keys || [])[objectIndex] ||
                `${config.prefix}:${objectIndex}`;
            return {
                key: key,
                prefix: config.prefix,
                position: Number(key.split(':')[1]),
                family: config.family || 'particles',
                renderer: 'plotly',
                revision: Date.now()
            };
        }
        """,
        Output("store-inspected-object", "data"),
        Input("graph-evd", "clickData", allow_optional=True),
        Input("button-close-inspector", "n_clicks"),
        Input("store-loaded-event", "data"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        """
        function(nClicks, selection, action, mode, recoSelection,
                 truthSelection, recoOptions, truthOptions, links) {
            if (!nClicks || !selection?.key) {
                return window.dash_clientside.no_update;
            }
            const available = {
                reco: new Set((recoOptions || []).map(option => option.value)),
                truth: new Set((truthOptions || []).map(option => option.value))
            };
            const current = {
                reco: (recoSelection || []).filter(key => available.reco.has(key)),
                truth: (truthSelection || []).filter(key => available.truth.has(key))
            };
            let next;
            let nextAction;
            if (action?.active && action.key === selection.key) {
                next = {
                    reco: (action.previous?.reco || []).filter(
                        key => available.reco.has(key)
                    ),
                    truth: (action.previous?.truth || []).filter(
                        key => available.truth.has(key)
                    )
                };
                nextAction = {active: false, revision: Date.now()};
            } else {
                next = {reco: [], truth: []};
                next[selection.prefix] = [selection.key];
                if (mode === 'both') {
                    const other = selection.prefix === 'reco' ? 'truth' : 'reco';
                    next[other] = (links?.[selection.key] || []).filter(
                        key => available[other].has(key)
                    );
                }
                nextAction = {
                    active: true,
                    key: selection.key,
                    // Keep the selection from before isolation began, even if
                    // the user moves directly from one isolated object to
                    // another. "Show all" then returns to the original view.
                    previous: action?.active ? action.previous : current,
                    revision: Date.now()
                };
            }

            // Update the pair as one transaction. This prevents the regular
            // linked-filter callback from treating the two set_props echoes as
            // independent user edits and recursively expanding the selection.
            const filterState = window._spinalTapFilterState || {};
            window._spinalTapFilterState = Object.assign({}, filterState, {
                reco: new Set(next.reco),
                truth: new Set(next.truth),
                acknowledgement: null,
                resetAcknowledgements: {
                    reco: [...next.reco],
                    truth: [...next.truth]
                }
            });
            window.dash_clientside.set_props(
                'dropdown-reco-filter', {value: [...next.reco]}
            );
            window.dash_clientside.set_props(
                'dropdown-truth-filter', {value: [...next.truth]}
            );
            return nextAction;
        }
        """,
        Output("store-inspection-action", "data"),
        Input("button-isolate-object", "n_clicks"),
        State("store-inspected-object", "data"),
        State("store-inspection-action", "data"),
        State("radio-run-mode", "value"),
        State("dropdown-reco-filter", "value"),
        State("dropdown-truth-filter", "value"),
        State("dropdown-reco-filter", "options"),
        State("dropdown-truth-filter", "options"),
        State("store-object-match-links", "data"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        """
        function(action, selection) {
            const active = Boolean(
                action?.active && selection?.key === action.key
            );
            return [
                active ? 'Show all' : 'Show only',
                active
                    ? 'viewer-action-button is-active'
                    : 'viewer-action-button',
                active ? 'true' : 'false',
                active
                    ? 'Restore the previous object selection'
                    : 'Show only this object and its one-hop matches'
            ];
        }
        """,
        Output("button-isolate-object", "children"),
        Output("button-isolate-object", "className"),
        Output("button-isolate-object", "aria-pressed"),
        Output("button-isolate-object", "title"),
        Input("store-inspection-action", "data"),
        Input("store-inspected-object", "data"),
    )

    app.clientside_callback(
        """
        function(selection, links) {
            const matches = selection?.key ? (links?.[selection.key] || []) : [];
            document.querySelectorAll('.webgl-viewer').forEach(root =>
                root._spinalTapViewer?.setInspectionMatches?.(selection, matches)
            );

            const plot = document.querySelector('#graph-evd .js-plotly-plot');
            if (plot && window.Plotly) {
                const overlays = [];
                const overlayIndices = [];
                (plot.data || []).forEach((trace, index) => {
                    if (trace.meta?.spinal_tap_inspection_overlay) {
                        overlayIndices.push(index);
                    }
                });
                if (overlayIndices.length) {
                    window.Plotly.deleteTraces(plot, overlayIndices.reverse());
                }

                const addOverlay = function(keys, opacity, label) {
                    if (!keys.length) return;
                    const wanted = new Set(keys);
                    const x = [], y = [], z = [];
                    let baseSize = 3;
                    (plot.data || []).forEach(trace => {
                        const config = trace.meta?.spinal_tap_filter;
                        if (!config) return;
                        const offsets = config.offsets || [];
                        const traceKeys = config.keys || [];
                        traceKeys.forEach((key, objectIndex) => {
                            if (!wanted.has(key)) return;
                            const start = offsets[objectIndex];
                            const end = offsets[objectIndex + 1];
                            for (let point = start; point < end; point++) {
                                x.push(trace.x[point]);
                                y.push(trace.y[point]);
                                z.push(trace.z[point]);
                            }
                            if (Number.isFinite(Number(trace.marker?.size))) {
                                baseSize = Math.max(
                                    baseSize, Number(trace.marker.size)
                                );
                            }
                        });
                    });
                    if (!x.length) return;
                    overlays.push({
                        type: 'scatter3d',
                        mode: 'markers',
                        name: label,
                        x: x,
                        y: y,
                        z: z,
                        hoverinfo: 'skip',
                        showlegend: false,
                        marker: {
                            color: '#f47c13',
                            opacity: opacity,
                            size: baseSize + 2,
                            symbol: 'circle-open'
                        },
                        meta: {spinal_tap_inspection_overlay: true}
                    });
                };
                addOverlay(selection?.key ? [selection.key] : [], 1, 'Selected object');
                addOverlay(matches, 0.78, 'Matched objects');
                if (overlays.length) window.Plotly.addTraces(plot, overlays);
            }
            return selection?.key
                ? {key: selection.key, matches: matches, revision: Date.now()}
                : null;
        }
        """,
        Output("store-inspection-highlights", "data"),
        Input("store-inspected-object", "data"),
        State("store-object-match-links", "data"),
        prevent_initial_call=True,
    )

    @app.callback(
        Output("object-inspector-title", "children"),
        Output("object-inspector-match-summary", "children"),
        Output("object-inspector-content", "children"),
        Output("object-inspector", "hidden"),
        Input("store-inspected-object", "data"),
        State("store-loaded-event", "data"),
        State("radio-run-mode", "value"),
        State("radio-object-mode", "value"),
        State("store-object-match-links", "data"),
        State("dropdown-reco-filter", "options"),
        State("dropdown-truth-filter", "options"),
        prevent_initial_call=True,
    )
    def update_object_inspector(
        selection,
        loaded_event,
        mode,
        family,
        links=None,
        reco_options=None,
        truth_options=None,
    ):
        """Build the object-inspection panel for a renderer selection."""
        if not selection or not loaded_event:
            return "", "", [], True

        prefix = selection.get("prefix")
        position = selection.get("position")
        selected_family = selection.get("family", family)
        valid_prefix = prefix in {"reco", "truth"}
        visible_prefix = mode == "both" or mode == prefix
        if (
            not valid_prefix
            or not visible_prefix
            or selected_family != family
            or not isinstance(position, int)
        ):
            return "", "", [], True

        try:
            reader = initialize_reader(
                loaded_event["file_path"], loaded_event.get("use_run", False)
            )
            data, *_ = load_data(reader, loaded_event["entry"], mode, family)
            collection = data[object_collection_key(prefix, family)]
            if position < 0 or position >= len(collection):
                return "", "", [], True
            summary = inspect_object(collection[position], prefix, family, position)
        except (KeyError, OSError, TypeError, ValueError):
            return "", "", [], True

        match_prefix = "Truth" if prefix == "reco" else "Reco"
        if links is not None:
            match_keys = links.get(selection["key"], [])
            options = truth_options if prefix == "reco" else reco_options
            labels = {
                option["value"]: option["label"].split(" ·", 1)[0]
                for option in (options or [])
            }
            matches = [labels.get(key, key) for key in match_keys]
        else:
            matches = [
                f"{match_prefix} {family[:-1].capitalize()} {int(match)}"
                for match in getattr(collection[position], "match_ids", [])
            ]
        if matches:
            if mode == "both":
                side = "right" if prefix == "reco" else "left"
                match_summary = f"Matches on the {side}: " + ", ".join(matches)
            else:
                match_summary = f"Matched {match_prefix.lower()}: " + ", ".join(matches)
        else:
            match_summary = f"No matched {match_prefix.lower()} {family}"

        group_labels = {
            "overview": "Overview",
            "identifiers": "Identifiers & references",
            "geometry": "Geometry",
            "energy": "Energy & kinematics",
            "lineage": "Truth lineage",
            "timing": "Timing",
            "detector_matching": "Detector matching",
            "interaction_physics": "Interaction physics",
            "matching": "Object matching",
            "details": "Additional attributes",
        }
        sections = []
        for group, rows in summary["groups"].items():
            entries = []
            for row in rows:
                entries.extend(
                    [
                        html.Dt(row["label"]),
                        html.Dd(row["value"]),
                    ]
                )
            sections.append(
                html.Section(
                    [
                        html.H4(
                            group_labels[group],
                            className="object-inspector-group-title",
                        ),
                        html.Dl(entries, className="object-inspector-grid"),
                    ],
                    className="object-inspector-group",
                )
            )

        return summary["title"], match_summary, sections, False

    app.clientside_callback(
        r"""
        function(hash) {
            if (!window.spinalTapShare) return null;
            try {
                return window.spinalTapShare.decodeHash(hash);
            } catch (error) {
                console.error('Could not decode shared Spinal Tap view:', error);
                window.spinalTapShare.reportError(
                    error.message || String(error), 'Could not load shared view'
                );
                return null;
            }
        }
        """,
        Output("store-share-request", "data"),
        Input("url", "hash"),
    )

    app.clientside_callback(
        """
        function(loadedEvent, renderer, mode, truthPoints, objectMode,
                 overlays, flashMode, crtMode, viewOptions, axes, hover, color,
                 colorscale, pointSize, pointOpacity, transform, domainMode,
                 colorMin, colorMax, rangeMode, visibleMin, visibleMax,
                 detector, detectorTag, geometryChoice,
                 recoSelection, recoOptions, truthSelection, truthOptions,
                 linked, watermarks) {
            const plotly = (renderer || []).includes('plotly');
            const sceneLabel = plotly ? 'Save HTML' : 'Save GIF';
            const sceneTitle = plotly
                ? 'Export the current Plotly scene as standalone HTML'
                : 'GIF export is available in WebGL mode';
            if (!loadedEvent) {
                return [
                    null, true, true, true, true, true,
                    sceneLabel, sceneTitle
                ];
            }

            const compactSelection = function(selection, options) {
                const selected = selection || [];
                const available = (options || []).map(option => option.value);
                return available.length && selected.length === available.length &&
                    available.every(value => selected.includes(value))
                    ? 'all'
                    : selected;
            };
            let geometry = {mode: geometryChoice || 'auto'};
            if (geometry.mode === 'manual') {
                geometry = {
                    mode: 'manual',
                    detector: detector || null,
                    tag: detectorTag || null
                };
            }

            const temporary = Boolean(loadedEvent.temporary);
            const drawModes = [...(overlays || [])];
            [['flash', flashMode], ['crt', crtMode]].forEach(function(item) {
                if (['all', 'matched'].includes(item[1])) {
                    drawModes.push(item[0]);
                }
                if (item[1] === 'matched') {
                    drawModes.push(`${item[0]}_match_only`);
                }
            });
            return [{
                version: window.spinalTapShare?.version || 1,
                file: loadedEvent.file_path,
                entry: loadedEvent.entry,
                renderer: plotly ? 'plotly' : 'webgl',
                display: {
                    run_mode: mode,
                    truth_points: truthPoints || 'points',
                    object: objectMode,
                    overlays: drawModes,
                    view: viewOptions || [],
                    axes: (axes || []).includes('axes')
                },
                attributes: {
                    hover: hover || [],
                    color: color || '',
                    colorscale: colorscale || 'Inferno',
                    appearance: {
                        point_size: pointSize || 1,
                        opacity: pointOpacity == null ? 1 : pointOpacity,
                        transform: transform || 'linear',
                        domain_mode: domainMode || 'auto',
                        color_min: colorMin,
                        color_max: colorMax,
                        range_mode: rangeMode || 'all',
                        visible_min: visibleMin,
                        visible_max: visibleMax
                    }
                },
                geometry: geometry,
                branding: {
                    watermarks: watermarks || ['spine'],
                    detector: detector || null
                },
                objects: {
                    reco: compactSelection(recoSelection, recoOptions),
                    truth: compactSelection(truthSelection, truthOptions),
                    linked: Boolean(linked)
                }
            }, temporary, false, false, temporary, false,
                sceneLabel, sceneTitle];
        }
        """,
        Output("store-share-state", "data"),
        Output("button-share", "disabled"),
        Output("button-reset-view", "disabled"),
        Output("button-save-png", "disabled"),
        Output("button-export-view", "disabled"),
        Output("button-save-scene", "disabled"),
        Output("button-save-scene", "children"),
        Output("button-save-scene", "title"),
        Input("store-loaded-event", "data"),
        Input("renderer-toggle", "value"),
        Input("radio-run-mode", "value"),
        Input("radio-truth-point-mode", "value"),
        Input("radio-object-mode", "value"),
        Input("checklist-draw-mode-1", "value"),
        Input("radio-flash-mode", "value"),
        Input("radio-crt-mode", "value"),
        Input("checklist-draw-mode-2", "value"),
        Input("checklist-show-axes", "value"),
        Input("dropdown-attr", "value"),
        Input("dropdown-attr-color", "value"),
        Input("dropdown-colorscale", "value"),
        Input("input-point-size", "value"),
        Input("input-point-opacity", "value"),
        Input("radio-color-transform", "value"),
        Input("radio-color-domain", "value"),
        Input("input-color-min", "value"),
        Input("input-color-max", "value"),
        Input("radio-visible-range", "value"),
        Input("input-visible-min", "value"),
        Input("input-visible-max", "value"),
        Input("dropdown-geo", "value"),
        Input("dropdown-geo-tag", "value"),
        Input("store-geometry-choice", "data"),
        Input("dropdown-reco-filter", "value"),
        Input("dropdown-reco-filter", "options"),
        Input("dropdown-truth-filter", "value"),
        Input("dropdown-truth-filter", "options"),
        Input("store-link-filters", "data"),
        Input("checklist-export-watermarks", "value"),
    )

    app.clientside_callback(
        """
        async function(nClicks, state) {
            if (!nClicks || !state || !window.spinalTapShare) {
                return window.dash_clientside.no_update;
            }
            try {
                await window.spinalTapShare.copyLink(state);
                setTimeout(function() {
                    window.dash_clientside.set_props(
                        'button-share', {children: 'Share'}
                    );
                }, 1600);
                return 'Copied!';
            } catch (error) {
                console.error('Could not copy shared Spinal Tap view:', error);
                setTimeout(function() {
                    window.dash_clientside.set_props(
                        'button-share', {children: 'Share'}
                    );
                }, 2200);
                return 'Copy failed';
            }
        }
        """,
        Output("button-share", "children"),
        Input("button-share", "n_clicks"),
        State("store-share-state", "data"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        """
        async function(resetClicks, saveClicks, sceneClicks, exportClicks, state) {
            const context = window.dash_clientside.callback_context;
            const trigger = context && context.triggered_id;
            if (!trigger || !window.spinalTapShare) {
                return window.dash_clientside.no_update;
            }

            try {
                if (trigger === 'button-reset-view') {
                    window.spinalTapShare.resetView();
                } else if (trigger === 'button-save-png') {
                    await window.spinalTapShare.saveImage(state);
                } else if (trigger === 'button-save-scene') {
                    const button = document.getElementById('button-save-scene');
                    const plotly = Boolean(document.querySelector(
                        '#graph-evd .js-plotly-plot'
                    ));
                    if (plotly) {
                        if (button) {
                            button.disabled = true;
                            button.textContent = 'Saving HTML';
                        }
                        try {
                            await window.spinalTapShare.saveHtml(state);
                        } finally {
                            if (button) {
                                button.disabled = false;
                                button.textContent = 'Save HTML';
                            }
                        }
                        return {
                            action: trigger,
                            revision: Date.now()
                        };
                    }
                    if (button) {
                        button.disabled = true;
                        button.textContent = 'GIF 0%';
                    }
                    try {
                        await window.spinalTapShare.saveGif(function(frame, total) {
                            if (button) {
                                button.textContent = `GIF ${Math.round(
                                    100 * frame / total
                                )}%`;
                            }
                        }, state);
                    } finally {
                        if (button) {
                            button.disabled = !document.querySelector(
                                '.webgl-viewer[data-scene-url]'
                            );
                            button.textContent = 'Save GIF';
                        }
                    }
                } else if (trigger === 'button-export-view') {
                    window.spinalTapShare.downloadJson(state);
                } else {
                    return window.dash_clientside.no_update;
                }
                return {
                    action: trigger,
                    revision: Date.now()
                };
            } catch (error) {
                console.error('Viewer action failed:', error);
                const action = trigger === 'button-reset-view'
                    ? 'Could not reset view'
                    : 'Could not export view';
                window.spinalTapShare.reportError(
                    error.message || String(error), action
                );
                return {
                    action: 'error',
                    revision: Date.now()
                };
            }
        }
        """,
        Output("store-view-action", "data"),
        Input("button-reset-view", "n_clicks"),
        Input("button-save-png", "n_clicks"),
        Input("button-save-scene", "n_clicks"),
        Input("button-export-view", "n_clicks"),
        State("store-share-state", "data"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        """
        function(values) {
            const visible = (values || []).includes('axes');
            const viewer = document.querySelector(
                '.webgl-viewer[data-scene-url]'
            );
            if (viewer) {
                viewer.dataset.showAxes = String(visible);
                viewer._spinalTapViewer?.setAxesVisible(visible);
            }

            const plot = document.querySelector('#graph-evd .js-plotly-plot');
            if (plot && window.Plotly) {
                const update = {};
                Object.keys(plot._fullLayout || {})
                    .filter(key => /^scene\\d*$/.test(key))
                    .forEach(function(key) {
                        update[`${key}.xaxis.visible`] = visible;
                        update[`${key}.yaxis.visible`] = visible;
                        update[`${key}.zaxis.visible`] = visible;
                    });
                if (Object.keys(update).length) {
                    window.Plotly.relayout(plot, update);
                }
            }
            return {visible: visible, revision: Date.now()};
        }
        """,
        Output("store-axes", "data"),
        Input("checklist-show-axes", "value"),
    )

    app.clientside_callback(
        r"""
        function(state, linkClicks) {
            if (!state || state.version !== 1 || !state.file) {
                return window.dash_clientside.no_update;
            }

            const setProps = window.dash_clientside.set_props;
            const dataMode = /^https?:\/\//.test(state.file) ? 'url' : 'path';
            const sourceMemory = window.spinalTapSourceState;
            const offClicks = (linkClicks || 0) % 2
                ? (linkClicks || 0) + 1
                : (linkClicks || 0);

            // Browse describes how the view definition was imported. Keep it
            // selected, but remember the referenced data source in the Path or
            // URL field where the user expects to find it later.
            if (sourceMemory?.values) {
                sourceMemory.values[dataMode] = state.file;
                sourceMemory.values[dataMode === 'url' ? 'path' : 'url'] = '';
            }
            setProps('input-file-path', {value: state.file});
            setProps('input-entry', {value: state.entry ?? 0});
            setProps('source-mode', {
                value: state.import_mode || dataMode
            });
            setProps('entry-mode', {value: 'entry'});
            setProps('input-entry', {
                disabled: false,
                style: {display: 'block', width: '100%', gridColumn: '1 / -1'}
            });
            ['input-run', 'input-subrun', 'input-event'].forEach(function(id) {
                setProps(id, {
                    disabled: true,
                    style: {display: 'none', width: '100%'}
                });
            });

            const pending = Object.assign({}, state, {
                restore_id: `${Date.now()}:${Math.random()}`,
                link_clicks_off: offClicks
            });
            return pending;
        }
        """,
        Output("store-share-pending", "data"),
        Input("store-share-request", "data"),
        State("button-link-filters", "n_clicks"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        """
        function(pending, loadedEvent, recoOptions, truthOptions, tagOptions,
                 objectFilter) {
            if (!pending || !loadedEvent) {
                return window.dash_clientside.no_update;
            }

            const canonical = value => (value || '').replace(
                /^\\/sdf\\/data\\/neutrino(?=\\/|$)/, '/data'
            );
            const sameEntry = (
                canonical(loadedEvent.file_path) === canonical(pending.file) &&
                Number(loadedEvent.entry) === Number(pending.entry)
            );
            if (window._spinalTapShareRestore === pending.restore_id) {
                if (!sameEntry) window.spinalTapShare?.cancelCameraRestore();
                return window.dash_clientside.no_update;
            }
            if (!sameEntry) {
                return window.dash_clientside.no_update;
            }

            const geometry = pending.geometry || {mode: 'auto'};
            const availableTags = new Set(
                (tagOptions || []).map(option => option.value)
            );
            if (geometry.mode === 'manual' && geometry.tag &&
                    !availableTags.has(geometry.tag)) {
                return window.dash_clientside.no_update;
            }

            // Wait for the object-filter callback to acknowledge the newly
            // loaded event's neutral all-visible baseline. Applying a shared
            // subset before that acknowledgement would let the reset overwrite
            // the restored selection on the next browser turn.
            const baseline = new Set(objectFilter || []);
            const allObjects = (recoOptions || []).concat(truthOptions || [])
                .map(option => option.value);
            if (allObjects.length &&
                    !allObjects.every(value => baseline.has(value))) {
                return window.dash_clientside.no_update;
            }

            window._spinalTapShareRestore = pending.restore_id;
            const setProps = window.dash_clientside.set_props;
            const display = pending.display || {};
            const attributes = pending.attributes || {};
            const overlays = display.overlays || [];
            const resolveSelection = function(saved, options) {
                const available = (options || []).map(option => option.value);
                if (saved === 'all') return available;
                const valid = new Set(available);
                return (saved || []).filter(value => valid.has(value));
            };
            const objects = pending.objects || {};
            const reco = resolveSelection(objects.reco, recoOptions);
            const truth = resolveSelection(objects.truth, truthOptions);

            // Reflect the already-rendered shared state into the controls only
            // after its source and entry are on screen. Doing this earlier can
            // redraw the previously loaded file while a URL is downloading.
            setProps('renderer-toggle', {
                value: pending.renderer === 'plotly' ? ['plotly'] : []
            });
            setProps('radio-run-mode', {value: display.run_mode || 'reco'});
            setProps('radio-object-mode', {value: display.object || 'particles'});
            setProps('checklist-draw-mode-1', {
                value: overlays.filter(value =>
                    ['point', 'direction', 'vertex', 'raw'].includes(value)
                )
            });
            setProps('radio-flash-mode', {
                value: overlays.includes('flash_match_only')
                    ? 'matched'
                    : (overlays.includes('flash') ? 'all' : 'off')
            });
            setProps('radio-crt-mode', {
                value: overlays.includes('crt_match_only')
                    ? 'matched'
                    : (overlays.includes('crt') ? 'all' : 'off')
            });
            setProps('checklist-draw-mode-2', {
                value: display.view || ['split_scene', 'sync']
            });
            setProps('checklist-show-axes', {
                value: display.axes === false ? [] : ['axes']
            });
            setProps('dropdown-attr', {value: attributes.hover || []});
            setProps('dropdown-attr-color', {value: attributes.color || ''});
            setProps('dropdown-colorscale', {
                value: attributes.colorscale || 'Inferno'
            });
            const appearance = attributes.appearance || {};
            setProps('input-point-size', {
                value: appearance.point_size || 1
            });
            setProps('input-point-opacity', {
                value: appearance.opacity == null ? 1 : appearance.opacity
            });
            setProps('radio-color-transform', {
                value: appearance.transform || 'linear'
            });
            setProps('radio-color-domain', {
                value: appearance.domain_mode || 'auto'
            });
            setProps('input-color-min', {value: appearance.color_min ?? null});
            setProps('input-color-max', {value: appearance.color_max ?? null});
            setProps('radio-visible-range', {
                value: appearance.range_mode || 'all'
            });
            setProps('input-visible-min', {
                value: appearance.visible_min ?? null
            });
            setProps('input-visible-max', {
                value: appearance.visible_max ?? null
            });
            setProps('checklist-export-watermarks', {
                value: pending.branding?.watermarks || ['spine']
            });

            if (geometry.mode === 'manual') {
                setProps('dropdown-geo', {value: geometry.detector || null});
                setProps('dropdown-geo-tag', {value: geometry.tag || null});
                setProps('store-geometry-choice', {data: 'manual'});
            } else if (geometry.mode === 'disabled') {
                setProps('dropdown-geo', {value: null});
                setProps('dropdown-geo-tag', {value: null});
                setProps('store-geometry-choice', {data: 'disabled'});
            } else {
                setProps('store-geometry-choice', {data: 'auto'});
            }

            setTimeout(function() {
                setProps('dropdown-reco-filter', {value: reco});
                setProps('dropdown-truth-filter', {value: truth});
                setTimeout(function() {
                    const clicks = pending.link_clicks_off || 0;
                    setProps('button-link-filters', {
                        n_clicks: objects.linked ? clicks + 1 : clicks
                    });
                    window.spinalTapShare?.restoreCamera(pending.camera);
                }, 180);
            }, 0);

            return {
                restore_id: pending.restore_id,
                file: loadedEvent.file_path,
                entry: loadedEvent.entry
            };
        }
        """,
        Output("store-share-applied", "data"),
        Input("store-share-pending", "data"),
        Input("store-loaded-event", "data"),
        Input("dropdown-reco-filter", "options"),
        Input("dropdown-truth-filter", "options"),
        Input("dropdown-geo-tag", "options"),
        Input("store-object-filter", "data"),
        prevent_initial_call=True,
    )

    @app.callback(
        Output("radio-run-mode", "options"),
        Output("radio-run-mode", "value"),
        Output("radio-object-mode", "options"),
        Output("radio-object-mode", "value"),
        Output("checklist-draw-mode-1", "options"),
        Output("checklist-draw-mode-1", "value"),
        Output("radio-flash-mode", "options"),
        Output("radio-flash-mode", "value"),
        Output("radio-crt-mode", "options"),
        Output("radio-crt-mode", "value"),
        Output("radio-truth-point-mode", "options"),
        Output("radio-truth-point-mode", "value"),
        Output("truth-point-control", "style"),
        Input("store-display-controls", "data"),
        prevent_initial_call=True,
    )
    def update_display_controls(control_state):
        """Apply file-dependent display capabilities to the controls."""
        if not control_state:
            return (no_update,) * 13
        overlay_state = overlay_control_state(
            control_state["draw_options"], control_state["draw_value"]
        )
        return (
            control_state["run_options"],
            control_state["run_value"],
            control_state["object_options"],
            control_state["object_value"],
            *overlay_state,
            control_state["truth_point_options"],
            control_state["truth_point_value"],
            control_state["truth_point_style"],
        )

    app.clientside_callback(
        """
        function(value) {
            setTimeout(function() {
                const picker = document.getElementById('truth-point-control');
                if (picker) picker.open = false;
            }, 0);
            return 'Point source';
        }
        """,
        Output("truth-point-summary", "children"),
        Input("radio-truth-point-mode", "value"),
    )

    @app.callback(
        Output("dropdown-geo-tag", "options"),
        Output("dropdown-geo-tag", "value"),
        Input("dropdown-geo", "value"),
        Input("store-entry", "data"),
    )
    def update_tag_options(detector, entry_state):
        """Update available tags based on selected detector."""
        if not detector:
            return [], None

        from spine.geo.factories import geo_dict

        # Get all tags for the selected detector
        tags = []
        for info in geo_dict().values():
            if info["name"].lower() == detector.lower():
                tag = info.get("tag", "")
                version = info.get("version", "")
                label = f"{tag} (v{version})" if tag else f"v{version}"
                tags.append({"label": label, "value": tag or version})

        # Sort by version number (descending)
        tags.sort(key=lambda x: x.get("value", ""), reverse=True)

        embedded_geo = (entry_state or {}).get("geometry") or {}
        selected = None
        embedded_detector = embedded_geo.get("detector", "").lower()
        if embedded_detector == detector.lower():
            selected = embedded_geo.get("tag") or embedded_geo.get("version")
        values = {option["value"] for option in tags}
        if selected not in values:
            selected = tags[0]["value"] if tags else None
        return tags, selected

    @app.callback(
        Output("dropdown-geo", "value"),
        Input("store-entry", "data"),
        Input("button-restore-geometry", "n_clicks"),
        prevent_initial_call=True,
    )
    def show_embedded_geometry(entry_state, _restore_clicks):
        """Reflect an automatically selected file geometry in the controls."""
        if entry_state is None:
            return no_update
        embedded_geo = entry_state.get("geometry") or {}
        if not embedded_geo or not embedded_geo.get("detector"):
            return None
        return embedded_geo["detector"].lower()

    @app.callback(
        Output("button-restore-geometry", "hidden"),
        Output("button-restore-geometry", "title"),
        Input("store-entry", "data"),
        Input("dropdown-geo", "value"),
    )
    def update_geometry_restore(entry_state, detector):
        """Offer a compact way to restore the file's detected geometry."""
        embedded_geo = (entry_state or {}).get("geometry") or {}
        embedded_detector = embedded_geo.get("detector")
        if not embedded_detector:
            return True, "No detected geometry to restore"

        tag = embedded_geo.get("tag") or embedded_geo.get("version")
        label = embedded_detector if not tag else f"{embedded_detector} · {tag}"
        return detector is not None, f"Restore detected geometry: {label}"

    app.clientside_callback(
        """
        function(detector, tag, entryState) {
            if (detector == null) return 'disabled';

            const embedded = (entryState || {}).geometry || {};
            const embeddedDetector = (embedded.detector || '').toLowerCase();
            const embeddedTag = embedded.tag || embedded.version || null;
            if (embeddedDetector === detector.toLowerCase() &&
                    (tag == null || embeddedTag === tag)) {
                return 'auto';
            }
            return 'manual';
        }
        """,
        Output("store-geometry-choice", "data"),
        Input("dropdown-geo", "value"),
        Input("dropdown-geo-tag", "value"),
        State("store-entry", "data"),
        prevent_initial_call=True,
    )

    # Clientside callback to submit the form when credentials are valid
    app.clientside_callback(
        """
        function(data) {
            if (data && data.experiment && data.password) {
                // Create a form and submit it
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = '/login';

                const expInput = document.createElement('input');
                expInput.type = 'hidden';
                expInput.name = 'experiment';
                expInput.value = data.experiment;
                form.appendChild(expInput);

                const pwdInput = document.createElement('input');
                pwdInput.type = 'hidden';
                pwdInput.name = 'password';
                pwdInput.value = data.password;
                form.appendChild(pwdInput);

                document.body.appendChild(form);
                form.submit();
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("url", "pathname"),
        Input("login-submit-trigger", "data"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        """
        function(attrs, color) {
            const context = window.dash_clientside.callback_context;
            const trigger = context && context.triggered_id;
            window.spinalTapRefreshControls?.markDirty(trigger);
            return window.dash_clientside.no_update;
        }
        """,
        Output("store-dropdown-pending", "data"),
        Input("dropdown-attr", "value"),
        Input("dropdown-attr-color", "value"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        """
        function(options, attrs, color) {
            window.spinalTapRefreshControls?.renderAttributeRows(
                options, attrs, color
            );
            return window.dash_clientside.no_update;
        }
        """,
        Output("attribute-picker-list", "title"),
        Input("store-attribute-options", "data"),
        Input("dropdown-attr", "value"),
        Input("dropdown-attr-color", "value"),
    )

    @app.callback(
        Output("continuous-appearance-controls", "style"),
        Input("radio-run-mode", "value"),
        Input("radio-object-mode", "value"),
        Input("radio-truth-point-mode", "value"),
        Input("dropdown-attr-color", "value"),
        Input("checklist-draw-mode-1", "value"),
    )
    def update_colorscale_visibility(mode, obj, truth_point_mode, attr, draw_modes):
        """Show scalar appearance tools only for continuous point colors."""
        raw = "raw" in (draw_modes or [])
        visible = raw or continuous_color_attribute(mode, obj, attr, truth_point_mode)
        return {"display": "grid" if visible else "none"}

    app.clientside_callback(
        """
        function(domainMode, rangeMode) {
            return [
                {display: domainMode === 'manual' ? 'grid' : 'none'},
                {display: rangeMode === 'range' ? 'grid' : 'none'}
            ];
        }
        """,
        Output("color-domain-inputs", "style"),
        Output("visible-range-inputs", "style"),
        Input("radio-color-domain", "value"),
        Input("radio-visible-range", "value"),
    )

    app.clientside_callback(
        """
        function(size, opacity) {
            const pointSize = Number.isFinite(Number(size)) ? Number(size) : 1;
            const alpha = Number.isFinite(Number(opacity)) ? Number(opacity) : 1;
            return [pointSize.toFixed(1) + '\u00d7',
                Math.round(alpha * 100) + '%'];
        }
        """,
        Output("point-size-value", "children"),
        Output("point-opacity-value", "children"),
        Input("input-point-size", "value"),
        Input("input-point-opacity", "value"),
    )

    app.clientside_callback(
        """
        function(size, opacity, colorscale, transform, domainMode,
                 colorMin, colorMax, rangeMode, visibleMin, visibleMax) {
            const settings = {
                point_size: size || 1,
                opacity: opacity == null ? 1 : opacity,
                colorscale: colorscale || 'Inferno',
                transform: transform || 'linear',
                domain_mode: domainMode || 'auto',
                color_min: colorMin,
                color_max: colorMax,
                range_mode: rangeMode || 'all',
                visible_min: visibleMin,
                visible_max: visibleMax
            };
            window.spinalTapWebgl?.applyAppearance(settings);
            const plotly = [...document.querySelectorAll(
                '#renderer-toggle input:checked'
            )].some(input => input.value === 'plotly');
            if (plotly) {
                clearTimeout(window.spinalTapPlotlyAppearanceTimer);
                window.spinalTapPlotlyAppearanceTimer = setTimeout(function() {
                    window.dash_clientside?.set_props(
                        'store-appearance-render-request',
                        {data: {revision: Date.now(), settings}}
                    );
                }, 100);
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("store-appearance-render-request", "data"),
        Input("input-point-size", "value"),
        Input("input-point-opacity", "value"),
        Input("dropdown-colorscale", "value"),
        Input("radio-color-transform", "value"),
        Input("radio-color-domain", "value"),
        Input("input-color-min", "value"),
        Input("input-color-max", "value"),
        Input("radio-visible-range", "value"),
        Input("input-visible-min", "value"),
        Input("input-visible-max", "value"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        """
        function(recoSelection, truthSelection, recoOptions, truthOptions,
                 linked, links, loadedEvent, draw_mode_1, flashMode, crtMode,
                 renderer) {
            const context = window.dash_clientside.callback_context;
            const trigger = context && context.triggered_id;
            const valid = {
                reco: new Set((recoOptions || []).map(option => option.value)),
                truth: new Set((truthOptions || []).map(option => option.value))
            };
            const incoming = {
                reco: new Set(
                    (recoSelection || []).filter(value => valid.reco.has(value))
                ),
                truth: new Set(
                    (truthSelection || []).filter(value => valid.truth.has(value))
                )
            };
            const selectionWasSanitized = {
                reco: incoming.reco.size !== (recoSelection || []).length,
                truth: incoming.truth.size !== (truthSelection || []).length
            };
            Object.entries(selectionWasSanitized).forEach(function(entry) {
                const side = entry[0];
                if (!entry[1]) return;
                window.dash_clientside.set_props(
                    side === 'reco'
                        ? 'dropdown-reco-filter'
                        : 'dropdown-truth-filter',
                    {value: [...incoming[side]]}
                );
            });
            let state = window._spinalTapFilterState;
            const eventKey = loadedEvent ? JSON.stringify([
                loadedEvent.file_path,
                loadedEvent.entry,
                loadedEvent.run,
                loadedEvent.subrun,
                loadedEvent.event,
                loadedEvent.filter_revision
            ]) : null;
            const eventChanged = Boolean(
                eventKey && (!state || state.eventKey !== eventKey)
            );

            if (eventChanged) {
                // Navigation establishes a neutral baseline. A closed chain
                // controls subsequent user edits; it must not interpret the
                // programmatic initialization as a directional match request.
                const reco = new Set(loadedEvent.reco_filter || []);
                const truth = new Set(loadedEvent.truth_filter || []);
                const resetAcknowledgements = {
                    reco: [...reco],
                    truth: [...truth]
                };
                state = {
                    reco,
                    truth,
                    eventKey,
                    acknowledgement: null,
                    resetAcknowledgements
                };
                window.dash_clientside.set_props(
                    'dropdown-reco-filter', {value: [...reco]}
                );
                window.dash_clientside.set_props(
                    'dropdown-truth-filter', {value: [...truth]}
                );
            } else if (!linked) {
                // Without linkage there is no transaction to preserve: both
                // dropdown values are authoritative. Dash may update the two
                // values in one callback while reporting only one trigger,
                // particularly when Both mode is first loaded.
                state = {
                    reco: incoming.reco,
                    truth: incoming.truth,
                    eventKey,
                    acknowledgement: null,
                    resetAcknowledgements: null
                };
            } else if (!state) {
                state = {
                    reco: incoming.reco,
                    truth: incoming.truth,
                    eventKey,
                    acknowledgement: null,
                    resetAcknowledgements: null
                };
            }

            const triggeredSide = trigger === 'dropdown-reco-filter'
                ? 'reco'
                : trigger === 'dropdown-truth-filter' ? 'truth' : null;
            // A selection containing values absent from the current options
            // is necessarily a late programmatic echo from the prior event,
            // never a user edit in the currently displayed dropdown.
            const side = triggeredSide && !selectionWasSanitized[triggeredSide]
                ? triggeredSide
                : null;
            const other = side === 'reco' ? 'truth' : 'reco';
            const expected = state.acknowledgement;
            const isAcknowledgement = Boolean(
                side && expected && expected.side === side
            );
            const resetExpected = side && state.resetAcknowledgements
                ? state.resetAcknowledgements[side]
                : null;
            const hasResetPending = Boolean(
                side && state.resetAcknowledgements &&
                Object.hasOwn(state.resetAcknowledgements, side)
            );
            const isResetAcknowledgement = Boolean(
                side && resetExpected &&
                resetExpected.length === incoming[side].size &&
                resetExpected.every(value => incoming[side].has(value))
            );

            if (eventChanged) {
                // The complete event selection was adopted above.
            } else if (isResetAcknowledgement) {
                // Ignore the selector echoes caused by the neutral reset.
                state[side] = incoming[side];
                delete state.resetAcknowledgements[side];
                if (!Object.keys(state.resetAcknowledgements).length) {
                    state.resetAcknowledgements = null;
                }
            } else if (hasResetPending) {
                // An older value can arrive after the options and event store.
                // Reassert the reset until this selector acknowledges it.
                window.dash_clientside.set_props(
                    side === 'reco'
                        ? 'dropdown-reco-filter'
                        : 'dropdown-truth-filter',
                    {value: resetExpected}
                );
            } else if (!linked) {
                // The complete unlinked snapshot was adopted above.
            } else if (isAcknowledgement) {
                // set_props invokes this callback again. Keep the transaction's
                // complete pair instead of treating that echo as a user action.
                state[side] = new Set(expected.values);
                state.acknowledgement = null;
            } else if (side) {
                const source = incoming[side];
                const oldSource = state[side];
                const target = new Set(state[other]);

                if (linked && source.size === 0 && oldSource.size > 0) {
                    // Clear is a whole-comparison action while filters are linked.
                    target.clear();
                } else if (linked) {
                    source.forEach(key => {
                        if (!oldSource.has(key)) {
                            (links?.[key] || []).forEach(match => target.add(match));
                        }
                    });
                    oldSource.forEach(key => {
                        if (!source.has(key)) {
                            (links?.[key] || []).forEach(match => target.delete(match));
                        }
                    });
                }
                state[side] = source;
                state[other] = target;

                if (linked) {
                    const values = [...target];
                    state.acknowledgement = {side: other, values};
                    window.dash_clientside.set_props(
                        other === 'reco'
                            ? 'dropdown-reco-filter'
                            : 'dropdown-truth-filter',
                        {value: values}
                    );
                }
            } else {
                // Link and match-map notifications are selection-neutral.
                // During a scene load Dash updates both dropdowns and the
                // match map independently; copying their transient input
                // snapshot here can erase whichever dropdown has not arrived.
                state.acknowledgement = null;
            }

            window._spinalTapFilterState = state;
            const recoValues = [...state.reco];
            const truthValues = [...state.truth];
            const selection = recoValues.concat(truthValues);
            const rendererName = (renderer || []).includes('plotly')
                ? 'plotly'
                : 'webgl';
            const renderRequest = function() {
                return {revision: `${Date.now()}:${Math.random()}`};
            };
            if (rendererName === 'plotly') {
                // Plotly 6 transports large traces as binary typed arrays.
                // Rebuild its filtered figure from the cached Python event
                // instead of attempting to slice those arrays in JavaScript.
                return [selection, renderRequest()];
            }
            const dependentModes = new Set(rendererName === 'webgl'
                ? ['flash', 'flash_match_only', 'crt', 'crt_match_only']
                : ['point', 'direction', 'vertex', 'flash',
                    'flash_match_only', 'crt', 'crt_match_only']);
            const activeModes = [...(draw_mode_1 || [])];
            if (flashMode !== 'off') activeModes.push('flash');
            if (crtMode !== 'off') activeModes.push('crt');
            if (activeModes.some(mode => dependentModes.has(mode))) {
                return [selection, renderRequest()];
            }

            setTimeout(function() {
                const viewer = document.querySelector('.webgl-viewer');
                if (viewer) {
                    viewer.dataset.selection = (selection || []).join(',');
                }
                if (viewer && viewer._spinalTapViewer) {
                    viewer._spinalTapViewer.setSelection(selection || []);
                    return;
                }

                const graphDiv = document.getElementById('graph-evd');
                if (!graphDiv) return;

                const plotlyDiv = graphDiv.querySelector('.js-plotly-plot');
                if (!plotlyDiv || !plotlyDiv.layout) return;

                const layoutMeta = plotlyDiv.layout.meta || {};
                const revision = layoutMeta.spinal_tap_filter_revision;
                if (revision === undefined) return;

                let cache = plotlyDiv._spinalTapObjectFilter;
                let cacheWasCreated = false;
                if (!cache || cache.revision !== revision) {
                    cache = {revision: revision, traces: {}};
                    cacheWasCreated = true;
                    plotlyDiv.data.forEach(function(trace, index) {
                        const meta = trace.meta || {};
                        const config = meta.spinal_tap_filter;
                        if (!config) return;

                        cache.traces[index] = {
                            config: config,
                            x: trace.x || [],
                            y: trace.y || [],
                            z: trace.z || [],
                            text: trace.text || [],
                            color: (trace.marker || {}).color || []
                        };
                    });
                    plotlyDiv._spinalTapObjectFilter = cache;
                }

                const selected = new Set(selection || []);
                const allSelected = Object.values(cache.traces).every(
                    function(base) {
                        const count = base.config.offsets.length - 1;
                        for (let objectIndex = 0;
                             objectIndex < count;
                             objectIndex++) {
                            const key = base.config.prefix + ':' + objectIndex;
                            if (!selected.has(key)) return false;
                        }
                        return true;
                    }
                );
                if (cacheWasCreated && allSelected) return;

                Object.entries(cache.traces).forEach(function(entry) {
                    const traceIndex = Number(entry[0]);
                    const base = entry[1];
                    const offsets = base.config.offsets;
                    const ranges = [];
                    for (let objectIndex = 0;
                         objectIndex < offsets.length - 1;
                         objectIndex++) {
                        const key = base.config.prefix + ':' + objectIndex;
                        if (selected.has(key)) {
                            ranges.push([
                                offsets[objectIndex], offsets[objectIndex + 1]
                            ]);
                        }
                    }

                    const selectRanges = function(values) {
                        const result = [];
                        ranges.forEach(function(range) {
                            for (let index = range[0]; index < range[1]; index++) {
                                result.push(values[index]);
                            }
                        });
                        return result;
                    };
                    const update = {
                        x: [selectRanges(base.x)],
                        y: [selectRanges(base.y)],
                        z: [selectRanges(base.z)],
                        text: [selectRanges(base.text)]
                    };
                    if (base.color.length === base.x.length) {
                        update['marker.color'] = [selectRanges(base.color)];
                    }
                    Plotly.restyle(plotlyDiv, update, [traceIndex]);
                });
            }, 0);

            return [selection, window.dash_clientside.no_update];
        }
        """,
        Output("store-object-filter", "data"),
        Output("store-filter-render-request", "data"),
        Input("dropdown-reco-filter", "value"),
        Input("dropdown-truth-filter", "value"),
        Input("dropdown-reco-filter", "options"),
        Input("dropdown-truth-filter", "options"),
        Input("store-link-filters", "data"),
        Input("store-object-match-links", "data"),
        Input("store-loaded-event", "data"),
        State("checklist-draw-mode-1", "value"),
        State("radio-flash-mode", "value"),
        State("radio-crt-mode", "value"),
        State("renderer-toggle", "value"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        """
        function(color, attrs) {
            if (!color || (attrs || []).includes(color)) {
                return window.dash_clientside.no_update;
            }
            return [...(attrs || []), color];
        }
        """,
        Output("dropdown-attr", "value", allow_duplicate=True),
        Input("dropdown-attr-color", "value"),
        State("dropdown-attr", "value"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        """
        function(attrs, color, drawModes) {
            const count = (attrs || []).length;
            const raw = (drawModes || []).includes('raw');
            const colorName = raw
                ? 'Depositions (Raw)'
                : color
                    ? color.replaceAll('_', ' ').replace(
                        /^./, value => value.toUpperCase()
                    )
                    : 'Object ID';
            return `${count} shown · Color: ${colorName}`;
        }
        """,
        Output("attribute-picker-summary", "children"),
        Input("dropdown-attr", "value"),
        Input("dropdown-attr-color", "value"),
        Input("checklist-draw-mode-1", "value"),
    )

    app.clientside_callback(
        """
        function(nClicks) {
            const linked = Boolean((nClicks || 0) % 2);
            return [
                linked,
                linked ? 'true' : 'false',
                linked ? 'match-link-toggle is-linked' : 'match-link-toggle'
            ];
        }
        """,
        Output("store-link-filters", "data"),
        Output("button-link-filters", "aria-pressed"),
        Output("button-link-filters", "className"),
        Input("button-link-filters", "n_clicks"),
    )

    app.clientside_callback(
        """
        function(mode) {
            return {display: mode === 'both' ? 'flex' : 'none'};
        }
        """,
        Output("checklist-draw-mode-2", "style"),
        Input("radio-run-mode", "value"),
    )

    app.clientside_callback(
        """
        function(mode, links) {
            const showReco = mode !== 'truth';
            const showTruth = mode !== 'reco';
            const showLink = mode === 'both';
            const hasLinks = Boolean(links && Object.keys(links).length);
            return [
                {display: showReco ? 'flex' : 'none'},
                {display: showTruth ? 'flex' : 'none'},
                {display: showLink ? 'inline-flex' : 'none'},
                !hasLinks
            ];
        }
        """,
        Output("reco-filter-group", "style"),
        Output("truth-filter-group", "style"),
        Output("button-link-filters", "style"),
        Output("button-link-filters", "disabled"),
        Input("radio-run-mode", "value"),
        Input("store-object-match-links", "data"),
    )

    app.clientside_callback(
        """
        function(recoSelection, recoOptions, truthSelection, truthOptions) {
            const recoValues = new Set(
                (recoOptions || []).map(option => option.value)
            );
            const truthValues = new Set(
                (truthOptions || []).map(option => option.value)
            );
            const recoCount = (recoSelection || []).filter(
                value => recoValues.has(value)
            ).length;
            const recoTotal = (recoOptions || []).length;
            const truthCount = (truthSelection || []).filter(
                value => truthValues.has(value)
            ).length;
            const truthTotal = (truthOptions || []).length;
            return [
                `Reco ${recoCount}/${recoTotal}`,
                `Truth ${truthCount}/${truthTotal}`
            ];
        }
        """,
        Output("reco-filter-label", "children"),
        Output("truth-filter-label", "children"),
        Input("dropdown-reco-filter", "value"),
        Input("dropdown-reco-filter", "options"),
        Input("dropdown-truth-filter", "value"),
        Input("dropdown-truth-filter", "options"),
    )

    app.clientside_callback(
        """
        function(commit, attribute, drawModes) {
            if (!commit || commit.control !== 'attribute-picker') {
                return window.dash_clientside.no_update;
            }
            const effectiveAttribute = (drawModes || []).includes('raw')
                ? 'depositions'
                : attribute || '';
            setTimeout(function() {
                const viewer = document.querySelector('.webgl-viewer');
                if (!viewer) return;
                viewer.dataset.colorAttribute = effectiveAttribute;
                if (viewer._spinalTapViewer) {
                    viewer._spinalTapViewer.setColorAttribute(effectiveAttribute);
                }
            }, 0);
            return window.dash_clientside.no_update;
        }
        """,
        Output("store-color", "data"),
        Input("store-dropdown-commit", "data"),
        State("dropdown-attr-color", "value"),
        State("checklist-draw-mode-1", "value"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        """
        function(bootstrap) {
            if (!bootstrap) return [];
            return window.spinalTapTheme?.initializeToggle?.() || [];
        }
        """,
        Output("theme-toggle", "value"),
        Input("store-theme-bootstrap", "data"),
    )

    app.clientside_callback(
        """
        function(theme) {
            const dark = (theme || []).includes('dark');
            window.spinalTapTheme?.select?.(dark ? 'dark' : 'light');
            setTimeout(function() {
                const viewer = document.querySelector('.webgl-viewer');
                if (viewer) {
                    viewer.dataset.dark = String(dark);
                }
                if (viewer && viewer._spinalTapViewer) {
                    viewer._spinalTapViewer.setDark(dark);
                    return;
                }

                const graphDiv = document.getElementById('graph-evd');
                if (!graphDiv) return;

                const plotlyDiv = graphDiv.querySelector('.js-plotly-plot');
                if (!plotlyDiv || !plotlyDiv.layout) return;

                const background = dark ? 'black' : 'white';
                const foreground = dark ? '#f2f5fa' : '#2a3f5f';
                const grid = dark ? '#506784' : 'lightgray';
                const update = {
                    paper_bgcolor: background,
                    'font.color': foreground,
                    'legend.font.color': foreground
                };

                ['scene', 'scene2', 'scene3'].forEach(function(scene) {
                    if (!plotlyDiv.layout[scene]) return;
                    ['xaxis', 'yaxis', 'zaxis'].forEach(function(axis) {
                        const key = scene + '.' + axis;
                        update[key + '.backgroundcolor'] = background;
                        update[key + '.gridcolor'] = grid;
                        update[key + '.color'] = foreground;
                    });
                });

                Plotly.relayout(plotlyDiv, update);

                const geometry = [];
                plotlyDiv.data.forEach(function(trace, index) {
                    if (trace.meta && trace.meta.kind === 'geometry') {
                        geometry.push(index);
                    }
                });
                if (geometry.length) {
                    const color = dark
                        ? 'rgba(255,255,255,0.400)'
                        : 'rgba(0,0,0,0.200)';
                    Plotly.restyle(plotlyDiv, {'line.color': color}, geometry);
                }
            }, 0);

            return window.dash_clientside.no_update;
        }
        """,
        Output("store-theme", "data"),
        Input("theme-toggle", "value"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        """
        function(children, draw_mode_1, draw_mode_2) {
            const draw_mode = (draw_mode_1 || []).concat(draw_mode_2 || []);
            const syncEnabled = draw_mode.includes('sync');

            // Defer until graph is actually mounted
            setTimeout(function() {
                const graphDiv = document.getElementById('graph-evd');
                if (!graphDiv) {
                    return;
                }

                const plotlyDiv = graphDiv.querySelector('.js-plotly-plot');
                if (!plotlyDiv || !plotlyDiv.layout) {
                    return;
                }

                window.spinalTapShare?.rememberPlotlyCamera(plotlyDiv);

                const hasDualLayout = !!(
                    plotlyDiv.layout.scene &&
                    plotlyDiv.layout.scene2
                );
                if (!hasDualLayout) {
                    return;
                }

                // Always remove old listener first to avoid duplicates
                if (plotlyDiv._cameraSyncListener) {
                    plotlyDiv.removeListener(
                        'plotly_relayout',
                        plotlyDiv._cameraSyncListener
                    );
                    delete plotlyDiv._cameraSyncListener;
                }

                if (!syncEnabled) {
                    console.log('Camera sync disabled');
                    return;
                }

                console.log('Attaching camera sync listener');

                let syncing = false;
                let lastSyncTime = 0;

                const listener = function(eventData) {
                    if (!eventData) return;

                    const now = Date.now();
                    // Ignore events immediately following relayout
                    if (syncing || now - lastSyncTime < 150) {
                        return;
                    }

                    const hasScene  = Object.prototype.hasOwnProperty.call(
                        eventData, 'scene.camera'
                    );
                    const hasScene2 = Object.prototype.hasOwnProperty.call(
                        eventData, 'scene2.camera'
                    );

                    // Ignore events that touch both cameras
                    if (hasScene && hasScene2) {
                        return;
                    }

                    if (!hasScene && !hasScene2) {
                        return;
                    }

                    const update = {};
                    let cam = null;

                    if (hasScene && !hasScene2) {
                        cam = eventData['scene.camera'];
                        if (!cam) return;
                        // Set BOTH cameras to avoid springback
                        update['scene.camera']  = cam;
                        update['scene2.camera'] = cam;
                        console.log('Syncing from left scene');
                    } else if (hasScene2 && !hasScene) {
                        cam = eventData['scene2.camera'];
                        if (!cam) return;
                        // Set BOTH cameras to avoid springback
                        update['scene.camera']  = cam;
                        update['scene2.camera'] = cam;
                        console.log('Syncing from right scene');
                    }

                    if (Object.keys(update).length === 0) {
                        return;
                    }

                    syncing = true;
                    lastSyncTime = Date.now();

                    Plotly.relayout(plotlyDiv, update)
                        .catch(function(err) {
                            console.error(
                                'Camera sync relayout error:', err
                            );
                        })
                        .finally(function() {
                            // Delay so relayout events are ignored
                            setTimeout(function() {
                                syncing = false;
                            }, 50);
                        });
                };

                plotlyDiv.on('plotly_relayout', listener);
                plotlyDiv._cameraSyncListener = listener;

            }, 0);

            // side-effect only
            return window.dash_clientside.no_update;
        }
        """,
        Output("store-camera-sync", "data"),
        Input("div-evd", "children"),
        State("checklist-draw-mode-1", "value"),
        State("checklist-draw-mode-2", "value"),
        prevent_initial_call=True,
    )

    @app.callback(
        [Output("login-error", "children"), Output("login-submit-trigger", "data")],
        [Input("login-button", "n_clicks")],
        [State("experiment-select", "value"), State("password-input", "value")],
        prevent_initial_call=True,
    )
    def handle_login(n_clicks, experiment, password):
        """Handle login button click - validate and trigger form submission."""
        from .app import check_password

        if not n_clicks:
            return "", None

        if not experiment:
            return "Please select an experiment", None

        if not password:
            return "Please enter a password", None

        if check_password(experiment, password):
            # Credentials are valid - trigger form submission via clientside callback
            return "", {"experiment": experiment, "password": password}

        return "Invalid credentials", None

    @app.callback(
        [
            Output("div-evd", "children"),
            Output("input-entry", "value"),
            Output("input-run", "value"),
            Output("input-subrun", "value"),
            Output("input-event", "value"),
            Output("text-info", "value"),
            Output("event-meta", "children"),
            Output("log-panel", "className"),
            Output("dropdown-reco-filter", "options"),
            Output("dropdown-reco-filter", "value"),
            Output("dropdown-truth-filter", "options"),
            Output("dropdown-truth-filter", "value"),
            Output("store-object-match-links", "data"),
            Output("store-entry", "data"),
            Output("store-loaded-event", "data"),
            Output("store-display-controls", "data"),
            Output("store-share-request", "data", allow_duplicate=True),
        ],
        [
            Input("button-load", "n_clicks"),
            Input("store-source-request", "data"),
            Input("input-file-path", "n_submit"),
            Input("button-go", "n_clicks"),
            Input("input-entry", "n_submit"),
            Input("input-run", "n_submit"),
            Input("input-subrun", "n_submit"),
            Input("input-event", "n_submit"),
            Input("button-previous", "n_clicks"),
            Input("button-next", "n_clicks"),
            Input("dropdown-attr-color", "value"),
            Input("store-appearance-render-request", "data"),
            Input("store-filter-render-request", "data"),
            Input("renderer-toggle", "value"),
            Input("radio-run-mode", "value"),
            Input("radio-truth-point-mode", "value"),
            Input("radio-object-mode", "value"),
            Input("dropdown-geo", "value"),
            Input("dropdown-geo-tag", "value"),
            Input("store-dropdown-commit", "data"),
            Input("checklist-draw-mode-1", "value"),
            Input("radio-flash-mode", "value"),
            Input("radio-crt-mode", "value"),
            Input("checklist-draw-mode-2", "value"),
            Input("store-share-pending", "data"),
        ],
        [
            State("store-object-filter", "data"),
            State("input-file-path", "value"),
            State("source-mode", "value"),
            State("input-entry", "value"),
            State("input-run", "value"),
            State("input-subrun", "value"),
            State("input-event", "value"),
            State("entry-mode", "value"),
            State("theme-toggle", "value"),
            State("dropdown-attr", "value"),
            State("store-geometry-choice", "data"),
            State("store-entry", "data"),
            State("store-loaded-event", "data"),
            State("store-display-controls", "data"),
            State("store-share-applied", "data"),
            State("checklist-show-axes", "value"),
            State("dropdown-colorscale", "value"),
            State("input-point-size", "value"),
            State("input-point-opacity", "value"),
            State("radio-color-transform", "value"),
            State("radio-color-domain", "value"),
            State("input-color-min", "value"),
            State("input-color-max", "value"),
            State("radio-visible-range", "value"),
            State("input-visible-min", "value"),
            State("input-visible-max", "value"),
        ],
        prevent_initial_call=True,
    )
    def update_graph(
        n_clicks_load,
        source_request,
        n_submit_source,
        n_clicks_go,
        n_submit_entry,
        n_submit_run,
        n_submit_subrun,
        n_submit_event,
        n_clicks_prev,
        n_clicks_next,
        draw_attr,
        appearance_render_request,
        filter_render_request,
        renderer,
        mode,
        truth_point_mode,
        obj,
        detector,
        detector_tag,
        dropdown_commit,
        core_draw_modes,
        flash_mode,
        crt_mode,
        draw_mode_2,
        share_pending,
        object_filter,
        file_path,
        source_mode,
        entry,
        run,
        subrun,
        event,
        entry_mode,
        theme,
        attrs,
        geometry_choice,
        entry_state,
        loaded_event,
        previous_control_state,
        share_applied,
        axes,
        colorscale,
        point_size,
        point_opacity,
        color_transform,
        color_domain_mode,
        color_min,
        color_max,
        visible_range_mode,
        visible_min,
        visible_max,
    ):
        """Callback which builds the graph given all the selections.

        Parameters
        ----------
        n_clicks_load : int
            Number of time the load button has been clicked
        source_request : dict, optional
            Uploaded source path and mode to open atomically.
        n_submit_source : int
            Number of times Return has been pressed in the source field
        n_clicks_go : int
            Number of times direct event navigation has been requested
        n_submit_entry : int
            Number of times Return has been pressed in the entry field
        n_submit_run : int
            Number of times Return has been pressed in the run field
        n_submit_subrun : int
            Number of times Return has been pressed in the subrun field
        n_submit_event : int
            Number of times Return has been pressed in the event field
        n_clicks_prev : int
            Number of time the previous button has been clicked
        n_clicks_next : int
            Number of time the next button has been clicked
        draw_attr : str
            Attribute to use to fetch the colorscale
        appearance_render_request : dict, optional
            Browser revision requesting a Plotly appearance redraw.
        filter_render_request : dict, optional
            Revision emitted when object filtering requires a server render.
        object_filter : List[str]
            Event-local object positions selected to show
        renderer : List[str]
            Checked renderer-switch value. An empty list selects WebGL and
            ``["plotly"]`` selects Plotly.
        mode : str
            Drawer run mode ('reco', 'truth' or 'both')
        truth_point_mode : str
            Truth point source (label, adapted or Geant4 points).
        obj : str
            Objects to be drawn ('fragments', 'particles' or 'interactions')
        detector : str
            Detector name
        detector_tag : str
            Detector tag
        dropdown_commit : dict
            Browser-side notification that a multi-select menu was closed.
        file_path : str
            Path to the input file
        source_mode : str
            Source mode used to open the input file.
        entry : int
            Entry number
        entry_prev : int
            Previous entry number
        run : int
            Run number
        subrun : int
            Subrun number
        event : int
            Event number
        entry_mode : str
            Event locator mode, either ``"entry"`` or ``"run"``.
        attrs : List[str]
            List of attributes to draw in the graph
        draw_mode_1 : List[str]
            Optional scene overlays.
        draw_mode_2 : List[str]
            Scene layout and camera options.
        geometry_choice : str
            Whether file geometry is automatic, manually selected or disabled.
        entry_state : dict, optional
            Previously loaded file and its embedded geometry configuration.
        loaded_event : dict, optional
            File and event coordinates of the scene currently displayed.
        previous_control_state : dict, optional
            Last file-dependent display-control configuration sent to Dash.
        share_pending : dict, optional
            Shared-view restoration currently being reflected into the controls.
        share_applied : dict, optional
            Most recently completed shared-view restoration.
        axes : List[str]
            Checked axis-visibility option. An empty list hides all axes.

        Returns
        -------
        dcc.Graph
            Dash graph containing the event display(s)
        int
            Entry number currently loaded in the graph
        int
            Run number currently loaded in the graph
        int
            Subrun number currently loaded in the graph
        int
            Event number currently loaded in the graph
        str
            Message to be displayed in the text area
        list
            Available object-filter options
        list
            Active object-filter values
        """
        # If one of the button is yet to be pressed, supress update
        trigger = ctx.triggered_id
        if trigger is None:
            return (no_update,) * 17

        # An uploaded source must carry its path and mode in the triggering
        # payload. Reading them back from separately updated controls races
        # Dash's client-side state propagation on the first Browse selection.
        if trigger == "store-source-request":
            if not source_request:
                return (no_update,) * 17
            file_path = source_request.get("file_path")
            source_mode = source_request.get("source_mode", source_mode)

        restoring_view = False
        share_request_output = no_update
        restored_state = None

        # A URL share request already contains the referenced data source and
        # entry. Treat the pending state as an atomic source-open trigger; the
        # controls and camera are reflected only after this render succeeds.
        if trigger == "store-share-pending":
            if not share_pending:
                return (no_update,) * 17
            restored_state = dict(share_pending)
            file_path = restored_state.get("file")
            entry = restored_state.get("entry")
            source_mode = (
                "url"
                if (file_path or "").startswith(("http://", "https://"))
                else "path"
            )
            entry_mode = "entry"

        use_run = entry_mode == "run"
        draw_mode_1 = compose_draw_modes(core_draw_modes, flash_mode, crt_mode)

        # Display controls always redraw the event currently on screen. Draft
        # edits in the file and entry fields remain inactive until Load is used.
        if trigger in AUTO_REFRESH_TRIGGERS:
            pending_restore = (share_pending or {}).get("restore_id")
            applied_restore = (share_applied or {}).get("restore_id")
            if pending_restore and pending_restore != applied_restore:
                return (no_update,) * 17
            if not loaded_event:
                return (no_update,) * 17
            file_path = loaded_event["file_path"]
            entry = loaded_event["entry"]
            run = loaded_event.get("run")
            subrun = loaded_event.get("subrun")
            event = loaded_event.get("event")
            use_run = loaded_event.get("use_run", use_run)

        # Browse identifies the file used to import data or a saved view. Once
        # an event is open, navigation must follow that event's resolved HDF5
        # source rather than re-opening the uploaded JSON document.
        file_path = navigation_file_path(file_path, source_mode, trigger, loaded_event)

        # Updating store-entry reflects automatic file geometry into the two
        # dropdowns. Those programmatic value changes do not require another
        # scene build; the navigation callback already drew that geometry.
        if trigger in {"dropdown-geo", "dropdown-geo-tag"} and (
            geometry_choice == "auto"
            and is_embedded_geometry_selection(detector, detector_tag, entry_state)
        ):
            return (no_update,) * 17

        # A cleared detector is an explicit opt-out even if the client-side
        # geometry-choice store has not propagated its update yet.
        if trigger == "dropdown-geo":
            geometry_choice = "disabled" if detector is None else "manual"
        elif trigger == "dropdown-geo-tag":
            geometry_choice = "manual"

        # The header switch stores only its checked Plotly state; unchecked is WebGL
        renderer = "plotly" if "plotly" in (renderer or []) else "webgl"

        # Point-only object visibility is updated directly in the existing
        # browser-side WebGL traces without touching the server data pipeline
        dependent_modes = (
            FILTER_DEPENDENT_DRAW_MODES
            if renderer == "webgl"
            else PLOTLY_FILTER_DEPENDENT_DRAW_MODES
        )
        fast_filter = renderer == "webgl" and not dependent_modes.intersection(
            draw_mode_1 or []
        )
        if trigger == "dropdown-attr-color":
            return (no_update,) * 17

        # Initialize the reader (throw if the file is not specified/found)
        skip = (no_update,) * 5

        def fail(message):
            return (
                *skip,
                message,
                no_update,
                "log-panel has-error",
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
            )

        if file_path is None or len(file_path) == 0:
            msg = "Must specify a file path..."
            return fail(msg)

        # Validate file access based on authentication
        is_valid, error_msg = validate_file_access(file_path)
        if not is_valid:
            return fail(error_msg)

        # Dispatch exact files by content, not extension. URL sources are
        # materialized into the private cache before applying the same rules.
        try:
            source_kind, resolved_source = classify_source(file_path)
        except (OSError, ValueError) as error:
            return fail(f"Could not open source:\n" f"{type(error).__name__}: {error}")
        # Resolve an imported JSON view and its referenced data source in this
        # same callback. URL shares arrive above as an already-decoded state.
        if trigger in SOURCE_OPEN_TRIGGERS and source_kind == "json":
            try:
                state = load_view_state(resolved_source)
            except (OSError, ValueError) as error:
                return fail(
                    f"Could not load shared view:\n" f"{type(error).__name__}: {error}"
                )
            state = dict(state)
            state["import_mode"] = source_mode
            restored_state = state
            share_request_output = state

            file_path = state["file"]
            is_valid, error_msg = validate_file_access(file_path)
            if not is_valid:
                return fail(error_msg)
            try:
                source_kind, resolved_source = classify_source(file_path)
            except (OSError, ValueError) as error:
                return fail(
                    f"Could not open shared-view source:\n"
                    f"{type(error).__name__}: {error}"
                )
            if source_kind == "json":
                return fail("A shared view cannot reference another shared view.")

        if restored_state is not None:
            restoring_view = True
            display_state = restored_state.get("display") or {}
            attribute_state = restored_state.get("attributes") or {}
            geometry_state = restored_state.get("geometry") or {"mode": "auto"}
            overlays = display_state.get("overlays") or []

            file_path = restored_state["file"]
            entry = restored_state["entry"]
            entry_mode = "entry"
            use_run = False
            renderer = (
                "plotly" if restored_state.get("renderer") == "plotly" else "webgl"
            )
            mode = display_state.get("run_mode", "reco")
            truth_point_mode = display_state.get("truth_points", "points")
            obj = display_state.get("object", "particles")
            core_draw_modes = [value for value in overlays if value in CORE_DRAW_MODES]
            flash_mode = (
                "matched"
                if "flash_match_only" in overlays
                else ("all" if "flash" in overlays else "off")
            )
            crt_mode = (
                "matched"
                if "crt_match_only" in overlays
                else ("all" if "crt" in overlays else "off")
            )
            draw_mode_1 = compose_draw_modes(core_draw_modes, flash_mode, crt_mode)
            draw_mode_2 = display_state.get("view") or ["split_scene", "sync"]
            axes = ["axes"] if display_state.get("axes", True) else []
            attrs = attribute_state.get("hover") or []
            draw_attr = attribute_state.get("color") or None
            colorscale = attribute_state.get("colorscale") or "Inferno"
            appearance_state = attribute_state.get("appearance") or {}
            point_size = appearance_state.get("point_size", 1.0)
            point_opacity = appearance_state.get("opacity", 1.0)
            color_transform = appearance_state.get("transform", "linear")
            color_domain_mode = appearance_state.get("domain_mode", "auto")
            color_min = appearance_state.get("color_min")
            color_max = appearance_state.get("color_max")
            visible_range_mode = appearance_state.get("range_mode", "all")
            visible_min = appearance_state.get("visible_min")
            visible_max = appearance_state.get("visible_max")
            geometry_choice = geometry_state.get("mode", "auto")
            detector = geometry_state.get("detector")
            detector_tag = geometry_state.get("tag")

            # The values above come from the imported view rather than the
            # controls that triggered this callback. Recompute the filtering
            # strategy from those restored values before drawing the scene.
            dependent_modes = (
                FILTER_DEPENDENT_DRAW_MODES
                if renderer == "webgl"
                else PLOTLY_FILTER_DEPENDENT_DRAW_MODES
            )
            fast_filter = renderer == "webgl" and not dependent_modes.intersection(
                draw_mode_1 or []
            )

            if source_kind == "json":
                return fail("A shared view cannot reference another shared view.")

        if source_kind == "manifest":
            is_valid, error_msg = validate_manifest_access(resolved_source)
            if not is_valid:
                return fail(error_msg)

        try:
            entry = parse_optional_int(entry)
            run = parse_optional_int(run)
            subrun = parse_optional_int(subrun)
            event = parse_optional_int(event)
        except (TypeError, ValueError):
            return fail("Entry, run, subrun and event values must be integers")

        else:
            try:
                reader = initialize_reader(file_path, use_run)
                msg = f"File(s) found with {len(reader)} entries"
            except FileNotFoundError:
                msg = f"File(s) not found:\n{file_path}"
                return fail(msg)
            except Exception as e:
                msg = repr(e)
                return fail(msg)

        # Check that the appropriate information is provided, abort otherwise
        if not use_run and entry is None:
            msg += "\nMust provide an entry number"
            return fail(msg)

        elif use_run and (run is None or subrun is None or event is None):
            msg += "\nMust provide run, subrun and event numbers"
            return fail(msg)

        # If using the run info, translate the triplet to an entry number
        if use_run:
            try:
                entry = reader.get_run_event_index(run, subrun, event)
            except (AssertionError, KeyError):
                msg += (
                    "\nCould not load requested event: "
                    f"(run={run}, subrun={subrun}, event={event}) was not found."
                )
                return fail(msg)

        # Update the entry number of the previous/next button was pressed
        # Supress updates entirely if we are out of range
        if "previous" in trigger:
            if entry == 0:
                return *skip, *(no_update,) * 12
            entry -= 1

        elif "next" in trigger:
            if entry >= len(reader) - 1:
                return *skip, *(no_update,) * 12
            entry += 1

        # Check on the entry number
        if entry >= len(reader):
            msg += f"\nEntry {entry} not found in file(s) provided"
            return fail(msg)

        msg += f"\nLoaded entry {entry}"

        # Resolve file capabilities before asking SPINE to build the selected
        # object family. This lets truth-only and partial files recover from a
        # stale UI selection on their very first load.
        try:
            products = get_reader_products(reader)
            control_state = display_control_state(
                products,
                mode,
                obj,
                draw_mode_1,
                truth_point_mode,
            )
            (
                run_options,
                mode,
                object_options,
                obj,
                draw_options,
                draw_mode_1,
            ) = control_state
            data, geo, run, subrun, event = load_data(reader, entry, mode, obj)
            requested_truth_point_mode = truth_point_mode
            (
                truth_point_options,
                truth_point_mode,
                truth_point_style,
            ) = truth_point_control_state(data, mode, obj, truth_point_mode)
            if truth_point_mode != requested_truth_point_mode:
                (
                    run_options,
                    mode,
                    object_options,
                    obj,
                    draw_options,
                    draw_mode_1,
                ) = display_control_state(
                    products, mode, obj, draw_mode_1, truth_point_mode
                )
        except Exception as error:
            return fail(
                f"Could not load the selected event:\n"
                f"{type(error).__name__}: {error}"
            )
        if run is not None:
            msg += f"\nRun: {run}, subrun: {subrun}, event: {event}"

        # An explicit geometry opt-out is scoped to the currently loaded file.
        # Changing files restores automatic detection and ignores the old selector.
        if restoring_view:
            canonical_path = canonicalize_data_path(file_path)
            file_changed = False
        else:
            canonical_path, geometry_choice, file_changed = geometry_choice_for_file(
                file_path, entry_state, geometry_choice
            )
        if file_changed:
            detector = None
            detector_tag = None

        # Build filter controls from the complete event before restricting objects
        reco_options = (
            build_object_filter_options(data, "reco", obj) if mode != "truth" else []
        )
        truth_options = (
            build_object_filter_options(data, "truth", obj) if mode != "reco" else []
        )
        all_reco = [option["value"] for option in reco_options]
        all_truth = [option["value"] for option in truth_options]
        all_objects = all_reco + all_truth

        # Select every object by default when navigating to another event
        active_filter = (
            all_objects if trigger in FILTER_RESET_TRIGGERS else (object_filter or [])
        )
        filtered_data, visible_count, total_count = filter_event_objects(
            data, mode, obj, active_filter
        )
        if visible_count < total_count:
            msg += f"\nShowing {visible_count} of {total_count} {obj}"

        # Automatic file geometry is used only until the user explicitly clears it
        configure_geometry(detector, detector_tag, geo, geometry_choice)

        # Intialize the drawer, fetch plot
        draw_mode = (draw_mode_1 or []) + (draw_mode_2 or [])
        appearance = {
            "point_size": min(3.0, max(0.5, float(point_size or 1.0))),
            "opacity": min(
                1.0,
                max(0.1, float(point_opacity if point_opacity is not None else 1.0)),
            ),
            "colorscale": colorscale or "Inferno",
            "transform": color_transform or "linear",
            "domain_mode": color_domain_mode or "auto",
            "color_min": color_min,
            "color_max": color_max,
            "range_mode": visible_range_mode or "all",
            "visible_min": visible_min,
            "visible_max": visible_max,
        }
        # Dependent glyphs still require a server render; point-only filtering
        # retains the complete buffers for instantaneous client-side updates
        draw_data = data if fast_filter else filtered_data
        drawer = Drawer(
            draw_data,
            draw_mode=mode,
            truth_point_mode=truth_point_mode,
            truth_dep_mode=TRUTH_POINT_MODES[truth_point_mode]["dep_mode"],
            split_scene="split_scene" in draw_mode,
            dark="dark" in (theme or []),
        )

        # Drop selections that do not apply after changing object or run mode.
        valid_attrs = set(object_attributes(mode, obj, truth_point_mode))
        attrs = [attr for attr in (attrs or []) if attr in valid_attrs] or None
        if draw_attr not in (attrs or []):
            draw_attr = None

        # Raw mode temporarily colors object points by their point-wise
        # depositions. The raw trace remains underneath for unassigned points,
        # while the coincident object trace supplies instance-aware hover. Keep
        # the user's selected color attribute untouched so it is restored when
        # Raw is disabled.
        effective_color_attr = draw_attr
        render_attrs = attrs
        if "raw" in draw_mode and "depositions" in valid_attrs:
            effective_color_attr = "depositions"
            render_attrs = list(dict.fromkeys([*(attrs or []), "depositions"]))

        # Render failures remain visible in production mode through the log.
        try:
            scene = drawer.get_scene(
                obj,
                render_attrs,
                color_attr=effective_color_attr,
                draw_raw="raw" in draw_mode,
                draw_end_points="point" in draw_mode,
                draw_directions="direction" in draw_mode,
                draw_vertices="vertex" in draw_mode,
                draw_flashes="flash" in draw_mode,
                matched_flash_only="flash_match_only" in draw_mode,
                draw_crthits="crt" in draw_mode,
                matched_crthit_only="crt_match_only" in draw_mode,
            )
            continuous_layers = apply_continuous_colorscale(
                scene, colorscale or "Inferno"
            )
            up_key = ",".join(f"{value:g}" for value in scene.metadata["up_dir"])
            camera_key = f"{canonical_path}:{entry}:{up_key}"
            if renderer == "webgl":
                token = scene_store.put(scene)
                display = html.Div(
                    id="webgl-viewer",
                    className="webgl-viewer",
                    **{
                        "data-scene-url": f"/scene/{token}.bin",
                        "data-dark": str("dark" in (theme or [])).lower(),
                        "data-selection": ",".join(active_filter),
                        "data-color-attribute": effective_color_attr or "",
                        "data-filter-enabled": str(fast_filter).lower(),
                        "data-sync-cameras": str("sync" in draw_mode).lower(),
                        "data-show-axes": str("axes" in (axes or [])).lower(),
                        "data-camera-key": camera_key,
                        "data-appearance": json.dumps(appearance),
                    },
                )
            else:
                figure = drawer.get(
                    obj,
                    render_attrs,
                    color_attr=effective_color_attr,
                    draw_raw="raw" in draw_mode,
                    draw_end_points="point" in draw_mode,
                    draw_directions="direction" in draw_mode,
                    draw_vertices="vertex" in draw_mode,
                    draw_flashes="flash" in draw_mode,
                    matched_flash_only="flash_match_only" in draw_mode,
                    draw_crthits="crt" in draw_mode,
                    matched_crthit_only="crt_match_only" in draw_mode,
                    synchronize=False,
                    split_traces=False,
                )
                apply_plotly_colorscale(
                    figure, colorscale or "Inferno", continuous_layers
                )
                apply_plotly_appearance(figure, continuous_layers, appearance)
                attach_object_filter_metadata(
                    figure,
                    scene,
                    revision=uuid.uuid4().hex,
                    selection=active_filter,
                )
                figure.update_layout(
                    width=None,
                    height=None,
                    showlegend=False,
                    uirevision=camera_key,
                )
                figure.update_scenes(
                    xaxis_visible="axes" in (axes or []),
                    yaxis_visible="axes" in (axes or []),
                    zaxis_visible="axes" in (axes or []),
                )
                display = dcc.Graph(
                    figure=figure,
                    id="graph-evd",
                    className="event-graph",
                    config=GRAPH_CONFIG,
                )
        except Exception as error:
            return fail(
                f"Could not draw {mode} {obj}:\n" f"{type(error).__name__}: {error}"
            )

        meta = [
            html.Span(format_entry_label(entry, len(reader)), className="meta-chip"),
        ]
        if run is not None:
            meta.extend(
                [
                    html.Span(f"Run {run}", className="meta-chip"),
                    html.Span(f"Subrun {subrun}", className="meta-chip"),
                    html.Span(f"Event {event}", className="meta-chip"),
                ]
            )

        filter_update = trigger != "store-filter-render-request"
        from .cache import cache_manager

        temporary_source = cache_manager.owns_path(file_path)
        control_payload = {
            "run_options": run_options,
            "run_value": mode,
            "object_options": object_options,
            "object_value": obj,
            "draw_options": draw_options,
            "draw_value": draw_mode_1,
            "truth_point_options": truth_point_options,
            "truth_point_value": truth_point_mode,
            "truth_point_style": truth_point_style,
        }

        return (
            display,
            entry,
            run,
            subrun,
            event,
            msg,
            meta,
            "log-panel is-success",
            reco_options if filter_update else no_update,
            (
                [key for key in active_filter if key.startswith("reco:")]
                if filter_update
                else no_update
            ),
            truth_options if filter_update else no_update,
            (
                [key for key in active_filter if key.startswith("truth:")]
                if filter_update
                else no_update
            ),
            (
                (build_object_match_links(data, obj) if mode == "both" else {})
                if filter_update
                else no_update
            ),
            (
                {"file_path": canonical_path, "geometry": geo}
                if geometry_choice == "auto" and detector is None
                else no_update
            ),
            (
                {
                    "file_path": canonical_path,
                    "entry": entry,
                    "run": run,
                    "subrun": subrun,
                    "event": event,
                    "use_run": use_run,
                    "reco_filter": all_reco,
                    "truth_filter": all_truth,
                    "filter_revision": [
                        trigger,
                        n_clicks_load,
                        n_submit_source,
                        n_clicks_go,
                        n_submit_entry,
                        n_submit_run,
                        n_submit_subrun,
                        n_submit_event,
                        n_clicks_prev,
                        n_clicks_next,
                        mode,
                        obj,
                    ],
                    "num_entries": len(reader),
                    "temporary": temporary_source,
                    "navigation_source_mode": (
                        (
                            "url"
                            if canonical_path.startswith(("http://", "https://"))
                            else "path"
                        )
                        if source_mode in {"browse", "upload"}
                        and trigger in EVENT_NAVIGATION_TRIGGERS
                        else None
                    ),
                }
                if trigger in FILTER_RESET_TRIGGERS
                else no_update
            ),
            control_payload if previous_control_state != control_payload else no_update,
            share_request_output,
        )

    @app.callback(
        Output("input-entry", "style"),
        Output("input-run", "style"),
        Output("input-subrun", "style"),
        Output("input-event", "style"),
        Output("input-entry", "disabled"),
        Output("input-run", "disabled"),
        Output("input-subrun", "disabled"),
        Output("input-event", "disabled"),
        Output("entry-mode", "options"),
        Output("button-go", "disabled"),
        Input("entry-mode", "value"),
        Input("store-loaded-event", "data"),
    )
    def update_entry_input(mode, loaded_event):
        """Switch between entry-index and run/event locator fields.

        Parameters
        ----------
        mode : str
            Event locator mode, either ``"entry"`` or ``"run"``.
        loaded_event : dict, optional
            Successfully loaded event state. Navigation remains unavailable
            until this is present.

        Returns
        -------
        str
            Whether to display the entry box or not
        str
            Whether to display the run box or not
        str
            Whether to display the subrun box or not
        str
            Whether to display the event box or not
        bool
            Whether the entry box is disabled or not
        bool
            Whether the run box is disabled or not
        bool
            Whether the subrun box is disabled or not
        bool
            Whether the event box is disabled or not
        list
            Entry-mode options with their availability state
        bool
            Whether the Go button is disabled or not
        """
        entry_on = {
            "display": "block",
            "width": "100%",
            "gridColumn": "1 / -1",
        }
        field_on = {"display": "block", "width": "100%"}
        entry_off = {
            "display": "none",
            "width": "100%",
            "gridColumn": "1 / -1",
        }
        field_off = {"display": "none", "width": "100%"}
        disabled = not bool(loaded_event)
        options = [
            {"label": "Entry", "value": "entry", "disabled": disabled},
            {"label": "Run", "value": "run", "disabled": disabled},
        ]
        if mode == "run":
            return (
                entry_off,
                field_on,
                field_on,
                field_on,
                True,
                disabled,
                disabled,
                disabled,
                options,
                disabled,
            )
        return (
            entry_on,
            field_off,
            field_off,
            field_off,
            disabled,
            True,
            True,
            True,
            options,
            disabled,
        )

    @app.callback(
        Output("input-file-path", "placeholder"),
        Output("input-file-path", "disabled"),
        Output("source-path-row", "style"),
        Output("source-upload-panel", "style"),
        Output("button-load", "style"),
        Input("source-mode", "value"),
    )
    def update_source_mode(mode):
        """Expose only the controls relevant to the selected source mode."""
        hidden = {"display": "none"}
        shown = {"display": "flex"}
        if mode in {"browse", "upload"}:
            return "", True, hidden, {"display": "grid"}, {"display": "block"}
        if mode == "url":
            return (
                "HTTPS URL to HDF5, manifest, or view…",
                False,
                shown,
                hidden,
                {"display": "block"},
            )
        return (
            "HDF5, manifest, or view path…",
            False,
            shown,
            hidden,
            {"display": "block"},
        )

    app.clientside_callback(
        r"""
        function(loadedEvent) {
            if (!loadedEvent || !loadedEvent.file_path) {
                return window.dash_clientside.no_update;
            }

            const file = loadedEvent.file_path;
            const mode = /^https?:\/\//.test(file) ? 'url' : 'path';
            const other = mode === 'url' ? 'path' : 'url';
            const navigationMode = loadedEvent.navigation_source_mode;
            const sourceMemory = window.spinalTapSourceState;
            if (sourceMemory?.values) {
                sourceMemory.values[mode] = file;
                sourceMemory.values[other] = '';
                if (navigationMode) {
                    sourceMemory.active = navigationMode;
                    setTimeout(function() {
                        window.dash_clientside.set_props('source-mode', {
                            value: navigationMode
                        });
                        window.dash_clientside.set_props('input-file-path', {
                            value: file
                        });
                    }, 0);
                } else {
                    const selectedMode = (
                        document.querySelector(
                            '#source-mode input:checked'
                        )?.value || sourceMemory.active
                    );
                    if (['browse', 'upload'].includes(selectedMode) &&
                            sourceMemory.values[selectedMode]) {
                        setTimeout(function() {
                            window.dash_clientside.set_props('input-file-path', {
                                value: sourceMemory.values[selectedMode]
                            });
                        }, 0);
                    }
                }
            }
            return {mode: mode, file: file, revision: Date.now()};
        }
        """,
        Output("store-source-memory", "data"),
        Input("store-loaded-event", "data"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        """
        function(loaded) {
            if (!loaded) return [true, true];
            const entry = Number(loaded.entry || 0);
            const count = Number(loaded.num_entries || 0);
            return [entry <= 0, count <= 0 || entry >= count - 1];
        }
        """,
        Output("button-previous", "disabled"),
        Output("button-next", "disabled"),
        Input("store-loaded-event", "data"),
    )

    app.clientside_callback(
        """
        function(loaded) {
            if (!loaded) return '';
            const source = loaded.file_path || '';
            const label = source.split('/').pop() || source;
            const count = Number(loaded.num_entries || 0);
            return `Opened: ${label} · ${count} ${count === 1 ? 'entry' : 'entries'}`;
        }
        """,
        Output("source-open-summary", "children"),
        Input("store-loaded-event", "data"),
    )

    @app.callback(
        Output("dropdown-attr", "options"),
        Output("dropdown-attr-color", "options"),
        Output("store-attribute-options", "data"),
        Input("radio-run-mode", "value"),
        Input("radio-object-mode", "value"),
        Input("radio-truth-point-mode", "value"),
        Input("input-attribute-search", "value"),
    )
    def update_attribute_options(mode, obj, truth_point_mode, search):
        """Update aligned hover and color choices for the current objects.

        Parameters
        ----------
        mode : str
            Drawer run mode ('reco', 'truth' or 'both').
        obj : str
            Objects to be drawn ('fragments', 'particles' or 'interactions').
        search : str, optional
            Case-insensitive attribute search text.
        Returns
        -------
        tuple[list[dict], list[dict], dict]
            Hidden Dash control options and the aligned visible-row payload.
        """
        hover, color_options = attribute_options(mode, obj, None, truth_point_mode)
        visible_hover, visible_color = attribute_options(
            mode, obj, search, truth_point_mode
        )
        return (
            hover,
            color_options,
            {
                "hover": visible_hover,
                "color": visible_color,
            },
        )
