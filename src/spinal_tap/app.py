#!/usr/bin/env python3
"""Spinal Tap (reconstruction visualization GUI)."""

import argparse
import hashlib
import os
import secrets

from dash import Dash
from flask import Flask, redirect, request, session

from .callbacks import register_callbacks
from .layout import get_layout
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

    args = parser.parse_args()

    if args.version:
        print(f"Spinal Tap version {__version__}")
        return

    # Initialize Flask server with session support
    server = Flask(__name__)
    server.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))

    # Add login endpoint
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

    # Initialize the Dash application with Flask server
    # suppress_callback_exceptions is needed because layout changes dynamically
    # based on authentication state
    app = Dash(
        __name__, server=server, title="Spinal Tap", suppress_callback_exceptions=True
    )

    # Set the application layout (pass function for dynamic evaluation)
    app.layout = get_layout

    # Register the callbacks
    register_callbacks(app)

    # Execute the dash app
    app.run(host=args.host, port=args.port, debug=True)


if __name__ == "__main__":
    main()
