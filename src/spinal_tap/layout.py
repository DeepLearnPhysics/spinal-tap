"""Defines the layout of the Spinal Tap application."""

import spine
from dash import dcc, html
from spine.geo.factories import geo_dict

from .version import __version__

SPINAL_TAP_LOGO_BLACK = "/assets/spinal-tap-logo-black.png"
SPINAL_TAP_LOGO_WHITE = "/assets/spinal-tap-logo-white.png"

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
    spine_version = getattr(spine, "__version__", "unknown")

    return html.Div(
        [
            dcc.Store(id="login-submit-trigger", data=None),
            html.Main(
                html.Div(
                    [
                        html.Div(
                            [
                                html.Img(
                                    src=SPINAL_TAP_LOGO_BLACK,
                                    alt="Spinal Tap",
                                    className=(
                                        "login-brand-logo login-brand-logo-light"
                                    ),
                                ),
                                html.Img(
                                    src=SPINAL_TAP_LOGO_WHITE,
                                    alt="Spinal Tap",
                                    className=(
                                        "login-brand-logo login-brand-logo-dark"
                                    ),
                                ),
                            ],
                            className="login-brand",
                        ),
                        html.Div(
                            [
                                html.H2("Sign in", className="login-title"),
                                html.P(
                                    (
                                        "Select an experiment and enter the "
                                        "shared password."
                                    ),
                                    className="login-copy",
                                ),
                                html.Div(
                                    [
                                        html.Label(
                                            "Experiment", className="field-label"
                                        ),
                                        dcc.Dropdown(
                                            id="experiment-select",
                                            options=[
                                                {
                                                    "label": "Public",
                                                    "value": "public",
                                                },
                                                {
                                                    "label": "DUNE",
                                                    "value": "dune",
                                                },
                                                {
                                                    "label": "ICARUS",
                                                    "value": "icarus",
                                                },
                                                {
                                                    "label": "SBND",
                                                    "value": "sbnd",
                                                },
                                            ],
                                            placeholder="Select experiment",
                                            className="control-dropdown",
                                        ),
                                    ],
                                    className="login-field",
                                ),
                                html.Div(
                                    [
                                        html.Label("Password", className="field-label"),
                                        dcc.Input(
                                            id="password-input",
                                            type="password",
                                            placeholder="Enter password",
                                            className="text-input",
                                        ),
                                    ],
                                    className="login-field",
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
                        html.Div(
                            [
                                html.Span(f"Tap {__version__}"),
                                html.Span("·", **{"aria-hidden": "true"}),
                                html.Span(f"SPINE {spine_version}"),
                            ],
                            className="login-version",
                        ),
                    ],
                    className="login-stack",
                ),
                className="login-shell",
            ),
        ],
        className="app-root login-root",
    )


def entry_controls():
    """Generate controls used to select an entry."""
    from .app import REQUIRE_AUTH
    from .cache import ALLOW_UPLOADS

    source_options = [{"label": "Path", "value": "path"}]
    if ALLOW_UPLOADS:
        label = "Upload" if REQUIRE_AUTH else "Browse"
        value = "upload" if REQUIRE_AUTH else "browse"
        source_options.append({"label": label, "value": value})
    source_options.append({"label": "URL", "value": "url"})

    return section(
        "Data",
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    dcc.Input(
                                        id="input-file-path",
                                        type="text",
                                        value="",
                                        placeholder="HDF5, manifest, or view path...",
                                        disabled=False,
                                        required=True,
                                        autoComplete="on",
                                        n_submit=0,
                                        className="text-input",
                                    ),
                                ],
                                id="source-path-row",
                                className="source-path-row",
                            ),
                            html.Div(
                                [
                                    html.Label(
                                        [
                                            html.Span(
                                                "Choose an HDF5, manifest, "
                                                "or view file…",
                                                id="upload-source-status",
                                                className="source-file-name",
                                            ),
                                            dcc.Input(
                                                id="upload-source-file",
                                                type="file",
                                                className="source-file-input",
                                            ),
                                        ],
                                        className="source-file-picker",
                                    ),
                                    html.Progress(
                                        id="upload-source-progress",
                                        value="0",
                                        max="100",
                                        className="source-upload-progress",
                                    ),
                                ],
                                id="source-upload-panel",
                                className="source-upload-panel",
                                style={"display": "none"},
                            ),
                        ],
                        className="source-input-shell",
                    ),
                    html.Button(
                        id="button-load",
                        children="Open",
                        disabled=False,
                        className="primary-button source-open-button",
                    ),
                    html.Div(
                        id="source-open-summary",
                        className="source-open-summary",
                    ),
                ],
                className="source-action-row",
            ),
            html.Div(
                [
                    dcc.RadioItems(
                        id="entry-mode",
                        options=[
                            {
                                "label": "Entry",
                                "value": "entry",
                                "disabled": True,
                            },
                            {
                                "label": "Run",
                                "value": "run",
                                "disabled": True,
                            },
                        ],
                        value="entry",
                        inline=True,
                        className="segmented-control entry-mode-control",
                    ),
                    html.Div(
                        [
                            dcc.Input(
                                id="input-entry",
                                value=0,
                                type="text",
                                inputMode="numeric",
                                pattern="[0-9]*",
                                disabled=True,
                                required=True,
                                className="text-input",
                                style={
                                    "display": "block",
                                    "width": "100%",
                                    "gridColumn": "1 / -1",
                                },
                            ),
                            *[
                                dcc.Input(
                                    id=f"input-{name}",
                                    placeholder=label,
                                    type="text",
                                    inputMode="numeric",
                                    pattern="[0-9]*",
                                    disabled=True,
                                    required=True,
                                    className="text-input",
                                    style={"display": "none", "width": "100%"},
                                )
                                for name, label in (
                                    ("run", "Run"),
                                    ("subrun", "Subrun"),
                                    ("event", "Event"),
                                )
                            ],
                        ],
                        className="event-fields",
                    ),
                    html.Button(
                        "Go",
                        id="button-go",
                        n_clicks=0,
                        disabled=True,
                        className="primary-button event-go-button",
                    ),
                ],
                className="event-selection-row",
            ),
        ],
        class_name="control-section data-section",
        actions=html.Div(
            [
                dcc.RadioItems(
                    id="source-mode",
                    options=source_options,
                    value="path",
                    inline=True,
                    className=(
                        "segmented-control source-mode-control "
                        f"source-mode-{len(source_options)}"
                    ),
                ),
                html.Details(
                    [
                        html.Summary(
                            [
                                html.Span(className="log-alert-icon"),
                                html.Span(className="log-label"),
                            ],
                            title="Status and messages",
                            className="log-summary",
                        ),
                        html.Div(
                            [
                                dcc.Textarea(
                                    id="text-info",
                                    value="Select a source to begin.",
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
            ],
            className="data-header-actions",
        ),
    )


def display_controls():
    """Generate object and drawing controls."""
    truth_source = html.Details(
        [
            html.Summary("Point source", id="truth-point-summary"),
            html.Div(
                dcc.RadioItems(
                    id="radio-truth-point-mode",
                    options=[
                        {"label": "Label", "value": "points"},
                        {"label": "Adapted", "value": "points_adapt"},
                        {"label": "Geant4", "value": "points_g4"},
                    ],
                    value="points",
                    inline=True,
                    className=("segmented-control truth-point-segmented-control"),
                ),
                className="truth-point-popover",
            ),
        ],
        id="truth-point-control",
        className="truth-point-control",
        style={"display": "none"},
    )
    return section(
        "Display",
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Run mode", className="field-label"),
                            dcc.RadioItems(
                                options=[
                                    {"label": "Reco", "value": "reco"},
                                    {"label": "Truth", "value": "truth"},
                                    {"label": "Both", "value": "both"},
                                ],
                                value="reco",
                                id="radio-run-mode",
                                inline=True,
                                className=(
                                    "segmented-control display-segmented-control"
                                ),
                            ),
                        ],
                        className="control-block",
                    ),
                    html.Div(
                        [
                            html.Label("Object", className="field-label"),
                            dcc.RadioItems(
                                options=[
                                    {"label": "Fragments", "value": "fragments"},
                                    {"label": "Particles", "value": "particles"},
                                    {"label": "Interactions", "value": "interactions"},
                                ],
                                value="particles",
                                id="radio-object-mode",
                                inline=True,
                                className=(
                                    "segmented-control display-segmented-control"
                                ),
                            ),
                        ],
                        className="control-block",
                    ),
                ],
                className="display-selector-row",
            ),
            html.Div(
                [
                    html.Div("Show", className="option-group-title"),
                    dcc.Checklist(
                        id="checklist-draw-mode-1",
                        options=[
                            {"label": "End points", "value": "point"},
                            {"label": "Directions", "value": "direction"},
                            {"label": "Vertices", "value": "vertex"},
                            {"label": "Raw", "value": "raw"},
                        ],
                        value=[],
                        inline=True,
                        className="overlay-toggle-grid",
                    ),
                    html.Div(
                        [
                            html.Div("Flash", className="overlay-mode-label"),
                            dcc.RadioItems(
                                id="radio-flash-mode",
                                options=[
                                    {"label": "Off", "value": "off"},
                                    {"label": "On", "value": "all"},
                                    {"label": "Matched", "value": "matched"},
                                ],
                                value="off",
                                inline=True,
                                className="segmented-control overlay-mode-control",
                            ),
                        ],
                        className="overlay-mode-group",
                    ),
                    html.Div(
                        [
                            html.Div("CRT", className="overlay-mode-label"),
                            dcc.RadioItems(
                                id="radio-crt-mode",
                                options=[
                                    {"label": "Off", "value": "off"},
                                    {"label": "On", "value": "all"},
                                    {"label": "Matched", "value": "matched"},
                                ],
                                value="off",
                                inline=True,
                                className="segmented-control overlay-mode-control",
                            ),
                        ],
                        className="overlay-mode-group",
                    ),
                ],
                className="show-controls",
            ),
        ],
        actions=truth_source,
    )


def attribute_controls():
    """Generate hovertext and coloring controls."""
    appearance = html.Details(
        [
            html.Summary("Appearance"),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Point size", htmlFor="input-point-size"),
                            html.Div(
                                [
                                    dcc.Slider(
                                        id="input-point-size",
                                        min=0.5,
                                        max=3.0,
                                        step=0.1,
                                        value=1.0,
                                        marks=None,
                                        tooltip={"placement": "bottom"},
                                    ),
                                    html.Output("1.0×", id="point-size-value"),
                                ],
                                className="appearance-slider-control",
                            ),
                        ],
                        className="appearance-field",
                    ),
                    html.Div(
                        [
                            html.Label("Opacity", htmlFor="input-point-opacity"),
                            html.Div(
                                [
                                    dcc.Slider(
                                        id="input-point-opacity",
                                        min=0.1,
                                        max=1.0,
                                        step=0.05,
                                        value=1.0,
                                        marks=None,
                                        tooltip={"placement": "bottom"},
                                    ),
                                    html.Output("100%", id="point-opacity-value"),
                                ],
                                className="appearance-slider-control",
                            ),
                        ],
                        className="appearance-field",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span("Continuous color"),
                                    dcc.Dropdown(
                                        id="dropdown-colorscale",
                                        options=[
                                            {"label": name, "value": name}
                                            for name in (
                                                "Inferno",
                                                "Viridis",
                                                "Cividis",
                                                "Turbo",
                                                "Rainbow",
                                                "Hot",
                                            )
                                        ],
                                        value="Inferno",
                                        clearable=False,
                                        searchable=False,
                                        className="colorscale-dropdown",
                                    ),
                                ],
                                className="appearance-field appearance-scale",
                            ),
                            dcc.RadioItems(
                                id="radio-color-transform",
                                options=[
                                    {"label": "Linear", "value": "linear"},
                                    {"label": "Log", "value": "log"},
                                ],
                                value="linear",
                                inline=True,
                                className="segmented-control appearance-segmented",
                            ),
                            html.Div(
                                [
                                    html.Canvas(
                                        id="appearance-histogram",
                                        className="appearance-histogram",
                                        **{
                                            "aria-label": (
                                                "Scalar value histogram; drag "
                                                "to select a visible range"
                                            )
                                        },
                                    ),
                                    html.Div(
                                        [
                                            html.Span("—", id="histogram-min-label"),
                                            html.Span("Drag to filter"),
                                            html.Span("—", id="histogram-max-label"),
                                        ],
                                        className="appearance-histogram-axis",
                                    ),
                                ],
                                className="appearance-histogram-control",
                            ),
                            html.Div(
                                [
                                    html.Span("Color domain"),
                                    dcc.RadioItems(
                                        id="radio-color-domain",
                                        options=[
                                            {"label": "Auto", "value": "auto"},
                                            {"label": "Manual", "value": "manual"},
                                        ],
                                        value="auto",
                                        inline=True,
                                        className=(
                                            "segmented-control appearance-segmented"
                                        ),
                                    ),
                                ],
                                className="appearance-choice",
                            ),
                            html.Div(
                                [
                                    dcc.Input(
                                        id="input-color-min",
                                        type="number",
                                        placeholder="Min",
                                    ),
                                    dcc.Input(
                                        id="input-color-max",
                                        type="number",
                                        placeholder="Max",
                                    ),
                                ],
                                id="color-domain-inputs",
                                className="appearance-range-inputs",
                                style={"display": "none"},
                            ),
                            html.Div(
                                [
                                    html.Span("Visible values"),
                                    dcc.RadioItems(
                                        id="radio-visible-range",
                                        options=[
                                            {"label": "All", "value": "all"},
                                            {"label": "Range", "value": "range"},
                                        ],
                                        value="all",
                                        inline=True,
                                        className=(
                                            "segmented-control appearance-segmented"
                                        ),
                                    ),
                                ],
                                className="appearance-choice",
                            ),
                            html.Div(
                                [
                                    dcc.Input(
                                        id="input-visible-min",
                                        type="number",
                                        placeholder="Min",
                                    ),
                                    dcc.Input(
                                        id="input-visible-max",
                                        type="number",
                                        placeholder="Max",
                                    ),
                                ],
                                id="visible-range-inputs",
                                className="appearance-range-inputs",
                                style={"display": "none"},
                            ),
                        ],
                        id="continuous-appearance-controls",
                        className="continuous-appearance-controls",
                        style={"display": "none"},
                    ),
                ],
                className="appearance-popover",
            ),
        ],
        id="appearance-picker",
        className="appearance-picker",
    )
    return section(
        "Attributes",
        [
            html.Details(
                [
                    html.Summary(
                        [
                            html.Span(
                                "0 shown · Color: Object ID",
                                id="attribute-picker-summary",
                            ),
                            html.Span(
                                [
                                    html.Button(
                                        id="button-clear-attributes",
                                        className="attribute-picker-clear",
                                        title="Clear hover and color attributes",
                                        **{
                                            "aria-label": "Clear attributes",
                                            "type": "button",
                                        },
                                        style={"display": "none"},
                                    ),
                                    html.Span(className="attribute-picker-chevron"),
                                ],
                                className="attribute-picker-actions",
                            ),
                        ],
                        className="attribute-picker-trigger",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span(className="attribute-picker-search-icon"),
                                    dcc.Input(
                                        id="input-attribute-search",
                                        type="search",
                                        placeholder="Search",
                                        debounce=False,
                                        className="attribute-picker-search",
                                    ),
                                ],
                                className="attribute-picker-search-container",
                            ),
                            html.Div(
                                [
                                    html.Span("Attribute"),
                                    html.Span("Hover"),
                                    html.Span("Color"),
                                ],
                                className="attribute-picker-heading",
                            ),
                            html.Div(
                                id="attribute-picker-list",
                                className="attribute-picker-list",
                            ),
                            dcc.Checklist(
                                id="dropdown-attr",
                                options=[],
                                value=[],
                                className="attribute-picker-state",
                            ),
                            dcc.RadioItems(
                                id="dropdown-attr-color",
                                options=[],
                                value="",
                                className="attribute-picker-state",
                            ),
                        ],
                        className="attribute-picker-popover",
                    ),
                ],
                id="attribute-picker",
                className="attribute-picker",
            ),
        ],
        actions=appearance,
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
        actions=html.Button(
            "↺",
            id="button-restore-geometry",
            type="button",
            title="Restore detected geometry",
            hidden=True,
            className="geometry-restore-button",
            **{"aria-label": "Restore detected geometry"},
        ),
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
                                [
                                    html.Button(
                                        "‹",
                                        id="button-previous",
                                        n_clicks=0,
                                        title="Previous entry (←)",
                                        disabled=True,
                                        className="entry-nav-button",
                                    ),
                                    html.Div(
                                        "No entry loaded",
                                        id="event-meta",
                                        className="viewer-meta muted",
                                    ),
                                    html.Button(
                                        "›",
                                        id="button-next",
                                        n_clicks=0,
                                        title="Next entry (→)",
                                        disabled=True,
                                        className="entry-nav-button",
                                    ),
                                ],
                                className="viewer-toolbar-primary",
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Span(
                                                "Reco 0/0",
                                                id="reco-filter-label",
                                                className="object-filter-summary",
                                            ),
                                            dcc.Dropdown(
                                                id="dropdown-reco-filter",
                                                options=[],
                                                value=[],
                                                multi=True,
                                                clearable=True,
                                                searchable=True,
                                                placeholder="",
                                                className="object-filter-dropdown",
                                            ),
                                        ],
                                        id="reco-filter-group",
                                        className="object-filter-group reco-filter",
                                    ),
                                    html.Button(
                                        html.Span(
                                            className="chain-icon",
                                            **{"aria-hidden": "true"},
                                        ),
                                        id="button-link-filters",
                                        n_clicks=0,
                                        title="Link matched object visibility",
                                        **{
                                            "aria-label": (
                                                "Link matched object visibility"
                                            ),
                                            "aria-pressed": "false",
                                        },
                                        className="match-link-toggle",
                                    ),
                                    html.Div(
                                        [
                                            html.Span(
                                                "Truth 0/0",
                                                id="truth-filter-label",
                                                className="object-filter-summary",
                                            ),
                                            dcc.Dropdown(
                                                id="dropdown-truth-filter",
                                                options=[],
                                                value=[],
                                                multi=True,
                                                clearable=True,
                                                searchable=True,
                                                placeholder="",
                                                className="object-filter-dropdown",
                                            ),
                                        ],
                                        id="truth-filter-group",
                                        className="object-filter-group truth-filter",
                                    ),
                                ],
                                id="object-filter-toolbar",
                                className="object-filter-toolbar",
                            ),
                        ],
                        className="viewer-toolbar",
                    ),
                    html.Div(
                        id="div-evd",
                        children=html.Div(className="viewer-empty"),
                        className="viewer-body",
                    ),
                    html.Aside(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Span(
                                                "Selected object",
                                                className="object-inspector-eyebrow",
                                            ),
                                            html.H3(
                                                id="object-inspector-title",
                                                className="object-inspector-title",
                                            ),
                                            html.Div(
                                                id="object-inspector-match-summary",
                                                className=(
                                                    "object-inspector-match-summary"
                                                ),
                                            ),
                                        ]
                                    ),
                                    html.Button(
                                        "×",
                                        id="button-close-inspector",
                                        type="button",
                                        title="Close object inspector (Esc)",
                                        className="object-inspector-close",
                                        **{"aria-label": "Close object inspector"},
                                    ),
                                ],
                                className="object-inspector-header",
                            ),
                            html.Div(
                                id="object-inspector-content",
                                className="object-inspector-content",
                            ),
                            html.Div(
                                [
                                    html.Button(
                                        "Center here",
                                        id="button-center-camera",
                                        type="button",
                                        disabled=True,
                                        title=(
                                            "Use the selected point as the "
                                            "WebGL view and GIF rotation center"
                                        ),
                                        className="viewer-action-button",
                                    ),
                                    html.Button(
                                        "Show only",
                                        id="button-isolate-object",
                                        type="button",
                                        title="Show only this object",
                                        className="viewer-action-button",
                                        **{"aria-pressed": "false"},
                                    ),
                                ],
                                className="object-inspector-actions",
                            ),
                        ],
                        id="object-inspector",
                        className="object-inspector",
                        hidden=True,
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    dcc.Checklist(
                                        id="checklist-draw-mode-2",
                                        options=[
                                            {
                                                "label": "Split scenes",
                                                "value": "split_scene",
                                            },
                                            {
                                                "label": "Sync cameras",
                                                "value": "sync",
                                            },
                                        ],
                                        value=["split_scene", "sync"],
                                        inline=True,
                                        className="viewer-view-toggles",
                                        style={"display": "none"},
                                    ),
                                    dcc.Checklist(
                                        id="checklist-show-axes",
                                        options=[
                                            {
                                                "label": "Axes",
                                                "value": "axes",
                                            },
                                        ],
                                        value=["axes"],
                                        inline=True,
                                        className="viewer-view-toggles",
                                    ),
                                    html.Button(
                                        "Reset view",
                                        id="button-reset-view",
                                        n_clicks=0,
                                        title="Reset view (R)",
                                        disabled=True,
                                        className="viewer-action-button",
                                    ),
                                ],
                                className="viewer-view-controls",
                            ),
                            html.Div(
                                [
                                    html.Details(
                                        [
                                            html.Summary(
                                                "Labels",
                                                title=(
                                                    "Choose labels included in "
                                                    "exported scenes"
                                                ),
                                            ),
                                            html.Div(
                                                [
                                                    html.Div(
                                                        "Include in exports",
                                                        className=(
                                                            "export-branding-title"
                                                        ),
                                                    ),
                                                    dcc.Checklist(
                                                        id="checklist-export-labels",
                                                        options=[
                                                            {
                                                                "label": "SPINE",
                                                                "value": "spine",
                                                            },
                                                            {
                                                                "label": (
                                                                    "Detector logo"
                                                                ),
                                                                "value": "detector",
                                                            },
                                                            {
                                                                "label": "Source name",
                                                                "value": "source",
                                                            },
                                                            {
                                                                "label": "Entry",
                                                                "value": "entry",
                                                            },
                                                            {
                                                                "label": (
                                                                    "Run / Subrun / "
                                                                    "Event"
                                                                ),
                                                                "value": "run",
                                                            },
                                                        ],
                                                        value=["spine", "entry"],
                                                        className=(
                                                            "export-watermark-"
                                                            "options"
                                                        ),
                                                    ),
                                                ],
                                                className=("export-branding-popover"),
                                            ),
                                        ],
                                        id="export-branding-menu",
                                        className="export-branding-menu",
                                    ),
                                    html.Button(
                                        "Save PNG",
                                        id="button-save-png",
                                        n_clicks=0,
                                        disabled=True,
                                        title="Save PNG (S)",
                                        className="viewer-action-button",
                                    ),
                                    html.Button(
                                        "Save GIF",
                                        id="button-save-scene",
                                        n_clicks=0,
                                        disabled=True,
                                        title="GIF export is available in WebGL mode",
                                        className="viewer-action-button",
                                    ),
                                    html.Button(
                                        "Share",
                                        id="button-share",
                                        n_clicks=0,
                                        disabled=True,
                                        title="Copy a link to this view",
                                        className="viewer-action-button",
                                    ),
                                    html.Button(
                                        "Export JSON",
                                        id="button-export-view",
                                        n_clicks=0,
                                        disabled=True,
                                        title="Export this view as JSON (E)",
                                        className="viewer-action-button",
                                    ),
                                ],
                                id="viewer-actions",
                                className="viewer-actions",
                            ),
                        ],
                        className="viewer-footer",
                    ),
                ],
                className="viewer-panel",
            ),
        ],
        className="workbench",
    )


def app_header(experiment=None, show_help=False):
    """Generate the application header."""
    spine_version = getattr(spine, "__version__", "unknown")

    return html.Header(
        [
            html.Div(
                [
                    html.Img(
                        src=SPINAL_TAP_LOGO_BLACK,
                        alt="Spinal Tap",
                        className="brand-logo brand-logo-light",
                    ),
                    html.Img(
                        src=SPINAL_TAP_LOGO_WHITE,
                        alt="Spinal Tap",
                        className="brand-logo brand-logo-dark",
                    ),
                ],
                className="brand-block",
            ),
            html.Div(
                [
                    html.Span(f"Tap {__version__}", className="version-chip"),
                    html.Span(f"SPINE {spine_version}", className="version-chip"),
                ],
                className="version-block",
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
                    (
                        html.Details(
                            [
                                html.Summary(
                                    "?",
                                    title="Keyboard shortcuts",
                                    **{"aria-label": "Keyboard shortcuts"},
                                ),
                                html.Div(
                                    [
                                        html.H3("Keyboard shortcuts"),
                                        html.Div(
                                            [
                                                html.Kbd("← / →"),
                                                html.Span("Previous / next entry"),
                                            ],
                                            className="help-shortcut-row",
                                        ),
                                        html.Div(
                                            [html.Kbd("R"), html.Span("Reset view")],
                                            className="help-shortcut-row",
                                        ),
                                        html.Div(
                                            [html.Kbd("A"), html.Span("Toggle axes")],
                                            className="help-shortcut-row",
                                        ),
                                        html.Div(
                                            [html.Kbd("S"), html.Span("Save PNG")],
                                            className="help-shortcut-row",
                                        ),
                                        html.Div(
                                            [
                                                html.Kbd("E"),
                                                html.Span("Export view JSON"),
                                            ],
                                            className="help-shortcut-row",
                                        ),
                                        html.Div(
                                            [
                                                html.Kbd("?"),
                                                html.Span("Open / close help"),
                                            ],
                                            className="help-shortcut-row",
                                        ),
                                        html.Div(
                                            [
                                                html.Span(
                                                    "Resources",
                                                    className="help-resources-title",
                                                ),
                                                html.A(
                                                    "Documentation",
                                                    href=(
                                                        "https://spinal-tap."
                                                        "readthedocs.io/stable/"
                                                    ),
                                                    target="_blank",
                                                    rel="noopener noreferrer",
                                                    className=(
                                                        "help-resource-link "
                                                        "help-documentation-link"
                                                    ),
                                                ),
                                                html.A(
                                                    "GitHub repository",
                                                    href=(
                                                        "https://github.com/"
                                                        "DeepLearnPhysics/spinal-tap"
                                                    ),
                                                    target="_blank",
                                                    rel="noopener noreferrer",
                                                    className="help-resource-link",
                                                ),
                                                html.A(
                                                    "Report an issue",
                                                    href=(
                                                        "https://github.com/"
                                                        "DeepLearnPhysics/spinal-tap/"
                                                        "issues/new/choose"
                                                    ),
                                                    target="_blank",
                                                    rel="noopener noreferrer",
                                                    className="help-resource-link",
                                                ),
                                            ],
                                            className="help-resources",
                                        ),
                                    ],
                                    className="help-popover",
                                ),
                            ],
                            id="help-menu",
                            className="help-menu",
                        )
                        if show_help
                        else None
                    ),
                    dcc.Checklist(
                        id="renderer-toggle",
                        options=[{"label": "", "value": "plotly"}],
                        value=[],
                        className="renderer-toggle",
                        labelClassName="renderer-toggle-label",
                        inputStyle={"display": "none"},
                    ),
                    dcc.Checklist(
                        id="theme-toggle",
                        options=[{"label": "", "value": "dark"}],
                        value=[],
                        className="theme-toggle",
                        labelClassName="theme-toggle-label",
                        inputStyle={"display": "none"},
                    ),
                ],
                className="header-toggles",
            ),
        ],
        className="app-header",
    )


def main_layout():
    """Generate the main application layout."""
    from .app import REQUIRE_AUTH, get_experiment

    experiment = get_experiment() if REQUIRE_AUTH else None

    return html.Div(
        [
            app_header(experiment, show_help=True),
            html.Main(
                [
                    dcc.Store(id="store-entry"),
                    dcc.Store(id="store-loaded-event"),
                    dcc.Store(id="store-source-memory"),
                    dcc.Store(id="store-source-request"),
                    dcc.Store(id="store-dropdown-commit"),
                    dcc.Store(id="store-dropdown-pending"),
                    dcc.Store(id="store-attribute-options"),
                    dcc.Store(id="store-camera-sync"),
                    dcc.Store(id="store-object-filter"),
                    dcc.Store(id="store-inspected-object"),
                    dcc.Store(id="store-inspection-action"),
                    dcc.Store(id="store-inspection-highlights"),
                    dcc.Store(id="store-camera-pivot"),
                    dcc.Store(id="store-filter-render-request"),
                    dcc.Store(id="store-appearance-render-request"),
                    dcc.Store(id="store-object-match-links"),
                    dcc.Store(id="store-display-controls"),
                    dcc.Store(id="store-link-filters", data=False),
                    dcc.Store(id="store-theme-bootstrap", data=True),
                    dcc.Store(id="store-theme"),
                    dcc.Store(id="store-color"),
                    dcc.Store(id="store-geometry-choice", data="auto"),
                    dcc.Store(id="store-share-state"),
                    dcc.Store(id="store-share-request"),
                    dcc.Store(id="store-share-pending"),
                    dcc.Store(id="store-share-applied"),
                    dcc.Store(id="store-view-action"),
                    dcc.Store(id="store-axes"),
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
