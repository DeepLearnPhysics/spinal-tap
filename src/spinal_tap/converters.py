"""Discover and resolve versioned spine-prod LArCV conversion bundles."""

import os
from pathlib import Path


def _config_roots() -> list[Path]:
    """Return configured SPINE configuration roots in lookup order."""
    configured = os.getenv("SPINAL_TAP_LARCV_CONFIG_ROOT") or os.getenv(
        "SPINE_CONFIG_PATH", ""
    )
    return [Path(path).expanduser() for path in configured.split(os.pathsep) if path]


def available_larcv_converters() -> list[dict[str, str]]:
    """Return Dash options for all installed dated truth-conversion bundles."""
    converters: dict[str, Path] = {}
    for root in _config_roots():
        convert_root = root / "convert"
        if not convert_root.is_dir():
            continue
        for path in convert_root.glob("*/truth_*.yaml"):
            converter_id = f"{path.parent.name}/{path.stem}"
            converters.setdefault(converter_id, path)

    return [
        {
            "label": f"{converter_id.split('/', 1)[0]} · {path.stem}",
            "value": converter_id,
        }
        for converter_id, path in sorted(converters.items())
    ]


def resolve_larcv_converter(value: str) -> str:
    """Resolve a converter ID or explicit YAML path to an installed bundle."""
    candidate = Path(value).expanduser()
    if candidate.is_file():
        return str(candidate.resolve())

    relative = Path("convert") / f"{value.removesuffix('.yaml')}.yaml"
    for root in _config_roots():
        candidate = root / relative
        if candidate.is_file():
            return str(candidate.resolve())

    raise FileNotFoundError(
        f"LArCV converter {value!r} was not found in SPINE_CONFIG_PATH."
    )
