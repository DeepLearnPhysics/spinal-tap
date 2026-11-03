"""Render credential-free S3DF resources pinned to a tested container digest."""

import argparse
import ast
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def validate_release(tag):
    """Require a stable tag matching the package version and dated release notes."""
    source = ast.parse((ROOT / "src/spinal_tap/version.py").read_text())
    version = next(
        ast.literal_eval(node.value)
        for node in source.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets)
    )
    if not re.fullmatch(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", tag):
        raise ValueError("A stable vMAJOR.MINOR.PATCH release tag is required.")
    if tag != f"v{version}":
        raise ValueError("Release tag must match spinal_tap.version.__version__.")
    if not re.search(
        rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}$",
        (ROOT / "CHANGELOG.md").read_text(),
        re.MULTILINE,
    ):
        raise ValueError("A dated CHANGELOG entry is required.")
    return version


def render_release(image, destination, flavor="larcv"):
    """Preserve S3DF runtime settings while excluding PVCs, Secrets and RBAC."""
    if not re.fullmatch(
        r"ghcr.io/deeplearnphysics/spinal-tap@sha256:[a-f0-9]{64}", image
    ):
        raise ValueError("An immutable spinal-tap image digest is required.")
    if flavor not in ("lean", "larcv"):
        raise ValueError("Image flavor must be lean or larcv.")
    resources = []
    for filename in ("deployment.yaml", "service.yaml", "ingress.yaml"):
        resource = yaml.safe_load((ROOT / "k8s/base" / filename).read_text())
        resource["metadata"]["namespace"] = "spinal-tap"
        if resource["kind"] == "Deployment":
            resource["spec"]["template"]["spec"]["containers"][0]["image"] = image
        elif resource["kind"] == "Ingress":
            # Match the existing S3DF route; do not migrate ingress controllers.
            resource["spec"]["ingressClassName"] = "nginx"
        resources.append(resource)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "release.yaml").write_text(
        yaml.safe_dump_all(resources, sort_keys=False)
    )
    (destination / "kustomization.yaml").write_text(
        "apiVersion: kustomize.config.k8s.io/v1beta1\n"
        "kind: Kustomization\nresources:\n  - release.yaml\n"
    )


def main():
    """Validate a release or render its immutable application bundle."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--tag", required=True)
    render = commands.add_parser("render")
    render.add_argument("--image", required=True)
    render.add_argument("--flavor", choices=["lean", "larcv"], default="larcv")
    render.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "validate":
        print(validate_release(args.tag))
    else:
        render_release(args.image, args.output, args.flavor)


if __name__ == "__main__":
    main()
