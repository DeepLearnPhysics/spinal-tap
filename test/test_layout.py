"""Tests for Spinal Tap layout controls."""

from spinal_tap import cache as cache_module
from spinal_tap.layout import (
    app_header,
    attribute_controls,
    display_controls,
    login_form,
    main_layout,
)


def component_by_id(component, component_id):
    """Find a Dash component recursively by ID."""
    if getattr(component, "id", None) == component_id:
        return component
    children = getattr(component, "children", None)
    if children is None:
        return None
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        result = component_by_id(child, component_id)
        if result is not None:
            return result
    return None


def component_by_class(component, class_name):
    """Find a Dash component recursively by CSS class."""
    classes = (getattr(component, "className", None) or "").split()
    if class_name in classes:
        return component
    children = getattr(component, "children", None)
    if children is None:
        return None
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        result = component_by_class(child, class_name)
        if result is not None:
            return result
    return None


def test_display_controls_do_not_use_split_traces():
    """The display controls should omit the obsolete split-trace option."""
    controls = display_controls()
    object_filter = component_by_id(controls, "dropdown-object-filter")
    draw_mode = component_by_id(main_layout(), "checklist-draw-mode-2")

    assert object_filter is None
    assert "split_traces" not in {option["value"] for option in draw_mode.options}
    assert draw_mode.style == {"display": "none"}


def test_display_modes_use_stable_segmented_controls():
    """Run and object modes should remain visible as three-way selectors."""
    controls = display_controls()
    run_mode = component_by_id(controls, "radio-run-mode")
    object_mode = component_by_id(controls, "radio-object-mode")
    truth_points = component_by_id(controls, "radio-truth-point-mode")
    truth_source = component_by_id(controls, "truth-point-control")
    truth_summary = component_by_id(controls, "truth-point-summary")

    assert run_mode.__class__.__name__ == "RadioItems"
    assert object_mode.__class__.__name__ == "RadioItems"
    assert "display-segmented-control" in run_mode.className
    assert "display-segmented-control" in object_mode.className
    assert [option["value"] for option in run_mode.options] == [
        "reco",
        "truth",
        "both",
    ]
    assert [option["value"] for option in object_mode.options] == [
        "fragments",
        "particles",
        "interactions",
    ]
    assert [option["value"] for option in truth_points.options] == [
        "points",
        "points_adapt",
        "points_g4",
    ]
    assert truth_source.__class__.__name__ == "Details"
    assert truth_summary.children == "Point source"


def test_scene_overlays_use_direct_controls():
    """Overlay and view choices should no longer require closing a menu."""
    display = display_controls()
    attributes = attribute_controls()

    overlays = component_by_id(display, "checklist-draw-mode-1")
    view = component_by_id(main_layout(), "checklist-draw-mode-2")
    axes = component_by_id(main_layout(), "checklist-show-axes")
    flash = component_by_id(display, "radio-flash-mode")
    crt = component_by_id(display, "radio-crt-mode")
    picker = component_by_id(attributes, "attribute-picker")
    clear = component_by_id(attributes, "button-clear-attributes")
    chevron = next(
        child
        for child in picker.children[0].children[1].children
        if getattr(child, "className", None) == "attribute-picker-chevron"
    )
    hover = component_by_id(attributes, "dropdown-attr")
    color = component_by_id(attributes, "dropdown-attr-color")
    colorscale = component_by_id(attributes, "dropdown-colorscale")
    appearance = component_by_id(attributes, "appearance-picker")
    continuous = component_by_id(attributes, "continuous-appearance-controls")
    search = component_by_id(attributes, "input-attribute-search")
    rows = component_by_id(attributes, "attribute-picker-list")

    assert overlays.__class__.__name__ == "Checklist"
    assert view.__class__.__name__ == "Checklist"
    assert axes.__class__.__name__ == "Checklist"
    assert axes.options == [{"label": "Axes", "value": "axes"}]
    assert axes.value == ["axes"]
    assert flash.value == "off"
    assert crt.value == "off"
    assert picker.__class__.__name__ == "Details"
    assert clear.title == "Clear hover and color attributes"
    assert clear.style == {"display": "none"}
    assert chevron.children is None
    assert hover.__class__.__name__ == "Checklist"
    assert color.__class__.__name__ == "RadioItems"
    assert colorscale.value == "Inferno"
    assert colorscale.clearable is False
    assert [option["value"] for option in colorscale.options] == [
        "Inferno",
        "Viridis",
        "Cividis",
        "Turbo",
        "Rainbow",
        "Hot",
    ]
    assert appearance.__class__.__name__ == "Details"
    assert appearance.children[0].children == "Appearance"
    assert continuous.style == {"display": "none"}
    point_size = component_by_id(attributes, "input-point-size")
    point_opacity = component_by_id(attributes, "input-point-opacity")
    assert point_size.__class__.__name__ == "Slider"
    assert point_size.value == 1.0
    assert point_size.min == 0.5
    assert point_size.max == 3.0
    assert point_opacity.__class__.__name__ == "Slider"
    assert point_opacity.value == 1.0
    assert point_opacity.min == 0.1
    assert point_opacity.max == 1.0
    assert component_by_id(attributes, "point-size-value").children == "1.0\u00d7"
    assert component_by_id(attributes, "point-opacity-value").children == "100%"
    assert component_by_id(attributes, "histogram-min-label").children == "\u2014"
    assert component_by_id(attributes, "histogram-max-label").children == "\u2014"
    assert component_by_id(attributes, "radio-color-transform").value == "linear"
    assert component_by_id(attributes, "radio-color-domain").value == "auto"
    assert component_by_id(attributes, "radio-visible-range").value == "all"
    assert search.placeholder == "Search"
    assert rows.children is None
    assert hover.className == "attribute-picker-state"
    assert color.className == "attribute-picker-state"


def test_object_inspector_exposes_webgl_camera_center_action():
    """The inspector should expose a guarded WebGL camera-center action."""
    layout = main_layout()
    center = component_by_id(layout, "button-center-camera")
    pivot = component_by_id(layout, "store-camera-pivot")

    assert center.children == "Center here"
    assert center.disabled is True
    assert center.className == "viewer-action-button"
    assert pivot.__class__.__name__ == "Store"


def test_viewer_contains_renderer_independent_object_inspector():
    """The canvas should expose one shared inspector for both renderers."""
    layout = main_layout()
    inspector = component_by_id(layout, "object-inspector")

    assert inspector.__class__.__name__ == "Aside"
    assert inspector.hidden is True
    assert component_by_id(layout, "store-inspected-object") is not None
    assert component_by_id(layout, "store-inspection-highlights") is not None
    assert component_by_id(layout, "button-close-inspector") is not None
    isolate = component_by_id(layout, "button-isolate-object")
    assert isolate.children == "Show only"
    assert isolate.disabled is True
    assert isolate.__dict__["aria-pressed"] == "false"


def test_layout_contains_refresh_state_stores():
    """The layout should separate loaded events from close notifications."""
    layout = main_layout()

    assert component_by_id(layout, "store-loaded-event") is not None
    assert component_by_id(layout, "store-source-memory") is not None
    assert component_by_id(layout, "store-source-request") is not None
    assert component_by_id(layout, "store-dropdown-commit") is not None
    assert component_by_id(layout, "store-dropdown-pending") is not None
    assert component_by_id(layout, "store-attribute-options") is not None
    assert component_by_id(layout, "store-object-match-links") is not None
    assert component_by_id(layout, "store-link-filters") is not None


def test_geometry_controls_include_detected_restore_action():
    """The geometry section should expose a compact, contextual restore action."""
    layout = main_layout()

    restore = component_by_id(layout, "button-restore-geometry")
    assert restore.children == "↺"
    assert restore.hidden is True
    assert restore.title == "Restore detected geometry"


def test_layout_contains_shared_view_controls():
    """The viewer should expose sharing and its staged restore state."""
    layout = main_layout()

    actions = component_by_id(layout, "viewer-actions")
    share = component_by_id(layout, "button-share")
    reset = component_by_id(layout, "button-reset-view")
    previous = component_by_id(layout, "button-previous")
    next_ = component_by_id(layout, "button-next")
    save = component_by_id(actions, "button-save-png")
    scene_export = component_by_id(actions, "button-save-scene")
    branding = component_by_id(actions, "export-branding-menu")
    labels = component_by_id(actions, "checklist-export-labels")
    export = component_by_id(actions, "button-export-view")
    file_path = component_by_id(layout, "input-file-path")
    assert file_path.n_submit == 0
    assert share.children == "Share"
    assert export.children == "Export JSON"
    assert share.disabled is True
    assert reset.disabled is True
    assert reset.title == "Reset view (R)"
    assert previous.title == "Previous entry (←)"
    assert next_.title == "Next entry (→)"
    assert save.disabled is True
    assert scene_export.children == "Save GIF"
    assert scene_export.disabled is True
    assert scene_export.title == "GIF export is available in WebGL mode"
    assert branding.children[0].children == "Labels"
    assert labels.value == ["spine", "entry"]
    assert [option["value"] for option in labels.options] == [
        "spine",
        "detector",
        "source",
        "entry",
        "run",
    ]
    assert export.disabled is True
    assert file_path.placeholder == "HDF5, manifest, or view path..."
    assert component_by_id(layout, "upload-view-state") is None
    assert component_by_id(layout, "upload-view-state-data") is None
    assert component_by_id(actions, "share-menu") is None
    for store_id in (
        "store-share-state",
        "store-share-request",
        "store-share-pending",
        "store-share-applied",
        "store-view-action",
    ):
        assert component_by_id(layout, store_id) is not None


def test_local_data_controls_use_native_file_picker():
    """Local Browse should use the standard browser file input."""
    controls = main_layout()
    modes = component_by_id(controls, "source-mode")
    entry_mode = component_by_id(controls, "entry-mode")

    assert [option["value"] for option in modes.options] == ["path", "browse", "url"]
    assert [option["value"] for option in entry_mode.options] == ["entry", "run"]
    assert all(option["disabled"] for option in entry_mode.options)
    assert component_by_id(controls, "upload-source-file").type == "file"
    assert (
        component_by_id(controls, "upload-source-status").children
        == "Choose an HDF5, manifest, or view file…"
    )
    assert component_by_id(controls, "button-browse-source") is None
    assert component_by_id(controls, "button-source") is None


def test_data_controls_use_compact_source_and_navigation_rows():
    """Source opening and event navigation should not consume full panel rows."""
    controls = main_layout()
    source = component_by_id(controls, "button-load")
    entry_mode = component_by_id(controls, "entry-mode")

    assert source.children == "Open"
    assert "full-width" not in source.className
    assert component_by_id(controls, "input-file-path") is not None
    assert "entry-mode-control" in entry_mode.className
    assert component_by_id(controls, "input-entry").disabled is True
    assert component_by_id(controls, "button-go").disabled is True
    assert component_by_id(controls, "store-filter-render-request") is not None


def test_data_controls_reserve_status_for_success_and_errors():
    """The source header should expose one fixed class-driven status control."""
    controls = main_layout()
    panel = component_by_id(controls, "log-panel")
    icon = next(
        child
        for child in panel.children[0].children
        if getattr(child, "className", None) == "log-alert-icon"
    )
    label = next(
        child
        for child in panel.children[0].children
        if getattr(child, "className", None) == "log-label"
    )

    assert panel.className == "log-panel"
    assert panel.children[0].title == "Status and messages"
    assert icon.children is None
    assert label.children is None


def test_authenticated_data_controls_offer_upload_not_server_browse(monkeypatch):
    """Hosted mode should transfer local files without exposing server paths."""
    monkeypatch.setattr("spinal_tap.app.REQUIRE_AUTH", True)
    monkeypatch.setattr(cache_module, "ALLOW_UPLOADS", True)

    controls = main_layout()
    modes = component_by_id(controls, "source-mode")

    assert [option["value"] for option in modes.options] == ["path", "upload", "url"]


def test_object_filters_live_in_the_viewer_toolbar():
    """Reco/truth filters and their link control should share the toolbar."""
    layout = main_layout()
    toolbar = component_by_id(layout, "object-filter-toolbar")

    reco = component_by_id(toolbar, "dropdown-reco-filter")
    truth = component_by_id(toolbar, "dropdown-truth-filter")
    link = component_by_id(toolbar, "button-link-filters")
    reco_label = component_by_id(toolbar, "reco-filter-label")
    truth_label = component_by_id(toolbar, "truth-filter-label")
    assert reco.multi is True
    assert truth.multi is True
    assert reco_label.children == "Reco 0/0"
    assert truth_label.children == "Truth 0/0"
    assert link.to_plotly_json()["props"]["aria-pressed"] == "false"


def test_header_uses_renderer_toggle():
    """Renderer selection should sit beside the theme as the same switch type."""
    header = app_header()
    renderer = component_by_id(header, "renderer-toggle")
    theme = component_by_id(header, "theme-toggle")

    assert renderer.__class__ is theme.__class__
    assert renderer.value == []
    assert renderer.options == [{"label": "", "value": "plotly"}]
    assert renderer.labelClassName == "renderer-toggle-label"

    logos = [
        child
        for child in header.children[0].children
        if child.__class__.__name__ == "Img"
    ]
    assert [logo.src for logo in logos] == [
        "/assets/spinal-tap-logo-black.png",
        "/assets/spinal-tap-logo-white.png",
    ]
    assert all(logo.alt == "Spinal Tap" for logo in logos)
    assert not any(
        getattr(child, "className", None) == "spine-logo"
        for child in header.children
        if child is not None
    )


def test_help_is_only_present_in_the_main_header():
    """Keyboard help should not appear on the login header."""
    header = app_header()
    layout = main_layout()

    assert component_by_id(header, "help-menu") is None
    help_menu = component_by_id(layout, "help-menu")
    assert help_menu is not None
    assert help_menu.children[0].children == "?"
    assert help_menu.children[0].title == "Keyboard shortcuts"
    resources = component_by_class(help_menu, "help-resources")
    assert resources.children[0].children == "Resources"
    links = resources.children[1:]
    assert [link.children for link in links] == [
        "Documentation",
        "GitHub repository",
        "Report an issue",
    ]
    assert [link.href for link in links] == [
        "https://spinal-tap.readthedocs.io/stable/",
        "https://github.com/DeepLearnPhysics/spinal-tap",
        "https://github.com/DeepLearnPhysics/spinal-tap/issues/new/choose",
    ]
    assert all(link.target == "_blank" for link in links)
    assert all(link.rel == "noopener noreferrer" for link in links)


def test_login_uses_dedicated_branded_layout():
    """The login surface should omit controls that require a loaded event."""
    layout = login_form()

    assert "login-root" in layout.className
    assert component_by_id(layout, "renderer-toggle") is None
    assert component_by_id(layout, "theme-toggle") is None
    assert component_by_id(layout, "help-menu") is None
    assert component_by_id(layout, "experiment-select") is not None
    assert component_by_id(layout, "password-input") is not None
    assert component_by_id(layout, "login-button") is not None

    stack = layout.children[1].children
    logos = stack.children[0].children
    assert [logo.src for logo in logos] == [
        "/assets/spinal-tap-logo-black.png",
        "/assets/spinal-tap-logo-white.png",
    ]
    assert stack.children[1].children[0].children == "Sign in"
    versions = [child.children for child in stack.children[2].children]
    assert versions[0].startswith("Tap ")
    assert versions[1] == "·"
    assert versions[2].startswith("SPINE ")


def test_main_layout_bootstraps_browser_theme_preference():
    """The authenticated UI should initialize its toggle from the browser."""
    layout = main_layout()

    bootstrap = component_by_id(layout, "store-theme-bootstrap")
    assert bootstrap is not None
    assert bootstrap.data is True
