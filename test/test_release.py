"""Keep S3DF release bundles immutable and separate from credentials and storage."""

import pytest
import yaml

from scripts import render_release as release


@pytest.mark.parametrize("flavor", ["lean", "larcv"])
def test_release_preserves_runtime_and_excludes_bootstrap(tmp_path, flavor):
    """Only manage the running app and route, preserving data and Secret refs."""
    image = "ghcr.io/deeplearnphysics/spinal-tap@sha256:" + "a" * 64
    release.render_release(image, tmp_path, flavor)
    objects = list(yaml.safe_load_all((tmp_path / "release.yaml").read_text()))
    assert [o["kind"] for o in objects] == ["Deployment", "Service", "Ingress"]
    assert all(o["metadata"]["namespace"] == "spinal-tap" for o in objects)
    pod = objects[0]["spec"]["template"]["spec"]
    container = pod["containers"][0]
    assert container["image"] == image
    assert (
        container["env"]
        == yaml.safe_load((release.ROOT / "k8s/base/deployment.yaml").read_text())[
            "spec"
        ]["template"]["spec"]["containers"][0]["env"]
    )
    assert any(
        v.get("persistentVolumeClaim", {}).get("claimName") == "spinal-tap-data"
        for v in pod["volumes"]
    )
    data = next(v for v in container["volumeMounts"] if v["name"] == "data")
    assert data["readOnly"] is True and data["mountPath"] == "/data"
    assert container["resources"]["limits"]["ephemeral-storage"] == "25Gi"
    assert objects[2]["spec"]["ingressClassName"] == "nginx"
    assert objects[2]["spec"]["rules"][0]["host"] == "spinal-tap.slac.stanford.edu"
    assert yaml.safe_load((tmp_path / "kustomization.yaml").read_text())[
        "resources"
    ] == ["release.yaml"]


@pytest.mark.parametrize(
    "image",
    [
        "ghcr.io/deeplearnphysics/spinal-tap:larcv",
        "ghcr.io/deeplearnphysics/spinal-tap:1.2.3",
        "ghcr.io/other/image@sha256:" + "a" * 64,
    ],
)
def test_mutable_or_unrelated_images_fail(tmp_path, image):
    """Never render a release from moving tags or a different repository."""
    with pytest.raises(ValueError, match="immutable"):
        release.render_release(image, tmp_path)
    assert not list(tmp_path.iterdir())


def test_unknown_flavor_fails(tmp_path):
    """Prevent a misspelled flavor from silently choosing another runtime."""
    with pytest.raises(ValueError, match="flavor"):
        release.render_release(
            "ghcr.io/deeplearnphysics/spinal-tap@sha256:" + "a" * 64,
            tmp_path,
            "unknown",
        )


def test_tag_and_changelog_must_match(tmp_path, monkeypatch):
    """Require the package version and release notes to agree before publication."""
    (tmp_path / "src/spinal_tap").mkdir(parents=True)
    (tmp_path / "src/spinal_tap/version.py").write_text('__version__ = "1.2.3"\n')
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("## [1.2.3] - 2026-11-02\n")
    monkeypatch.setattr(release, "ROOT", tmp_path)
    assert release.validate_release("v1.2.3") == "1.2.3"
    with pytest.raises(ValueError, match="match"):
        release.validate_release("v1.2.2")
    with pytest.raises(ValueError, match="stable"):
        release.validate_release("v1.2.3-rc.1")
    changelog.write_text("## [Unreleased]\n")
    with pytest.raises(ValueError, match="dated"):
        release.validate_release("v1.2.3")
