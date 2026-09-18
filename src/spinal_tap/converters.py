"""Discover and resolve versioned spine-prod LArCV conversion bundles."""

import os
from collections import Counter
from pathlib import Path

import yaml


def _converter_tags(path: Path, roots: list[Path]) -> list[str]:
    """Read display tags, falling back through the converter's includes."""

    def collect(config_path: Path, visited: set[Path]) -> list[str]:
        config_path = config_path.resolve()
        if config_path in visited:
            return []
        visited.add(config_path)

        try:
            config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return []

        tags = config.get("__meta__", {}).get("tags") or []
        if tags:
            return [str(tag) for tag in tags]

        includes = config.get("include") or []
        if isinstance(includes, str):
            includes = [includes]

        inherited = []
        for include in includes:
            candidates = [config_path.parent / include]
            candidates.extend(root / include for root in roots)
            include_path = next(
                (candidate for candidate in candidates if candidate.is_file()), None
            )
            if include_path is not None:
                inherited.extend(collect(include_path, visited))

        return list(dict.fromkeys(inherited))

    return collect(path, set())


def _config_roots() -> list[Path]:
    """Return configured SPINE configuration roots in lookup order."""
    configured = os.getenv("SPINAL_TAP_LARCV_CONFIG_ROOT") or os.getenv(
        "SPINE_CONFIG_PATH", ""
    )
    return [Path(path).expanduser() for path in configured.split(os.pathsep) if path]


def available_larcv_converters() -> list[dict[str, str]]:
    """Return Dash options for all installed dated truth-conversion bundles."""
    roots = _config_roots()
    converters: dict[str, Path] = {}
    for root in roots:
        convert_root = root / "convert"
        if not convert_root.is_dir():
            continue
        for path in convert_root.glob("*/truth_*.yaml"):
            converter_id = f"{path.parent.name}/{path.stem}"
            converters.setdefault(converter_id, path)

    detector_counts = Counter(
        converter_id.split("/", 1)[0] for converter_id in converters
    )
    options = []
    for converter_id, path in sorted(converters.items()):
        detector = converter_id.split("/", 1)[0]
        label = f"{detector} · {path.stem}"
        if detector_counts[detector] > 1:
            tags = _converter_tags(path, roots)
            if tags:
                label += f" · {', '.join(tags)}"
        options.append({"label": label, "value": converter_id})

    return options


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
