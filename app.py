#!/usr/bin/env python3
"""Spinal tap (reconstruction visualization GUI)."""

import os
import sys
import argparse

from dash import Dash

# Add current directory version of SPINE as source for now
# TODO: get rid of this
current_directory = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_directory+'/spine')

from layout import layout
from callbacks import register_callbacks


if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser()

    parser.add_argument('--port', type=int, default=8888,
                        help="Sets the Flask server port number (default: 8888)")

    parser.add_argument('--host', type=str, default='0.0.0.0',
                        help="Sets the Flask server host address (default: 0.0.0.0)")

    args = parser.parse_args()

    # Initialize the application
    app = Dash(__name__, title='Spinal Tap')

    # Set the application layout
    app.layout = layout

    # Register the callbacks
    register_callbacks(app)

    # Execute the dash app
    app.run_server(host=args.host, port=args.port, debug=True)
