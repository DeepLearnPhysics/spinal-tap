"""Check the exact release container without production credentials or data."""

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request


def smoke(image, version, flavor):
    """Verify package/native runtime, anonymous login and logo assets."""
    code = (
        "from spinal_tap.version import __version__; "
        f"assert __version__ == {version!r}, __version__; "
        "import spine"
    )
    if flavor == "larcv":
        code += "; import ROOT; from larcv import larcv"
    subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "python3", image, "-c", code],
        check=True,
        timeout=120,
    )
    container = subprocess.check_output(
        [
            "docker",
            "run",
            "--detach",
            "--publish",
            "127.0.0.1::8888",
            "--env",
            "SPINAL_TAP_AUTH=true",
            image,
        ],
        text=True,
    ).strip()
    try:
        port = (
            subprocess.check_output(
                ["docker", "port", container, "8888/tcp"], text=True
            )
            .strip()
            .rsplit(":", 1)[1]
        )
        origin = f"http://127.0.0.1:{port}"
        for _ in range(90):
            try:
                with urllib.request.urlopen(origin + "/_dash-layout", timeout=3) as r:
                    layout = json.load(r)
                break
            except (OSError, urllib.error.URLError):
                time.sleep(1)
        else:
            raise RuntimeError("Container did not become ready.")
        assert "experiment-select" in json.dumps(layout), "Login form is missing."
        assert version in json.dumps(layout), "Version is missing from login form."
        for path in (
            "/",
            "/assets/spinal-tap-logo-black.png",
            "/assets/spinal-tap-logo-white.png",
        ):
            with urllib.request.urlopen(origin + path, timeout=10) as response:
                assert response.status == 200
                if path.endswith(".png"):
                    assert response.read(8) == b"\x89PNG\r\n\x1a\n"
        print(f"Container smoke checks passed: {flavor} {version}")
    finally:
        subprocess.run(["docker", "rm", "--force", container], check=True)


def main():
    """Run the smoke test for one image variant."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--version", required=True)
    parser.add_argument("--flavor", choices=["lean", "larcv"], required=True)
    args = parser.parse_args()
    smoke(args.image, args.version, args.flavor)


if __name__ == "__main__":
    main()
