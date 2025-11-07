"""Defines the layout of the Spinal Tap application."""

from dash import dcc, html


def login_form():
    """Generate login form for experiment selection and authentication."""
    return html.Div(
        [
            # Store to hold values for form submission
            dcc.Store(id="login-submit-trigger", data=None),
            # Banner display (matching main app)
            html.Div(
                [
                    html.H2("Spinal Tap", id="title"),
                    html.Img(
                        src=(
                            "https://raw.githubusercontent.com/DeepLearnPhysics/spine/"
                            "main/docs/source/_static/img/spine-logo-dark.png"
                        ),
                        style={"height": "80%", "padding-top": 8},
                    ),
                ],
                className="banner",
            ),
            # Login container (matching main app container style)
            html.Div(
                [
                    html.Div(
                        [
                            html.H3(
                                "Authentication Required",
                                style={
                                    "margin-bottom": "10px",
                                    "color": "#302F54",
                                    "text-align": "center",
                                },
                            ),
                            html.P(
                                "Please select your experiment and enter the password.",
                                style={
                                    "margin-bottom": "30px",
                                    "color": "#302F54",
                                    "text-align": "center",
                                },
                            ),
                            html.Div(
                                [
                                    html.Label(
                                        "Experiment:",
                                        style={
                                            "color": "#302F54",
                                            "font-weight": "bold",
                                        },
                                    ),
                                    dcc.Dropdown(
                                        id="experiment-select",
                                        options=[
                                            {"label": "DUNE", "value": "dune"},
                                            {"label": "ICARUS", "value": "icarus"},
                                            {"label": "SBND", "value": "sbnd"},
                                        ],
                                        placeholder="Select experiment",
                                        style={"margin-bottom": "20px"},
                                    ),
                                ],
                            ),
                            html.Div(
                                [
                                    html.Label(
                                        "Password:",
                                        style={
                                            "color": "#302F54",
                                            "font-weight": "bold",
                                        },
                                    ),
                                    dcc.Input(
                                        id="password-input",
                                        type="password",
                                        placeholder="Enter password",
                                        style={
                                            "width": "100%",
                                            "padding": "8px",
                                            "margin-bottom": "10px",
                                            "border": "1px solid #ccc",
                                            "border-radius": "4px",
                                        },
                                    ),
                                ],
                            ),
                            html.Div(
                                id="login-error",
                                style={
                                    "color": "red",
                                    "margin-bottom": "10px",
                                    "min-height": "20px",
                                    "text-align": "center",
                                },
                            ),
                            html.Button(
                                "Login",
                                id="login-button",
                                n_clicks=0,
                                style={
                                    "width": "100%",
                                    "padding": "10px",
                                    "background-color": "#72A0C1",
                                    "color": "white",
                                    "border": "none",
                                    "border-radius": "4px",
                                    "cursor": "pointer",
                                    "font-size": "1.2rem",
                                    "font-weight": "bold",
                                },
                            ),
                        ],
                        style={
                            "max-width": "400px",
                            "margin": "40px auto",
                        },
                    ),
                ],
                className="container",
            ),
        ],
    )


def div_graph_daq():
    """Generates an HTML div that contains the DAQ graph and the display
    options.
    """
    return html.Div(
        [
            # List of options for the graph display
            html.Div(
                [
                    # Box to specify the path to the data file
                    dcc.Input(
                        id="input-file-path",
                        type="text",
                        value="",
                        placeholder="Input file path...",
                        disabled=False,
                        required=True,
                        style={
                            "display": "flex",
                            "justify-content": "center",
                            "align-items": "center",
                            "width": "100%",
                            "margin-top": "10px",
                        },
                    ),
                    # Entry number or run/subrun/event number
                    html.Div(
                        [
                            # Toggle between entry/(run, subrun, event) loading
                            html.Div(
                                [
                                    html.Button(
                                        id="button-source",
                                        children="Entry #",
                                        disabled=False,
                                        style={
                                            "justify-content": "left",
                                            "width": "100%",
                                        },
                                    )
                                ],
                                className="three columns",
                            ),
                            # Entry number
                            html.Div(
                                [
                                    dcc.Input(
                                        id="input-entry",
                                        value=0,
                                        min=0,
                                        type="number",
                                        disabled=False,
                                        required=True,
                                        style={"width": "100%", "display": "block"},
                                    )
                                ],
                                className="nine columns",
                            ),
                            # Run number
                            html.Div(
                                [
                                    dcc.Input(
                                        id="input-run",
                                        placeholder="Run",
                                        min=0,
                                        type="number",
                                        disabled=True,
                                        required=True,
                                        style={"width": "100%", "display": "none"},
                                    )
                                ],
                                className="three columns",
                            ),
                            # Subrun number
                            html.Div(
                                [
                                    dcc.Input(
                                        id="input-subrun",
                                        placeholder="Subrun",
                                        min=0,
                                        type="number",
                                        disabled=True,
                                        required=True,
                                        style={"width": "100%", "display": "none"},
                                    )
                                ],
                                className="three columns",
                            ),
                            # Event number
                            html.Div(
                                [
                                    dcc.Input(
                                        id="input-event",
                                        placeholder="Event",
                                        min=0,
                                        type="number",
                                        disabled=True,
                                        required=True,
                                        style={"width": "100%", "display": "none"},
                                    )
                                ],
                                className="three columns",
                            ),
                        ],
                        style={
                            "margin-top": "10px",
                        },
                        className="twelve columns",
                    ),
                    # Control buttons
                    html.Div(
                        [
                            # Load button
                            html.Div(
                                [
                                    html.Button(
                                        id="button-load",
                                        children="Load",
                                        disabled=False,
                                        style={
                                            "justify-content": "left",
                                            "width": "100%",
                                        },
                                    )
                                ],
                                className="four columns",
                            ),
                            # Previous entry button
                            html.Div(
                                [
                                    html.Button(
                                        id="button-previous",
                                        children="Previous",
                                        disabled=False,
                                        style={
                                            "justify-content": "center",
                                            "width": "100%",
                                        },
                                    )
                                ],
                                className="four columns",
                            ),
                            # Next entry button
                            html.Div(
                                [
                                    html.Button(
                                        id="button-next",
                                        children="Next",
                                        disabled=False,
                                        style={
                                            "justify-content": "center",
                                            "width": "100%",
                                        },
                                    )
                                ],
                                className="four columns",
                            ),
                        ],
                        style={
                            "margin-top": "10px",
                        },
                        className="twelve columns",
                    ),
                    # Box with information about the loading process
                    dcc.Textarea(
                        id="text-info",
                        value="Select a file, an entry and press the load button...",
                        readOnly=True,
                        style={
                            #    'display': 'flex',
                            #    'justify-content': 'center',
                            #    'align-items': 'center',
                            "color": "white",
                            "background-color": "gray",
                            "width": "100%",
                            "height": "70px",
                            "margin-top": "10px",
                        },
                    ),
                    # Choice of run mode and objects to draw
                    html.Div(
                        [
                            # Run mode radio
                            html.Div(
                                [
                                    html.H6(
                                        "Run mode",
                                        style={
                                            "font-weight": "bold",
                                            "margin-bottom": "0px",
                                            "margin-top": "10px",
                                        },
                                    ),
                                    dcc.RadioItems(
                                        options=[
                                            {
                                                "label": " Reconstructed",
                                                "value": "reco",
                                            },
                                            {"label": " Truth", "value": "truth"},
                                            {"label": " Both", "value": "both"},
                                        ],
                                        value="reco",
                                        id="radio-run-mode",
                                        style={"margin-left": "0.5%"},
                                    ),
                                ],
                                className="six columns",
                            ),
                            # Object type radio
                            html.Div(
                                [
                                    html.H6(
                                        "Object",
                                        style={
                                            "font-weight": "bold",
                                            "margin-bottom": "0px",
                                            "margin-top": "10px",
                                        },
                                    ),
                                    dcc.RadioItems(
                                        options=[
                                            {
                                                "label": " Fragments",
                                                "value": "fragments",
                                            },
                                            {
                                                "label": " Particles",
                                                "value": "particles",
                                            },
                                            {
                                                "label": " Interactions",
                                                "value": "interactions",
                                            },
                                        ],
                                        value="particles",
                                        id="radio-object-mode",
                                        style={"margin-left": "0.5%"},
                                    ),
                                ],
                                className="six columns",
                            ),
                        ],
                        className="twelve columns",
                    ),
                    # Checklist for drawing options
                    html.Div(
                        [
                            html.H6(
                                "Drawing options",
                                style={
                                    "font-weight": "bold",
                                    "margin-bottom": "0px",
                                    "margin-top": "10px",
                                },
                            )
                        ],
                        className="twelve columns",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    dcc.Checklist(
                                        id="checklist-draw-mode-1",
                                        options=[
                                            {
                                                "label": " Draw end points",
                                                "value": "point",
                                            },
                                            {
                                                "label": " Draw directions",
                                                "value": "direction",
                                            },
                                            {
                                                "label": " Draw vertices",
                                                "value": "vertex",
                                            },
                                            {
                                                "label": " Draw flashes",
                                                "value": "flash",
                                            },
                                            {
                                                "label": " Only matched flashes",
                                                "value": "flash_match_only",
                                            },
                                            {
                                                "label": " Draw CRT hits",
                                                "value": "crt",
                                            },
                                            {
                                                "label": " Only matched CRT hits",
                                                "value": "crt_match_only",
                                            },
                                        ],
                                        value=[],
                                        style={"margin-left": "0.5%"},
                                    )
                                ],
                                className="six columns",
                            ),
                            html.Div(
                                [
                                    dcc.Checklist(
                                        id="checklist-draw-mode-2",
                                        options=[
                                            {"label": " Show raw", "value": "raw"},
                                            {
                                                "label": " Split scene",
                                                "value": "split_scene",
                                            },
                                            {
                                                "label": " Split traces",
                                                "value": "split_traces",
                                            },
                                            {"label": " Sync cameras", "value": "sync"},
                                        ],
                                        value=["split_scene"],
                                        style={"margin-left": "0.5%"},
                                    )
                                ],
                                className="six columns",
                            ),
                        ],
                        className="twelve columns",
                    ),
                    # Dropdown for geometry selection (among known geometries)
                    html.Div(
                        [
                            html.H6(
                                "Attributes",
                                style={
                                    "font-weight": "bold",
                                    "margin-bottom": "0px",
                                    "margin-top": "10px",
                                },
                            ),
                            dcc.Dropdown(
                                id="dropdown-attr",
                                clearable=True,
                                searchable=True,
                                multi=True,
                                value=None,
                            ),
                            html.Div(
                                [
                                    html.P(
                                        " Color:",
                                        style={
                                            "margin-top": "5px",
                                            "display": "flex",
                                            "justify-content": "center",
                                            "align-items": "center",
                                        },
                                        className="two columns",
                                    ),
                                    html.Div(
                                        [
                                            dcc.Dropdown(
                                                id="dropdown-attr-color",
                                                clearable=True,
                                                searchable=True,
                                                multi=False,
                                                value=None,
                                            )
                                        ],
                                        className="ten columns",
                                    ),
                                ],
                                style={"margin-top": "10px"},
                                className="twelve columns",
                            ),
                        ],
                        style={"margin-top": "10px"},
                        className="twelve columns",
                    ),
                    # Dropdown for geometry selection (among known geometries)
                    # TODO: set up environment to find available geometries
                    html.Div(
                        [
                            html.H6(
                                "Geometry",
                                style={
                                    "font-weight": "bold",
                                    "margin-bottom": "0px",
                                    "margin-top": "10px",
                                },
                            ),
                            dcc.Dropdown(
                                id="dropdown-geo",
                                clearable=True,
                                searchable=True,
                                options=[
                                    # {'label': 'None', 'value': None}
                                    {"label": "2x2", "value": "2x2"},
                                    {"label": "ICARUS", "value": "icarus"},
                                    {"label": "SBND", "value": "sbnd"},
                                    {"label": "DUNE ND-LAr", "value": "ndlar"},
                                ],
                                value=None,
                            ),
                        ],
                        style={"margin-top": "10px", "margin-bottom": "10px"},
                        className="twelve columns",
                    ),
                ],
                className="three columns",
                style={"margin-left": "0.5%"},
            ),
            # Event display division
            html.Div(
                id="div-evd",
                children=dcc.Graph(id="graph-evd"),
                className="eight columns",
                style={"margin-top": "10px", "height": "100%"},
            ),
        ],
        className="row",
        style={
            "border-radius": "5px",
            "border-width": "5px",
            "border": "2px solid rgb(216, 216, 216)",
            "position": "relative",
            "height": "100%",
        },
    )


def main_layout():
    """Generate the main application layout."""
    # Import here to avoid circular dependency
    from .app import REQUIRE_AUTH, get_experiment

    # Get current experiment for display
    experiment = get_experiment() if REQUIRE_AUTH else None

    return html.Div(
        [
            # Banner display
            html.Div(
                [
                    html.H2("Spinal Tap", id="title"),
                    # Show experiment name and logout if authenticated
                    (
                        html.Div(
                            [
                                html.Div(
                                    experiment.upper(),
                                    style={
                                        "color": "#000000",
                                        "font-size": "1.8rem",
                                        "font-weight": "bold",
                                        "text-align": "center",
                                        "line-height": "1.2",
                                    },
                                ),
                                html.A(
                                    "Logout",
                                    href="/logout",
                                    style={
                                        "display": "block",
                                        "padding": "4px 12px",
                                        "margin-top": "4px",
                                        "background-color": "transparent",
                                        "border": "2px solid #000000",
                                        "border-radius": "4px",
                                        "color": "#000000",
                                        "font-size": "1rem",
                                        "font-weight": "600",
                                        "text-decoration": "none",
                                        "text-align": "center",
                                        "cursor": "pointer",
                                        "transition": "all 0.2s",
                                    },
                                ),
                            ],
                            style={
                                "position": "absolute",
                                "left": "50%",
                                "top": "50%",
                                "transform": "translate(-50%, -50%)",
                            },
                        )
                        if REQUIRE_AUTH and experiment
                        else None
                    ),
                    html.Img(
                        src=(
                            "https://raw.githubusercontent.com/DeepLearnPhysics/spine/"
                            "main/docs/source/_static/img/spine-logo-dark.png"
                        ),
                        style={"height": "80%", "padding-top": 8},
                    ),
                ],
                className="banner",
                style={"position": "relative"},
            ),
            # Main HTML division
            html.Div(
                [
                    # Invisible div that stores the underlying drawer objects
                    dcc.Store(id="store-entry"),  # Entry number to load
                    dcc.Store(id="store-camera-sync"),  # For camera synchronization
                    # Html div that shows the event display and display controls
                    div_graph_daq(),
                ],
                className="container",
            ),
        ]
    )


def get_layout():
    """Get the appropriate layout based on authentication status.

    Returns
    -------
    dash.html.Div
        Login form if auth required and not authenticated, main layout otherwise.
    """
    # Import here to avoid circular dependency
    from .app import REQUIRE_AUTH, is_authenticated

    # Always include dcc.Location for URL updates
    content = (
        login_form() if (REQUIRE_AUTH and not is_authenticated()) else main_layout()
    )

    return html.Div([dcc.Location(id="url", refresh=True), content])
