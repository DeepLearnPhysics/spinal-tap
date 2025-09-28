#!/usr/bin/env python3
"""Spinal tap (reconstruction visualization GUI)."""

import argparse

from dash import Dash

from .callbacks import register_callbacks
from .layout import layout

# Import version
from .version import __version__


def main():

    # Parse command line arguments
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Show the Spinal Tap version and exit."
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

    # Initialize the application
    app = Dash(__name__, title="Spinal Tap")

    # Set the application layout
    app.layout = layout

    # Register the callbacks
    register_callbacks(app)

    # Execute the dash app
    app.run(host=args.host, port=args.port, debug=True)


if __name__ == "__main__":
    main()
