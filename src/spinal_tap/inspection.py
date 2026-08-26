"""Build compact, renderer-independent summaries of SPINE objects."""

from __future__ import annotations

from typing import Any

import numpy as np

__all__ = ["inspect_object", "object_collection_key"]


_GROUPS = {
    "overview": {
        "size",
        "shape",
        "pid",
        "pdg_code",
        "is_primary",
    },
    "identifiers": set(),
    "geometry": {
        "start_point",
        "end_point",
        "vertex",
        "direction",
        "start_dir",
        "end_dir",
        "length",
        "reco_length",
        "distance_travel",
        "units",
    },
    "energy": {
        "depositions_sum",
        "depositions_q_sum",
        "depositions_adapt_sum",
        "depositions_adapt_q_sum",
        "depositions_g4_sum",
        "calo_ke",
        "csda_ke",
        "mcs_ke",
        "energy_init",
        "energy_deposit",
        "ke",
        "reco_ke",
        "mass",
        "p",
        "end_p",
        "momentum",
        "end_momentum",
        "reco_momentum",
        "hadronic_invariant_mass",
        "momentum_transfer",
        "momentum_transfer_mag",
        "energy_transfer",
        "lepton_p",
    },
    "lineage": {
        "parent_pdg_code",
        "ancestor_pdg_code",
        "group_primary",
        "interaction_primary",
        "creation_process",
        "parent_creation_process",
        "ancestor_creation_process",
        "children_counts",
    },
    "timing": {
        "t",
        "end_t",
        "time",
        "first_step_t",
        "last_step_t",
        "parent_t",
        "ancestor_t",
    },
    "detector_matching": set(),
    "interaction_physics": {
        "current_type",
        "interaction_scheme",
        "interaction_mode",
        "interaction_type",
        "target",
        "nucleon",
        "quark",
        "theta",
        "bjorken_x",
        "inelasticity",
        "topology",
    },
    "matching": {
        "is_matched",
        "match_ids",
        "match_overlaps",
        "best_match_id",
        "best_match_overlap",
    },
}


def _attribute_group(obj: Any, name: str) -> str:
    """Return the semantic inspector group for one SPINE attribute."""
    explicit = next(
        (
            group
            for group, attributes in _GROUPS.items()
            if name in attributes and group != "identifiers"
        ),
        None,
    )
    if explicit is not None:
        return explicit
    if name.startswith(("crt_", "flash_")) or name in {
        "is_crt_matched",
        "is_flash_matched",
    }:
        return "detector_matching"

    try:
        metadata = obj.attr_metadata(name)
    except AttributeError:
        metadata = None
    is_reference = metadata is not None and (
        getattr(metadata, "index", False)
        or getattr(metadata, "reference", None) is not None
    )
    looks_like_id = name == "id" or name.endswith(("_id", "_ids"))
    if is_reference or looks_like_id:
        return "identifiers"
    if metadata is not None:
        if getattr(metadata, "position", False) or (
            getattr(metadata, "vector", False) and "momentum" not in name
        ):
            return "geometry"
        units = getattr(metadata, "units", None)
        if units in {"MeV", "GeV", "MeV/c", "GeV/c", "MeV/c^2", "GeV/c^2"}:
            return "energy"
        if units in {"ns", "us", "s"}:
            return "timing"
    return "details"


def object_collection_key(prefix: str, family: str) -> str:
    """Return the event-product key for one inspection selection."""
    if prefix not in {"reco", "truth"}:
        raise ValueError(f"Unsupported object prefix: {prefix}")
    if family not in {"fragments", "particles", "interactions"}:
        raise ValueError(f"Unsupported object family: {family}")
    return f"{prefix}_{family}"


def _format_number(value: float) -> str:
    """Format a finite scalar compactly while preserving useful precision."""
    if np.isnan(value):
        return "—"
    if np.isposinf(value):
        return "∞"
    if np.isneginf(value):
        return "−∞"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6g}"


def _format_value(value: Any, enum_values: dict[int, str] | None = None) -> str:
    """Convert one SPINE field value into concise inspector text."""
    if isinstance(value, (bool, np.bool_)):
        return "True" if value else "False"
    if isinstance(value, (int, np.integer)):
        integer = int(value)
        if enum_values and integer in enum_values:
            return f"{enum_values[integer].replace('_', ' ').title()} ({integer})"
        return str(integer)
    if isinstance(value, (float, np.floating)):
        return _format_number(float(value))
    if isinstance(value, str):
        return value or "—"
    if value is None:
        return "—"

    array = np.asarray(value)
    if array.ndim == 0:
        return _format_value(array.item(), enum_values)
    if array.size == 0:
        return "—"
    if array.size <= 8:
        values = ", ".join(_format_value(item) for item in array.reshape(-1))
        return f"[{values}]"
    if array.dtype.kind in "biuf":
        finite = array.astype(float, copy=False)
        finite = finite[np.isfinite(finite)]
        if len(finite):
            return (
                f"{array.shape[0]} values · "
                f"{_format_number(float(np.min(finite)))}–"
                f"{_format_number(float(np.max(finite)))}"
            )
    return f"{array.shape[0]} values"


def _label(name: str) -> str:
    """Turn a Python attribute name into a compact human-readable label."""
    return name.replace("_", " ").capitalize()


def inspect_object(obj: Any, prefix: str, family: str, position: int) -> dict:
    """Return a grouped, JSON-friendly summary of one output object.

    Point-wise arrays are intentionally omitted by ``as_dict``. Their useful
    aggregates remain available through stored properties such as ``size`` and
    ``depositions_sum``, keeping the inspector informative without shipping
    thousands of values to the browser.
    """
    values = obj.as_dict() if hasattr(obj, "as_dict") else vars(obj)
    enum_values = getattr(obj, "enum_values", {})
    units = getattr(obj, "field_units", {})
    grouped = {name: [] for name in (*_GROUPS, "details")}

    for name, value in values.items():
        if name.startswith("_"):
            continue
        group = _attribute_group(obj, name)
        text = _format_value(value, enum_values.get(name))
        unit = units.get(name)
        if unit and text != "—":
            text = f"{text} {unit}"
        grouped[group].append({"name": name, "label": _label(name), "value": text})

    object_id = getattr(obj, "id", position)
    singular = family[:-1].capitalize()
    return {
        "key": f"{prefix}:{position}",
        "prefix": prefix,
        "family": family,
        "position": position,
        "object_id": int(object_id),
        "title": f"{prefix.capitalize()} {singular} {object_id}",
        "groups": {name: rows for name, rows in grouped.items() if rows},
    }
