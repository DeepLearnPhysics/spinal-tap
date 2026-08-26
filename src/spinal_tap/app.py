#!/usr/bin/env python3
"""Spinal Tap (reconstruction visualization GUI)."""

import argparse
import hashlib
import json
import logging
import os
import secrets
from pathlib import Path

from dash import Dash
from flask import Flask, Response, abort, jsonify, redirect, request, session
from werkzeug.serving import run_simple

from .callbacks import register_callbacks
from .layout import get_layout
from .scene import scene_store
from .version import __version__

# Authentication configuration
REQUIRE_AUTH = os.getenv("SPINAL_TAP_AUTH", "false").lower() == "true"

# Shared folders accessible to all authenticated users (comma-separated)
SHARED_FOLDERS = [
    folder.strip()
    for folder in os.getenv(
        "SPINAL_TAP_SHARED_FOLDERS", "/data/generic,/data/public_html"
    ).split(",")
    if folder.strip()
]

# Experiment password hashes (only used if REQUIRE_AUTH is True)
# Store SHA256 hashes of passwords, not plain text
EXPERIMENT_PASSWORDS = {
    "public": os.getenv("PASSWORD_PUBLIC", ""),
    "dune": os.getenv("PASSWORD_DUNE", ""),
    "icarus": os.getenv("PASSWORD_ICARUS", ""),
    "sbnd": os.getenv("PASSWORD_SBND", ""),
}

# Map experiments to their accessible data folders
EXPERIMENT_PATHS = {
    "public": [],
    "dune": ["/data/2x2", "/data/ndlar", "/data/dune", "/data/pdune"],
    "icarus": ["/data/icarus"],
    "sbnd": ["/data/sbnd"],
}


def hash_password(password):
    """Hash a password using SHA256.

    Parameters
    ----------
    password : str
        The plain text password to hash.

    Returns
    -------
    str
        The SHA256 hash of the password.
    """
    return hashlib.sha256(password.encode()).hexdigest()


def check_password(experiment, password):
    """Check if password matches for the given experiment.

    Parameters
    ----------
    experiment : str
        The experiment name.
    password : str
        The plain text password to check.

    Returns
    -------
    bool
        True if the password is correct or authentication is not required,
        False otherwise.
    """
    if not REQUIRE_AUTH:
        return True

    stored_hash = EXPERIMENT_PASSWORDS.get(experiment, "")
    if not stored_hash:
        return False

    return hash_password(password) == stored_hash


def get_experiment():
    """Get the current user's experiment from session.

    Returns
    -------
    str or None
        The experiment name if authenticated, None otherwise.
        If REQUIRE_AUTH is False, returns None (no restrictions).
    """
    if not REQUIRE_AUTH:
        return None

    try:
        return session.get("experiment") if session.get("authenticated") else None
    except RuntimeError:
        # Not in request context
        return None


def is_authenticated():
    """Check if the user is authenticated.

    Returns
    -------
    bool
        True if the user is authenticated or authentication is not required,
        False otherwise.
    """
    if not REQUIRE_AUTH:
        return True

    # Check if we're in a request context
    try:
        return session.get("authenticated", False)
    except RuntimeError:
        # Not in request context (e.g., during app initialization)
        return False


def register_scene_routes(server):
    """Register the compact renderer-neutral scene download endpoint."""

    @server.route("/scene/<token>.bin")
    def get_scene(token):
        """Return one compact renderer-neutral scene payload."""
        payload = scene_store.get(token)
        if payload is None:
            abort(404)
        return Response(
            payload,
            mimetype="application/octet-stream",
            headers={"Cache-Control": "private, max-age=300"},
        )


def register_source_routes(server):
    """Register bounded temporary-upload endpoints."""
    from .cache import cache_manager

    def upload_error(error, status=400):
        """Return one consistent JSON upload error response."""
        return jsonify({"error": str(error)}), status

    @server.post("/api/uploads")
    def begin_upload():
        """Allocate a private, session-scoped temporary upload."""
        if not is_authenticated():
            return upload_error("Authentication required.", 401)
        payload = request.get_json(silent=True) or {}
        try:
            result = cache_manager.begin_upload(
                payload.get("name", ""), int(payload.get("size", 0))
            )
        except PermissionError as error:
            return upload_error(error, 403)
        except (TypeError, ValueError, OSError) as error:
            return upload_error(error)
        return jsonify(result), 201

    @server.put("/api/uploads/<upload_id>/<int:index>")
    def upload_chunk(upload_id, index):
        """Store one independently retryable upload chunk."""
        if not is_authenticated():
            return upload_error("Authentication required.", 401)
        if (
            request.content_length is None
            or request.content_length > cache_manager.max_chunk_bytes
        ):
            return upload_error("Upload chunk is missing or too large.", 413)
        try:
            result = cache_manager.write_chunk(
                upload_id,
                request.headers.get("X-Upload-Token", ""),
                index,
                request.get_data(cache=False),
            )
        except PermissionError as error:
            return upload_error(error, 403)
        except (ValueError, OSError) as error:
            return upload_error(error)
        return jsonify(result)

    @server.post("/api/uploads/<upload_id>/complete")
    def complete_upload(upload_id):
        """Validate and publish a completed temporary source."""
        if not is_authenticated():
            return upload_error("Authentication required.", 401)
        try:
            result = cache_manager.finish_upload(
                upload_id, request.headers.get("X-Upload-Token", "")
            )
        except PermissionError as error:
            return upload_error(error, 403)
        except (ValueError, OSError, json.JSONDecodeError) as error:
            return upload_error(error)
        return jsonify(result)

    @server.delete("/api/uploads/<upload_id>")
    def cancel_upload(upload_id):
        """Discard a private incomplete upload."""
        if not is_authenticated():
            return upload_error("Authentication required.", 401)
        try:
            cache_manager.cancel_upload(
                upload_id, request.headers.get("X-Upload-Token", "")
            )
        except PermissionError as error:
            return upload_error(error, 403)
        return "", 204


def create_app(server=None):
    """Create and configure the Flask-backed Dash application."""
    if server is None:
        server = Flask(__name__)
    server.secret_key = server.secret_key or os.getenv(
        "SECRET_KEY", secrets.token_hex(32)
    )

    @server.route("/login", methods=["POST"])
    def login():
        """Handle login requests."""
        experiment = request.form.get("experiment")
        password = request.form.get("password")
        if check_password(experiment, password):
            session["experiment"] = experiment
            session["authenticated"] = True
            return redirect("/")
        return "Invalid credentials", 401

    @server.route("/logout")
    def logout():
        """Handle logout requests."""
        session.clear()
        return redirect("/")

    register_scene_routes(server)
    register_source_routes(server)
    asset_dir = Path(__file__).parent / "assets"
    app = Dash(
        __name__,
        server=server,
        title="Spinal Tap",
        suppress_callback_exceptions=True,
        assets_folder=str(asset_dir),
    )
    app.layout = get_layout
    register_callbacks(app)
    return app


def main():
    """Main entry point for Spinal Tap application."""

    # Parse command line arguments
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--version",
        "-v",
        action="store_true",
        help="Show the Spinal Tap version and exit.",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8888,
        help="Sets the Flask server port number (default: 8888)",
    )

    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Sets the Flask server host address (default: 0.0.0.0)",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable the Dash debugger and development reloader.",
    )

    args = parser.parse_args()

    if args.version:
        print(f"Spinal Tap version {__version__}")
        return

    app = create_app()
    if args.debug:
        app.run(host=args.host, port=args.port, debug=True)
        return

    # Keep the normal CLI focused on the one useful startup URL. Werkzeug's
    # banner and per-request access log are available when debugging is explicit.
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    print(f"Spinal Tap is running on http://{args.host}:{args.port}/")
    run_simple(args.host, args.port, app.server, threaded=True)


if __name__ == "__main__":
    main()
