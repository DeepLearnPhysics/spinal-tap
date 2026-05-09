"""Defines the layout of the Spinal Tap application."""

import spine
from dash import dcc, html
from spine.geo.factories import geo_dict

from .version import __version__

SPINE_LOGO = (
    "https://raw.githubusercontent.com/DeepLearnPhysics/spine/"
    "main/docs/source/_static/img/spine-logo-dark.png"
)

GRAPH_CONFIG = {
    "responsive": True,
    "displaylogo": False,
    "toImageButtonOptions": {
        "format": "png",
        "filename": "spinal_tap_event_display",
        "scale": 2,
    },
}


def section(title, children, class_name="control-section", actions=None):
    """Generate a labeled control section."""
    return html.Section(
        [
            html.Div(
                [
                    html.H3(title, className="section-title"),
                    actions,
                ],
                className="section-header",
            ),
            *children,
        ],
        className=class_name,
    )


def login_form():
    """Generate login form for experiment selection and authentication."""
    return html.Div(
        [
            dcc.Store(id="login-submit-trigger", data=None),
            app_header(),
            html.Main(
                html.Div(
                    [
                        html.H2("Authentication Required", className="login-title"),
                        html.P(
                            "Select an experiment and enter the shared password.",
                            className="login-copy",
                        ),
                        html.Label("Experiment", className="field-label"),
                        dcc.Dropdown(
                            id="experiment-select",
                            options=[
                                {"label": "Public", "value": "public"},
                                {"label": "DUNE", "value": "dune"},
                                {"label": "ICARUS", "value": "icarus"},
                                {"label": "SBND", "value": "sbnd"},
                            ],
                            placeholder="Select experiment",
                            className="control-dropdown",
                        ),
                        html.Label("Password", className="field-label"),
                        dcc.Input(
                            id="password-input",
                            type="password",
                            placeholder="Enter password",
                            className="text-input",
                        ),
                        html.Div(id="login-error", className="login-error"),
                        html.Button(
                            "Login",
                            id="login-button",
                            n_clicks=0,
                            className="primary-button full-width",
                        ),
                    ],
                    className="login-panel",
                ),
                className="login-shell",
            ),
        ],
        className="app-root",
    )


def entry_controls():
    """Generate controls used to select an entry."""
    return section(
        "Data",
        [
            dcc.Input(
                id="input-file-path",
                type="text",
                value="",
                placeholder="Input file path...",
                disabled=False,
                required=True,
                autoComplete="on",
                className="text-input",
            ),
            html.Div(
                [
                    html.Button(
                        id="button-source",
                        children="Entry #",
                        disabled=False,
                        className="secondary-button source-toggle",
                    ),
                    dcc.Input(
                        id="input-entry",
                        value=0,
                        type="text",
                        inputMode="numeric",
                        pattern="[0-9]*",
                        disabled=False,
                        required=True,
                        className="text-input",
                        style={
                            "display": "block",
                            "gridColumn": "2 / -1",
                            "width": "100%",
                        },
                    ),
                    dcc.Input(
                        id="input-run",
                        placeholder="Run",
                        type="text",
                        inputMode="numeric",
                        pattern="[0-9]*",
                        disabled=True,
                        required=True,
                        className="text-input",
                        style={"display": "none", "width": "100%"},
                    ),
                    dcc.Input(
                        id="input-subrun",
                        placeholder="Subrun",
                        type="text",
                        inputMode="numeric",
                        pattern="[0-9]*",
                        disabled=True,
                        required=True,
                        className="text-input",
                        style={"display": "none", "width": "100%"},
                    ),
                    dcc.Input(
                        id="input-event",
                        placeholder="Event",
                        type="text",
                        inputMode="numeric",
                        pattern="[0-9]*",
                        disabled=True,
                        required=True,
                        className="text-input",
                        style={"display": "none", "width": "100%"},
                    ),
                ],
                className="entry-grid",
            ),
            html.Div(
                [
                    html.Button(
                        id="button-load",
                        children="Load",
                        disabled=False,
                        className="primary-button",
                    ),
                    html.Button(
                        id="button-previous",
                        children="Previous",
                        disabled=False,
                        className="secondary-button",
                    ),
                    html.Button(
                        id="button-next",
                        children="Next",
                        disabled=False,
                        className="secondary-button",
                    ),
                ],
                className="button-row",
            ),
        ],
        actions=html.Details(
            [
                html.Summary(
                    [
                        html.Span("!", className="log-alert-icon"),
                        html.Span("Log", className="log-label"),
                    ],
                    className="log-summary",
                ),
                html.Div(
                    [
                        dcc.Textarea(
                            id="text-info",
                            value=(
                                "Select a file, an entry and press the load "
                                "button..."
                            ),
                            readOnly=True,
                            className="status-log",
                        ),
                    ],
                    className="log-popover",
                ),
            ],
            id="log-panel",
            className="log-panel",
        ),
    )


def display_controls():
    """Generate object and drawing controls."""
    return section(
        "Display",
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Run mode", className="field-label"),
                            dcc.Dropdown(
                                options=[
                                    {"label": "Reconstructed", "value": "reco"},
                                    {"label": "Truth", "value": "truth"},
                                    {"label": "Both", "value": "both"},
                                ],
                                value="reco",
                                id="radio-run-mode",
                                clearable=False,
                                searchable=False,
                                className="control-dropdown",
                            ),
                        ],
                        className="control-block",
                    ),
                    html.Div(
                        [
                            html.Label("Object", className="field-label"),
                            dcc.Dropdown(
                                options=[
                                    {"label": "Fragments", "value": "fragments"},
                                    {"label": "Particles", "value": "particles"},
                                    {"label": "Interactions", "value": "interactions"},
                                ],
                                value="particles",
                                id="radio-object-mode",
                                clearable=False,
                                searchable=False,
                                className="control-dropdown",
                            ),
                        ],
                        className="control-block",
                    ),
                ],
                className="stacked-controls",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Show", className="option-group-title"),
                            dcc.Dropdown(
                                id="checklist-draw-mode-1",
                                options=[
                                    {"label": "End points", "value": "point"},
                                    {"label": "Directions", "value": "direction"},
                                    {"label": "Vertices", "value": "vertex"},
                                    {"label": "Raw depositions", "value": "raw"},
                                    {"label": "Flashes", "value": "flash"},
                                    {
                                        "label": "Only matched flashes",
                                        "value": "flash_match_only",
                                    },
                                    {"label": "CRT hits", "value": "crt"},
                                    {
                                        "label": "Only matched CRT hits",
                                        "value": "crt_match_only",
                                    },
                                ],
                                value=[],
                                multi=True,
                                clearable=True,
                                searchable=False,
                                placeholder="Select overlays",
                                className="control-dropdown",
                            ),
                        ],
                        className="control-block",
                    ),
                    html.Div(
                        [
                            html.Div("View", className="option-group-title"),
                            dcc.Dropdown(
                                id="checklist-draw-mode-2",
                                options=[
                                    {"label": "Split scene", "value": "split_scene"},
                                    {"label": "Split traces", "value": "split_traces"},
                                    {"label": "Sync cameras", "value": "sync"},
                                ],
                                value=["split_scene", "sync"],
                                multi=True,
                                clearable=True,
                                searchable=False,
                                placeholder="Select view options",
                                className="control-dropdown",
                            ),
                        ],
                        className="control-block",
                    ),
                ],
                className="draw-options",
            ),
        ],
    )


def attribute_controls():
    """Generate hovertext and coloring controls."""
    return section(
        "Attributes",
        [
            dcc.Dropdown(
                id="dropdown-attr",
                clearable=True,
                searchable=True,
                multi=True,
                value=None,
                placeholder="Hover attributes",
                className="control-dropdown",
            ),
            html.Div(
                [
                    html.Label("Color", className="field-label inline-label"),
                    dcc.Dropdown(
                        id="dropdown-attr-color",
                        clearable=True,
                        searchable=True,
                        multi=False,
                        value=None,
                        placeholder="Color attribute",
                        className="control-dropdown",
                    ),
                ],
                className="inline-control",
            ),
        ],
    )


def geometry_controls():
    """Generate geometry selection controls."""
    detector_options = [
        {"label": name, "value": name.lower()}
        for name in sorted(set(info["name"] for info in geo_dict().values()))
    ]

    return section(
        "Geometry",
        [
            html.Div(
                [
                    dcc.Dropdown(
                        id="dropdown-geo",
                        clearable=True,
                        searchable=True,
                        options=detector_options,
                        value=None,
                        placeholder="Detector",
                        className="control-dropdown",
                    ),
                    dcc.Dropdown(
                        id="dropdown-geo-tag",
                        clearable=True,
                        searchable=True,
                        options=[],
                        value=None,
                        placeholder="Tag",
                        className="control-dropdown",
                    ),
                ],
                className="split-control",
            )
        ],
    )


def div_graph_daq():
    """Generate the event display and controls."""
    return html.Div(
        [
            html.Aside(
                [
                    entry_controls(),
                    display_controls(),
                    attribute_controls(),
                    geometry_controls(),
                ],
                className="control-rail",
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.Div(
                                "No entry loaded",
                                id="event-meta",
                                className="viewer-meta muted",
                            ),
                        ],
                        className="viewer-toolbar",
                    ),
                    html.Div(
                        id="div-evd",
                        children=html.Div(className="viewer-empty"),
                        className="viewer-body",
                    ),
                ],
                className="viewer-panel",
            ),
        ],
        className="workbench",
    )


def app_header(experiment=None):
    """Generate the application header."""
    spine_version = getattr(spine, "__version__", "unknown")

    return html.Header(
        [
            html.Div(
                [
                    html.H1("Spinal Tap", id="title"),
                    html.Span("SPINE Event Display", className="app-kicker"),
                ],
                className="brand-block",
            ),
            (
                html.Div(
                    [
                        html.Span(experiment.upper(), className="experiment-chip"),
                        html.A("Logout", href="/logout", className="logout-link"),
                    ],
                    className="session-block",
                )
                if experiment
                else None
            ),
            html.Div(
                [
                    html.Span(f"Tap {__version__}", className="version-chip"),
                    html.Span(f"SPINE {spine_version}", className="version-chip"),
                ],
                className="version-block",
            ),
            html.Div(
                [
                    dcc.Checklist(
                        id="theme-toggle",
                        options=[{"label": "", "value": "dark"}],
                        value=[],
                        className="theme-toggle",
                        labelClassName="theme-toggle-label",
                        inputStyle={"display": "none"},
                    ),
                ],
                className="theme-control",
            ),
            html.Img(src=SPINE_LOGO, className="spine-logo"),
        ],
        className="app-header",
    )


def main_layout():
    """Generate the main application layout."""
    from .app import REQUIRE_AUTH, get_experiment

    experiment = get_experiment() if REQUIRE_AUTH else None

    return html.Div(
        [
            app_header(experiment),
            html.Main(
                [
                    dcc.Store(id="store-entry"),
                    dcc.Store(id="store-camera-sync"),
                    div_graph_daq(),
                ],
                className="app-main",
            ),
        ],
        className="app-root",
    )


def get_layout():
    """Get the appropriate layout based on authentication status.

    Returns
    -------
    dash.html.Div
        Login form if auth required and not authenticated, main layout otherwise.
    """
    from .app import REQUIRE_AUTH, is_authenticated

    content = (
        login_form() if (REQUIRE_AUTH and not is_authenticated()) else main_layout()
    )

    return html.Div([dcc.Location(id="url", refresh=True), content])
