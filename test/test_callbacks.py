"""Tests for Spinal Tap callback registration."""

import json
from types import SimpleNamespace

import plotly.graph_objects as go
import pytest
from dash import Dash, dcc, html, no_update
from flask import Flask
from spine.vis.scene import PointStyle

import spinal_tap.callbacks as callback_module
from spinal_tap.app import create_app
from spinal_tap.callbacks import (
    GRAPH_CONFIG,
    apply_continuous_colorscale,
    apply_plotly_appearance,
    apply_plotly_colorscale,
    attribute_options,
    compose_draw_modes,
    configure_geometry,
    continuous_color_attribute,
    display_control_state,
    format_entry_label,
    geometry_choice_for_file,
    is_embedded_geometry_selection,
    load_view_state,
    navigation_file_path,
    overlay_control_state,
    parse_optional_int,
    register_callbacks,
    restored_object_filter,
    validate_manifest_access,
    validate_view_state,
)
from spinal_tap.layout import get_layout


def registered_callback(app, name):
    """Return an undecorated registered server callback by function name."""
    for callback in app.callback_map.values():
        function = callback.get("callback")
        if function is None:
            continue
        function = getattr(function, "__wrapped__", function)
        if function.__name__ == name:
            return function
    raise KeyError(name)


@pytest.fixture(scope="module")
def callback_app():
    """Build one application for direct callback tests."""
    return create_app()


def test_camera_sync_owns_graph_mount_updates():
    """Only camera synchronization should mutate a newly mounted graph."""
    server = Flask(__name__)
    app = Dash(__name__, server=server, suppress_callback_exceptions=True)
    app.layout = get_layout
    register_callbacks(app)

    dependencies = server.test_client().get("/_dash-dependencies").get_json()
    graph_mount_callbacks = [
        callback
        for callback in dependencies
        if any(
            item["id"] == "div-evd" and item["property"] == "children"
            for item in callback["inputs"]
        )
    ]

    assert [callback["output"] for callback in graph_mount_callbacks] == [
        "store-camera-sync.data"
    ]


def test_object_inspector_uses_cached_event_data(callback_app, monkeypatch):
    """The inspector should summarize the selected cached output object."""
    callback = registered_callback(callback_app, "update_object_inspector")
    obj = SimpleNamespace(
        id=17,
        shape=1,
        depositions_sum=12.5,
        is_matched=True,
        match_ids=[9, 12],
        enum_values={"shape": {1: "track"}},
        field_units={"depositions_sum": "MeV"},
    )
    obj.as_dict = lambda: {
        "id": obj.id,
        "shape": obj.shape,
        "depositions_sum": obj.depositions_sum,
        "is_matched": obj.is_matched,
    }
    monkeypatch.setattr(callback_module, "initialize_reader", lambda *args: object())
    monkeypatch.setattr(
        callback_module,
        "load_data",
        lambda *args: ({"reco_particles": [obj]}, None, None),
    )

    title, match_summary, content, hidden = callback(
        {"prefix": "reco", "position": 0, "family": "particles"},
        {"file_path": "/tmp/event.h5", "entry": 3},
        "reco",
        "particles",
    )

    assert title == "Reco Particle 17"
    assert match_summary == "Matched truth: Truth Particle 9, Truth Particle 12"
    assert not hidden
    assert [section.children[0].children for section in content] == [
        "Overview",
        "Identifiers & references",
        "Energy & kinematics",
        "Object matching",
    ]

    _, match_summary, _, _ = callback(
        {"key": "reco:0", "prefix": "reco", "position": 0, "family": "particles"},
        {"file_path": "/tmp/event.h5", "entry": 3},
        "both",
        "particles",
        {"reco:0": ["truth:2"]},
        [],
        [{"value": "truth:2", "label": "Truth Particle 12 · 4 pts"}],
    )
    assert match_summary == "Matches on the right: Truth Particle 12"

    _, match_summary, _, _ = callback(
        {"key": "reco:0", "prefix": "reco", "position": 0, "family": "particles"},
        {"file_path": "/tmp/event.h5", "entry": 3},
        "both",
        "particles",
        {},
        [],
        [],
    )
    assert match_summary == "No matched truth particles"


def test_object_inspector_rejects_stale_selection(callback_app):
    """Selections outside the current mode or family should close the panel."""
    callback = registered_callback(callback_app, "update_object_inspector")
    selection = {"prefix": "truth", "position": 0, "family": "fragments"}

    assert callback(
        selection,
        {"file_path": "/tmp/event.h5", "entry": 3},
        "reco",
        "particles",
    ) == ("", "", [], True)
    assert callback(None, None, "reco", "particles") == ("", "", [], True)


def test_object_inspector_handles_missing_cached_object(callback_app, monkeypatch):
    """Stale positions and unavailable cached products should close cleanly."""
    callback = registered_callback(callback_app, "update_object_inspector")
    selection = {"prefix": "reco", "position": 4, "family": "particles"}
    loaded = {"file_path": "/tmp/event.h5", "entry": 3}
    monkeypatch.setattr(callback_module, "initialize_reader", lambda *args: object())
    monkeypatch.setattr(
        callback_module,
        "load_data",
        lambda *args: ({"reco_particles": []}, None, None),
    )
    assert callback(selection, loaded, "reco", "particles") == ("", "", [], True)

    monkeypatch.setattr(
        callback_module,
        "load_data",
        lambda *args: (_ for _ in ()).throw(OSError("cache unavailable")),
    )
    assert callback(selection, loaded, "reco", "particles") == ("", "", [], True)


def test_entry_label_reports_zero_based_index_range():
    """The entry chip should show the current and maximum valid indexes."""
    assert format_entry_label(0, 100) == "Entry 0/99"
    assert format_entry_label(99, 100) == "Entry 99/99"


def test_restored_object_filter_resolves_saved_subsets():
    """Saved subsets should retain valid keys and default missing sides to all."""
    reco = [{"value": "reco:0"}, {"value": "reco:1"}]
    truth = [{"value": "truth:0"}, {"value": "truth:1"}]

    assert restored_object_filter(
        {"objects": {"reco": ["reco:1", "reco:9"], "truth": []}},
        reco,
        truth,
    ) == ["reco:1"]
    assert restored_object_filter({}, reco, truth) == [
        "reco:0",
        "reco:1",
        "truth:0",
        "truth:1",
    ]


def test_browse_navigation_uses_loaded_hdf5_source():
    """Navigation should use loaded data regardless of the source editor."""
    loaded = {"file_path": "https://example.org/event.h5", "entry": 2}

    for mode in ("path", "browse", "upload", "url"):
        assert (
            navigation_file_path("/tmp/draft-source.json", mode, "button-next", loaded)
            == loaded["file_path"]
        )
        assert (
            navigation_file_path("/tmp/draft-source.json", mode, "button-go", loaded)
            == loaded["file_path"]
        )
        assert (
            navigation_file_path("/tmp/draft-source.json", mode, "input-entry", loaded)
            == loaded["file_path"]
        )
    assert (
        navigation_file_path("/tmp/imported-view.json", "browse", "button-load", loaded)
        == "/tmp/imported-view.json"
    )


def test_display_controls_follow_available_products():
    """Run, object and overlay controls should reject invalid combinations."""
    products = {
        "points",
        "depositions",
        "points_label",
        "depositions_label",
        "truth_particles",
        "truth_interactions",
        "flashes",
    }
    state = display_control_state(
        products,
        mode="reco",
        obj="particles",
        draw_modes=["point", "direction", "vertex", "raw", "flash"],
    )
    run_options, mode, object_options, obj, draw_options, draw_modes = state

    assert [option["value"] for option in run_options] == ["reco", "truth", "both"]
    assert {option["value"] for option in run_options if option["disabled"]} == {
        "reco",
        "both",
    }
    assert (mode, obj) == ("truth", "particles")
    assert {option["value"] for option in object_options if option["disabled"]} == {
        "fragments"
    }
    disabled = {option["value"] for option in draw_options if option["disabled"]}
    assert {"point", "direction", "vertex", "raw", "flash"}.isdisjoint(disabled)
    assert draw_modes == ["point", "direction", "vertex", "raw", "flash"]

    overlay_state = overlay_control_state(draw_options, draw_modes)
    assert overlay_state[1] == ["point", "direction", "vertex", "raw"]
    assert overlay_state[3] == "all"
    assert overlay_state[5] == "off"
    assert compose_draw_modes(overlay_state[1], "matched", "all") == [
        "point",
        "direction",
        "vertex",
        "raw",
        "flash",
        "flash_match_only",
        "crt",
    ]

    interaction_state = display_control_state(
        products,
        mode="truth",
        obj="interactions",
        draw_modes=["point", "direction", "vertex"],
    )
    interaction_options = interaction_state[4]
    interaction_disabled = {
        option["value"] for option in interaction_options if option["disabled"]
    }
    assert {"point", "direction"}.issubset(interaction_disabled)
    assert "vertex" not in interaction_disabled
    assert interaction_state[5] == ["vertex"]

    both_products = {
        "reco_particles",
        "truth_particles",
        "reco_interactions",
        "truth_interactions",
    }
    both_state = display_control_state(
        both_products, mode="both", obj="particles", draw_modes=["vertex"]
    )
    assert both_state[1] == "both"
    assert all(not option["disabled"] for option in both_state[0])
    interaction_state = display_control_state(
        both_products, mode="both", obj="interactions", draw_modes=["vertex"]
    )
    assert interaction_state[5] == ["vertex"]

    fallback = display_control_state(
        {"reco_particles"}, mode="reco", obj="fragments", draw_modes=[]
    )
    assert fallback[3] == "particles"


def test_attribute_picker_options_align_and_filter_search_results():
    """Search should show only matching attributes in aligned rows."""
    hover, color = attribute_options("reco", "particles", search="pid")

    assert [option["value"] for option in hover] == [
        option["value"] for option in color
    ]
    assert all("pid" in option["value"] for option in hover)
    assert "is_contained" not in {option["value"] for option in hover}
    assert "shape" not in {option["value"] for option in hover}

    hover, color = attribute_options("reco", "particles", search="object")
    assert hover == [{"label": "Object ID", "value": "id"}]
    assert color[0]["value"] == ""

    hover, color = attribute_options("reco", "particles")
    color_by_attr = {option["value"]: option for option in color}
    assert color_by_attr["length"]["disabled"] is False
    assert color_by_attr["chi2_per_pid"]["disabled"] is True

    _, truth_color = attribute_options("truth", "particles")
    truth_color_by_attr = {option["value"]: option for option in truth_color}
    for attr in ("pdg_code", "parent_pdg_code", "ancestor_pdg_code"):
        assert truth_color_by_attr[attr]["disabled"] is False

    _, both_color = attribute_options("both", "particles")
    both_color_by_attr = {option["value"]: option for option in both_color}
    assert both_color_by_attr["pdg_code"]["disabled"] is False
    assert both_color_by_attr["ancestor_pdg_code"]["disabled"] is True


def test_colorscale_control_appears_only_for_continuous_colors(callback_app):
    """The compact scale selector should not accompany categorical colors."""
    visibility = registered_callback(callback_app, "update_colorscale_visibility")

    assert visibility("reco", "particles", "points", "depositions", []) == {
        "display": "grid"
    }
    assert visibility("reco", "particles", "points", "shape", []) == {"display": "none"}
    assert visibility("reco", "particles", "points", None, ["raw"]) == {
        "display": "grid"
    }


def test_continuous_colorscale_classification_and_application():
    """Only continuous layer styles should receive a selected named scale."""
    assert continuous_color_attribute("reco", "particles", "depositions")
    assert continuous_color_attribute("truth", "particles", "depositions")
    assert continuous_color_attribute("both", "particles", "depositions")
    assert not continuous_color_attribute("reco", "particles", "shape")
    assert not continuous_color_attribute("reco", "particles", None)

    continuous = SimpleNamespace(
        name="Particles",
        style=PointStyle(colorscale="Inferno"),
        metadata={"attribute_styles": {"depositions": {"colorscale": "Inferno"}}},
    )
    discrete = SimpleNamespace(
        name="Categories",
        style=PointStyle(colorscale=["red", "blue"]),
        metadata={},
    )
    scene = SimpleNamespace(views=[SimpleNamespace(layers=[continuous, discrete])])
    names = apply_continuous_colorscale(scene, "Viridis")

    assert names == {"Particles"}
    assert continuous.style.colorscale == "Viridis"
    assert continuous.metadata["attribute_styles"]["depositions"]["colorscale"] == (
        "Viridis"
    )
    assert discrete.style.colorscale == ["red", "blue"]

    figure = go.Figure(
        data=[
            go.Scatter3d(
                name="Particles",
                marker={"color": [0, 1], "colorscale": "Inferno"},
            ),
            go.Scatter3d(
                name="Categories",
                marker={"color": [0, 1], "colorscale": "Inferno"},
            ),
            go.Scatter3d(
                name="Particles",
                line={"color": [0, 1], "colorscale": "Inferno"},
            ),
            go.Cone(
                name="Particles",
                x=[0],
                y=[0],
                z=[0],
                u=[1],
                v=[0],
                w=[0],
                colorscale="Inferno",
            ),
        ]
    )
    apply_plotly_colorscale(figure, "Viridis", names)
    assert (
        figure.data[0].marker.colorscale
        == go.Scatter3d(marker={"colorscale": "Viridis"}).marker.colorscale
    )
    assert figure.data[1].marker.colorscale != figure.data[0].marker.colorscale
    assert figure.data[2].line.colorscale == figure.data[0].marker.colorscale
    assert figure.data[3].colorscale == figure.data[0].marker.colorscale


def test_plotly_appearance_styles_and_filters_continuous_points():
    """Plotly appearance controls should not alter categorical traces."""
    figure = go.Figure(
        data=[
            go.Scatter3d(
                name="Particles",
                mode="markers",
                x=[0, 1, 2],
                y=[0, 1, 2],
                z=[0, 1, 2],
                text=["a", "b", "c"],
                marker={"size": 2, "color": [1, 10, 100]},
            ),
            go.Scatter3d(
                name="Categories",
                mode="markers",
                x=[0, 1],
                y=[0, 1],
                z=[0, 1],
                marker={"size": 2, "color": [0, 1]},
            ),
        ]
    )
    apply_plotly_appearance(
        figure,
        {"Particles"},
        {
            "point_size": 1.5,
            "opacity": 0.5,
            "transform": "log",
            "domain_mode": "manual",
            "color_min": 1,
            "color_max": 100,
            "range_mode": "range",
            "visible_min": 10,
            "visible_max": 100,
        },
    )

    continuous, categorical = figure.data
    assert list(continuous.x) == [1, 2]
    assert list(continuous.text) == ["b", "c"]
    assert list(continuous.marker.color) == [1, 2]
    assert continuous.marker.size == 3
    assert continuous.marker.opacity == 0.5
    assert continuous.marker.cmin == 0
    assert continuous.marker.cmax == 2
    histogram = figure.layout.meta["appearance_histogram"]
    assert histogram["count"] == 3
    assert histogram["min"] == 0
    assert histogram["max"] == 2
    assert len(histogram["bins"]) == 36
    assert list(categorical.x) == [0, 1]
    assert categorical.marker.size == 3


def test_plotly_appearance_preserves_automatic_source_domain():
    """Automatic appearance should retain SPINE's robust scalar bounds."""
    figure = go.Figure(
        data=[
            go.Scatter3d(
                name="Particles",
                mode="markers",
                x=[0, 1, 2],
                y=[0, 1, 2],
                z=[0, 1, 2],
                marker={
                    "color": [0.1, 1.0, 100.0],
                    "colorscale": "Inferno",
                    "cmin": 0.0,
                    "cmax": 2.0,
                },
            )
        ]
    )

    apply_plotly_appearance(
        figure,
        {"Particles"},
        {
            "point_size": 1.0,
            "opacity": 1.0,
            "transform": "linear",
            "domain_mode": "auto",
            "range_mode": "all",
        },
    )

    assert figure.data[0].marker.cmin == 0.0
    assert figure.data[0].marker.cmax == 2.0


def test_plotly_appearance_handles_auxiliary_and_unusual_traces():
    """Appearance styling should skip auxiliaries and nonnumeric colors cleanly."""
    figure = go.Figure(
        data=[
            go.Scatter3d(name="Lines", mode="lines", x=[0, 1], y=[0, 1], z=[0, 1]),
            go.Scatter3d(
                name="Particles",
                mode="markers",
                x=[0],
                y=[0],
                z=[0],
                marker={"color": [1]},
                meta={"kind": "vertex"},
            ),
            go.Scatter3d(
                name="Particles",
                mode="markers",
                x=[0, 1],
                y=[0, 1],
                z=[0, 1],
                marker={"color": ["red", "blue"]},
            ),
        ]
    )

    apply_plotly_appearance(
        figure,
        {"Particles"},
        {"point_size": 2.0, "opacity": 0.5},
    )

    assert figure.data[0].mode == "lines"
    assert figure.data[1].marker.size is None
    assert figure.data[2].marker.size == 4
    assert list(figure.data[2].marker.color) == ["red", "blue"]
    assert figure.layout.meta["appearance_histogram"]["bins"] == []


def test_plotly_appearance_automatic_log_domain_and_constant_histogram():
    """Automatic log bounds should honor sources and constant distributions."""
    figure = go.Figure(
        data=[
            go.Scatter3d(
                name="Particles",
                mode="markers",
                x=[0, 1],
                y=[0, 1],
                z=[0, 1],
                marker={"color": [10, 10], "cmin": 1},
            )
        ]
    )

    apply_plotly_appearance(
        figure,
        {"Particles"},
        {
            "transform": "log",
            "domain_mode": "auto",
            "range_mode": "all",
        },
    )

    assert figure.data[0].marker.cmin == 0
    assert figure.data[0].marker.cmax == 1
    histogram = figure.layout.meta["appearance_histogram"]
    assert histogram["count"] == 2
    assert histogram["min"] == histogram["max"] == 1


def test_truth_point_sources_limit_pointwise_attributes():
    """Truth hover and color fields should follow the selected point cloud."""
    label, _ = attribute_options("truth", "particles", truth_point_mode="points")
    adapted, _ = attribute_options(
        "truth", "particles", truth_point_mode="points_adapt"
    )
    geant4, _ = attribute_options("truth", "particles", truth_point_mode="points_g4")
    label = {option["value"] for option in label}
    adapted = {option["value"] for option in adapted}
    geant4 = {option["value"] for option in geant4}

    assert {"depositions", "depositions_q", "sources"} <= label
    assert not label & {"depositions_adapt", "sources_adapt", "depositions_g4"}
    assert {
        "depositions_adapt",
        "depositions_adapt_q",
        "sources_adapt",
    } <= adapted
    assert not adapted & {"depositions", "sources", "depositions_g4"}
    assert "depositions_g4" in geant4
    assert not geant4 & {"depositions", "depositions_adapt", "sources_adapt"}

    both, _ = attribute_options("both", "particles", truth_point_mode="points_adapt")
    assert (
        not {option["value"] for option in both}
        & callback_module.TRUTH_POINTWISE_ATTRIBUTES
    )


def test_truth_point_control_uses_event_backing_arrays():
    """Point modes without object indexes should remain visibly unavailable."""
    particle = SimpleNamespace(index=[0], index_adapt=[], index_g4=[0])
    data = {
        "points_label": [[0, 0, 0]],
        "points": [[0, 0, 0]],
        "points_g4": [[0, 0, 0]],
        "truth_particles": [particle],
    }
    options, value, style = callback_module.truth_point_control_state(
        data, "truth", "particles", "points_adapt"
    )
    enabled = {option["value"] for option in options if not option["disabled"]}

    assert enabled == {"points", "points_g4"}
    assert value == "points"
    assert style == {"display": "block"}
    assert callback_module.truth_point_control_state(data, "reco", "particles")[2] == {
        "display": "none"
    }


def test_application_serves_webgl_asset_and_callback_graph():
    """The application factory should expose the viewer and valid dependencies."""
    app = create_app()
    client = app.server.test_client()

    index = client.get("/")
    asset = client.get("/assets/webgl-viewer.js")
    refresh_asset = client.get("/assets/refresh-controls.js")
    shortcut_asset = client.get("/assets/keyboard-shortcuts.js")
    share_asset = client.get("/assets/share-state.js")
    gif_asset = client.get("/assets/gif-encoder.js")
    logo_assets = {
        name: client.get(f"/assets/{name}.png")
        for name in (
            "spine-logo-dark",
            "spine-logo-light",
            "dune-logo",
            "icarus-logo",
            "sbnd-logo",
        )
    }
    dependencies = client.get("/_dash-dependencies")

    assert index.status_code == 200
    assert asset.status_code == 200
    assert shortcut_asset.status_code == 200
    assert b"class Viewer" in asset.data
    assert b"this.syncCameras = root.dataset.syncCameras" in asset.data
    assert b'this.showAxes = root.dataset.showAxes !== "false"' in asset.data
    assert b"setAxesVisible(visible)" in asset.data
    assert b"if (uSymbol != 0 && distanceToEdge < 0.0) discard" in asset.data
    assert b"outColor = vColor" in asset.data
    assert b"const NAMED_COLOR_SCALES" in asset.data
    assert b'viridis: ["#440154"' in asset.data
    assert b'rainbow: ["#96005a"' in asset.data
    assert b'hot: ["#000000"' in asset.data
    assert b"renderAppearanceHistogram(canvas, values" in asset.data
    assert b"renderAppearanceHistogramData(canvas, histogram" in asset.data
    assert b"appearance_histogram" in asset.data
    assert b"const selectionIds = item.selectionIds ? [] : null" in asset.data
    assert b"item.activeSelectionIds = selectionIds" in asset.data
    assert b'canvas.addEventListener("pointerdown"' in asset.data
    assert b'set_props("radio-visible-range"' in asset.data
    assert b"setTimeout(drawPlotlyHistogram, 100)" in asset.data
    assert b"if (!picker?.open || !plot?.data" in asset.data
    assert b"Math.max(3.5, item.source.style?.size || 3)" in asset.data
    assert b"detectorBasis(this.scene.metadata.up_dir)" in asset.data
    assert b"cameraDirection(camera, this.cameraBasis)" in asset.data
    assert b"const camera = this.cameras[index]" in asset.data
    assert b"this.mixedObjectViews" in asset.data
    assert b'document.body.classList.add("scene-loading")' in asset.data
    assert b'document.body.classList.remove("scene-loading")' in asset.data
    assert b'plot.once("plotly_afterplot", complete)' in asset.data
    assert b'afterBrowserPaint(() => endSceneLoad("dash"))' in asset.data
    assert b'document.querySelector(".webgl-viewer[data-scene-url]")' in asset.data
    assert b"queueActivity(sourceActivity())" in asset.data
    assert b'queueActivity("Loading entry' in asset.data
    assert b'"Updating scene' in asset.data
    assert b'`Rendering ${renderer === "plotly" ? "Plotly" : "WebGL"}' in asset.data
    assert b'`Downloading ${name || "file"} from ${url.hostname}' in asset.data
    assert b"`Loading WebGL scene (${megabytes.toFixed(1)} MB)" in asset.data
    assert b"renderAttributeRows" in refresh_asset.data
    assert b"attribute-picker-row" in refresh_asset.data
    assert b"hoverOptions.sort((left, right)" in refresh_asset.data
    assert b"pinSelectedAttributeRows" in refresh_asset.data
    assert b"pickerOpen && currentOrder.size" in refresh_asset.data
    assert b"list.offsetWidth - list.clientWidth" in refresh_asset.data
    assert b'"--attribute-scrollbar-width"' in refresh_asset.data
    assert b'getElementById("input-attribute-search")' in refresh_asset.data
    assert b'"arrowleft"' in shortcut_asset.data
    assert b'"arrowright"' in shortcut_asset.data
    assert b'"#button-reset-view"' in shortcut_asset.data
    assert b'input[value="axes"]' in shortcut_asset.data
    assert b'"#button-save-png"' in shortcut_asset.data
    assert b'"#button-export-view"' in shortcut_asset.data
    assert b'"#help-menu > summary"' in shortcut_asset.data
    assert b'input[value="split_scene"]' not in shortcut_asset.data
    assert b'input[value="sync"]' not in shortcut_asset.data
    assert b"hasTextFocus(event.target)" in shortcut_asset.data
    assert b'hoverInput.className = "attribute-picker-hover-input"' in (
        refresh_asset.data
    )
    assert b"const next = new Set(selectedAttrs)" in refresh_asset.data
    assert b"if (input.checked) next.add(input.value)" in refresh_asset.data
    assert b"hoverInput.click()" in refresh_asset.data
    assert b'const isObjectId = value === "id"' in refresh_asset.data
    assert b"Object ID is always shown in the tooltip" in refresh_asset.data
    assert b"`${qualifier} ${lines[0]}`" in asset.data
    assert b'item.source.metadata.kind === "vertex"' in asset.data
    assert b"return 2.25 * size" in asset.data
    assert b'item.source.type !== "vector"' in asset.data
    assert b'best.item.source.type === "vector"' in asset.data
    assert b'["vx", "vy", "vz"]' in asset.data
    assert b"formatPointCoordinate(value)" in asset.data
    assert b"best.item.activeSourceIndices[best.vertex]" in asset.data
    assert b"attributeValues" in asset.data
    assert b"long_form_attributes" in asset.data
    assert b"root._spinalTapSceneUrl === sceneUrl" in asset.data
    assert b'attributeFilter: ["data-scene-url", "data-dash-is-loading"]' in asset.data
    assert b'return "True"' in asset.data
    assert b'return "False"' in asset.data
    assert refresh_asset.status_code == 200
    assert b"refreshAppearanceHistogram()" in refresh_asset.data
    assert b"store-dropdown-commit" in refresh_asset.data
    assert b"markDirty" in refresh_asset.data
    assert b'"truth-point-control"' in refresh_asset.data
    assert b'"log-panel"' in refresh_asset.data
    assert b'"export-branding-menu"' in refresh_asset.data
    assert b"!picker.contains(event.target)" in refresh_asset.data
    assert share_asset.status_code == 200
    assert gif_asset.status_code == 200
    assert all(asset.status_code == 200 for asset in logo_assets.values())
    assert all(asset.mimetype == "image/png" for asset in logo_assets.values())
    assert b"GIF89a" in gif_asset.data
    assert b"class Encoder" in gif_asset.data
    assert b"nextCode > (1 << codeSize)" in gif_asset.data
    assert b"base64UrlEncode" in share_asset.data
    assert b"decodeHash" in share_asset.data
    assert b"captureCamera" in share_asset.data
    assert b"restoreCamera" in share_asset.data
    assert b"stableAttempts >= 10" in share_asset.data
    assert b"downloadJson" in share_asset.data
    assert b"exportBaseName" in share_asset.data
    assert b"function sourceStem(source)" in share_asset.data
    assert b".slice(0, 48)" in share_asset.data
    assert b"resetView" in share_asset.data
    assert b"saveImage" in share_asset.data
    assert b"saveGif" in share_asset.data
    assert b"saveHtml" in share_asset.data
    assert b"serializablePlotlyFigure" in share_asset.data
    assert b"brandingAssets" in share_asset.data
    assert b"function darkTheme()" in share_asset.data
    assert b'darkTheme() ? "spine-logo-light.png" : "spine-logo-dark.png"' in (
        share_asset.data
    )
    assert b"watermarkBadge" not in share_asset.data
    assert b"drawBranding" in share_asset.data
    assert b"plotlyBrandingImages" in share_asset.data
    assert b"function imageDataUrl(image)" in share_asset.data
    assert b"source: imageDataUrl(asset.image)" in share_asset.data
    assert b'if (name.includes("icarus"))' in share_asset.data
    assert b'if (name.includes("sbnd"))' in share_asset.data
    assert b'name.includes("dune")' in share_asset.data
    assert b'name.includes("2x2")' in share_asset.data
    assert b'name.includes("nd-lar")' in share_asset.data
    assert b'name.includes("ndlar")' not in share_asset.data
    assert b"`${exportBaseName(state)}.html`" in share_asset.data
    assert b"`${exportBaseName(payload)}.json`" in share_asset.data
    assert b'async saveImage(filename = "spinal_tap_event_display.png"' in asset.data
    assert (
        b"await this.drawGifOverlay(context, output.width, output.height)" in asset.data
    )
    assert b"if (overlay) await overlay" in asset.data
    assert b"async saveGif(" in asset.data
    assert b'filename = "spinal_tap_event_display.gif"' in asset.data
    assert b"const frames = 180" in asset.data
    assert b"const frameDelay = 2" in asset.data
    assert b"reportError" in share_asset.data
    assert dependencies.status_code == 200
    callback_graph = dependencies.get_json()
    assert any(callback["output"] == "store-color.data" for callback in callback_graph)
    share_state = next(
        callback
        for callback in callback_graph
        if callback["output"].startswith("..store-share-state.data...")
    )
    assert {
        "id": "checklist-export-watermarks",
        "property": "value",
    } in share_state["inputs"]
    assert {
        ("input-point-size", "value"),
        ("input-point-opacity", "value"),
        ("radio-color-transform", "value"),
        ("radio-color-domain", "value"),
        ("input-color-min", "value"),
        ("input-color-max", "value"),
        ("radio-visible-range", "value"),
        ("input-visible-min", "value"),
        ("input-visible-max", "value"),
    }.issubset({(item["id"], item["property"]) for item in share_state["inputs"]})


def test_shared_view_callbacks_capture_and_restore_in_stages():
    """Shared links should load the event before filters and cameras."""
    app = create_app()
    dependencies = app.server.test_client().get("/_dash-dependencies").get_json()

    outputs = {callback["output"] for callback in dependencies}
    assert "checklist-draw-mode-2.style" in outputs
    assert "store-share-request.data" in outputs
    assert "store-share-pending.data" in outputs
    assert "store-share-applied.data" in outputs
    assert "store-view-action.data" in outputs
    assert "store-source-memory.data" in outputs
    assert "button-share.children" in outputs
    assert any(
        "store-share-state.data" in output and "button-share.disabled" in output
        for output in outputs
    )

    restore = next(
        callback
        for callback in dependencies
        if callback["output"] == "store-share-applied.data"
    )
    restore_inputs = {(item["id"], item["property"]) for item in restore["inputs"]}
    assert ("store-loaded-event", "data") in restore_inputs
    assert ("dropdown-reco-filter", "options") in restore_inputs
    assert ("dropdown-truth-filter", "options") in restore_inputs
    assert ("store-object-filter", "data") in restore_inputs

    actions = next(
        callback
        for callback in dependencies
        if callback["output"] == "store-view-action.data"
    )
    action_inputs = {(item["id"], item["property"]) for item in actions["inputs"]}
    assert action_inputs == {
        ("button-reset-view", "n_clicks"),
        ("button-save-png", "n_clicks"),
        ("button-save-scene", "n_clicks"),
        ("button-export-view", "n_clicks"),
    }

    graph = next(
        callback
        for callback in dependencies
        if "div-evd.children" in callback["output"]
    )
    assert "store-share-request.data" in graph["output"]
    graph_state = {(item["id"], item["property"]) for item in graph["state"]}
    graph_inputs = {(item["id"], item["property"]) for item in graph["inputs"]}
    assert ("store-share-pending", "data") in graph_inputs
    assert ("source-mode", "value") in graph_state
    assert ("entry-mode", "value") in graph_state
    assert ("input-entry", "disabled") not in graph_state

    source_memory = next(
        callback
        for callback in dependencies
        if callback["output"] == "store-source-memory.data"
    )
    assert source_memory["inputs"] == [{"id": "store-loaded-event", "property": "data"}]


def test_plotly_uses_the_shared_reset_and_export_actions():
    """Plotly should not duplicate actions supplied by the common tray."""
    assert {"toImage", "resetCameraDefault3d"}.issubset(
        set(GRAPH_CONFIG["modeBarButtonsToRemove"])
    )


def test_view_state_is_validated_and_gets_a_restore_revision(tmp_path):
    """Valid JSON paths should always trigger a fresh restoration."""
    state = {
        "version": 1,
        "file": "/data/example.h5",
        "entry": 4,
        "display": {"overlays": [], "view": ["sync"], "axes": False},
        "attributes": {"hover": ["shape"]},
        "objects": {"reco": "all", "truth": ["truth:2"]},
    }

    path = tmp_path / "view.json"
    path.write_text(json.dumps(state))
    first = load_view_state(str(path))
    second = load_view_state(str(path))

    assert first["entry"] == 4
    assert first["display"]["axes"] is False
    assert first["restore_nonce"] != second["restore_nonce"]


@pytest.mark.parametrize(
    "state, message",
    [
        ({"version": 2, "file": "/data/a.h5", "entry": 0}, "version"),
        ({"version": 1, "entry": 0}, "file path"),
        (
            {"version": 1, "file": "/data/a.h5", "entry": -1},
            "entry number",
        ),
        (
            {
                "version": 1,
                "file": "/data/a.h5",
                "entry": 0,
                "objects": {"reco": "not-all"},
            },
            "object selection",
        ),
        (
            {
                "version": 1,
                "file": "/data/a.h5",
                "entry": 0,
                "display": {"truth_points": "invented"},
            },
            "truth point source",
        ),
        (
            {
                "version": 1,
                "file": "/data/a.h5",
                "entry": 0,
                "display": {"axes": "yes"},
            },
            "axes setting",
        ),
        (
            {
                "version": 1,
                "file": "/data/a.h5",
                "entry": 0,
                "attributes": {"colorscale": ["Inferno"]},
            },
            "continuous colorscale",
        ),
        (
            {
                "version": 1,
                "file": "/data/a.h5",
                "entry": 0,
                "attributes": {"appearance": {"transform": "square"}},
            },
            "color transform",
        ),
    ],
)
def test_view_state_rejects_invalid_schema(state, message):
    """Malformed imports should provide a useful visible error message."""
    with pytest.raises(ValueError, match=message):
        validate_view_state(state)


@pytest.mark.parametrize(
    "state,message",
    [
        ([], "JSON object"),
        ({"version": 1, "file": "/a.h5", "entry": "x"}, "entry number"),
        (
            {"version": 1, "file": "/a.h5", "entry": 0, "display": ["bad"]},
            "control groups",
        ),
        (
            {
                "version": 1,
                "file": "/a.h5",
                "entry": 0,
                "display": {"overlays": "point"},
            },
            "option list",
        ),
    ],
)
def test_view_state_rejects_additional_invalid_types(state, message):
    """Type errors at every schema level should remain explicit."""
    with pytest.raises(ValueError, match=message):
        validate_view_state(state)


@pytest.mark.parametrize(
    "appearance,message",
    [
        ([], "appearance settings"),
        ({"domain_mode": "fixed"}, "color domain"),
        ({"range_mode": "window"}, "visible range"),
        ({"point_size": "large"}, "point_size"),
        ({"point_size": 0.25}, "point_size"),
        ({"opacity": 0.0}, "opacity"),
    ],
)
def test_view_state_rejects_invalid_appearance(appearance, message):
    """Imported point styling should enforce its complete schema and bounds."""
    state = {
        "version": 1,
        "file": "/a.h5",
        "entry": 0,
        "attributes": {"appearance": appearance},
    }
    with pytest.raises(ValueError, match=message):
        validate_view_state(state)


def test_load_view_state_reports_text_and_json_errors(tmp_path):
    """Imported view decoding failures should include actionable context."""
    invalid_utf8 = tmp_path / "binary.json"
    invalid_utf8.write_bytes(b"\xff\xfe")
    with pytest.raises(ValueError, match="UTF-8 JSON"):
        load_view_state(str(invalid_utf8))

    invalid_json = tmp_path / "broken.json"
    invalid_json.write_text("{\ninvalid")
    with pytest.raises(ValueError, match="line 2, column 1"):
        load_view_state(str(invalid_json))


def test_access_and_manifest_validation_branches(monkeypatch, tmp_path):
    """Authentication should cover URLs, uploads, shared paths and manifests."""
    from spinal_tap import app, cache

    monkeypatch.setattr(app, "REQUIRE_AUTH", False)
    assert callback_module.validate_file_access("/anything") == (True, None)

    monkeypatch.setattr(app, "REQUIRE_AUTH", True)
    monkeypatch.setattr(app, "get_experiment", lambda: None)
    assert callback_module.validate_file_access("/anything")[0] is False

    monkeypatch.setattr(app, "get_experiment", lambda: "dune")
    monkeypatch.setattr(cache, "ALLOW_URLS", True)
    assert callback_module.validate_file_access("https://example.org/a") == (True, None)
    monkeypatch.setattr(cache, "ALLOW_URLS", False)
    assert callback_module.validate_file_access("https://example.org/a")[0] is False

    monkeypatch.setattr(
        cache.cache_manager, "owns_path", lambda path: path == "/upload"
    )
    assert callback_module.validate_file_access("/upload") == (True, None)
    monkeypatch.setattr(app, "SHARED_FOLDERS", ["/data/public"])
    monkeypatch.setattr(app, "EXPERIMENT_PATHS", {"dune": ["/data/dune"]})
    assert callback_module.validate_file_access("/data/public/a.h5") == (True, None)
    assert callback_module.validate_file_access("/data/dune/a.h5") == (True, None)

    manifest = tmp_path / "files.list"
    manifest.write_text("relative.h5\nhttps://example.org/remote.h5\n")
    checks = []

    def validate(path):
        checks.append(path)
        return (not path.startswith("https"), "remote denied")

    monkeypatch.setattr(callback_module, "validate_file_access", validate)
    valid, message = validate_manifest_access(str(manifest))
    assert not valid
    assert "remote.h5" in message
    assert checks[0] == str(tmp_path / "relative.h5")
    monkeypatch.setattr(
        callback_module, "validate_file_access", lambda path: (True, None)
    )
    assert validate_manifest_access(str(manifest)) == (True, None)
    assert parse_optional_int("") is None
    assert parse_optional_int(None) is None
    assert parse_optional_int("4") == 4


def test_scene_refresh_inputs_use_committed_multi_selects():
    """Scene rebuilds should use close commits, not raw multi-select changes."""
    app = create_app()
    dependencies = app.server.test_client().get("/_dash-dependencies").get_json()
    graph_callback = next(
        callback
        for callback in dependencies
        if "div-evd.children" in callback["output"]
    )
    inputs = {(item["id"], item["property"]) for item in graph_callback["inputs"]}
    states = {(item["id"], item["property"]) for item in graph_callback["state"]}

    assert ("store-dropdown-commit", "data") in inputs
    assert ("input-file-path", "n_submit") in inputs
    for field in ("input-entry", "input-run", "input-subrun", "input-event"):
        assert (field, "n_submit") in inputs
    assert ("radio-run-mode", "value") in inputs
    assert ("radio-truth-point-mode", "value") in inputs
    assert ("radio-object-mode", "value") in inputs
    assert ("dropdown-geo", "value") in inputs
    assert ("dropdown-geo-tag", "value") in inputs
    assert ("dropdown-attr", "value") not in inputs
    assert ("checklist-draw-mode-1", "value") in inputs
    assert ("radio-flash-mode", "value") in inputs
    assert ("radio-crt-mode", "value") in inputs
    assert ("checklist-draw-mode-2", "value") in inputs
    assert ("checklist-show-axes", "value") not in inputs
    assert ("checklist-show-axes", "value") in states
    assert ("store-filter-render-request", "data") in inputs
    assert ("store-object-filter", "data") not in inputs

    filter_callback = next(
        callback
        for callback in dependencies
        if "store-object-filter.data" in callback["output"]
        and "store-filter-render-request.data" in callback["output"]
    )
    filter_inputs = {
        (item["id"], item["property"]) for item in filter_callback["inputs"]
    }
    assert filter_inputs == {
        ("dropdown-reco-filter", "value"),
        ("dropdown-reco-filter", "options"),
        ("dropdown-truth-filter", "value"),
        ("dropdown-truth-filter", "options"),
        ("store-link-filters", "data"),
        ("store-object-match-links", "data"),
        ("store-loaded-event", "data"),
    }

    pending_callback = next(
        callback
        for callback in dependencies
        if callback["output"] == "store-dropdown-pending.data"
    )
    pending_inputs = {
        (item["id"], item["property"]) for item in pending_callback["inputs"]
    }
    assert pending_inputs == {
        ("dropdown-attr", "value"),
        ("dropdown-attr-color", "value"),
    }

    attribute_callback = next(
        callback
        for callback in dependencies
        if "dropdown-attr-color.options" in callback["output"]
    )
    attribute_inputs = {
        (item["id"], item["property"]) for item in attribute_callback["inputs"]
    }
    assert attribute_inputs == {
        ("radio-run-mode", "value"),
        ("radio-object-mode", "value"),
        ("radio-truth-point-mode", "value"),
        ("input-attribute-search", "value"),
    }

    axes_callback = next(
        callback for callback in dependencies if callback["output"] == "store-axes.data"
    )
    assert axes_callback["inputs"] == [
        {"id": "checklist-show-axes", "property": "value"}
    ]


def test_configure_geometry_respects_explicit_clear(monkeypatch):
    """Clearing geometry should suppress the file's embedded configuration."""
    calls = []

    class Manager:
        def initialize_or_get(self, *args, **kwargs):
            calls.append((args, kwargs))

        @classmethod
        def reset(cls):
            calls.append("reset")

    monkeypatch.setattr(callback_module, "GeoManager", Manager)

    configure_geometry(None, None, {"detector": "2x2"}, "auto")
    configure_geometry(None, None, {"detector": "2x2"}, "disabled")
    configure_geometry("icarus", "v1", {"detector": "2x2"}, "manual")
    configure_geometry(None, None, None, "auto")

    assert calls == [
        ((), {"detector": "2x2"}),
        "reset",
        (("icarus", "v1"), {}),
        "reset",
    ]


def test_geometry_choice_resets_to_auto_for_new_file():
    """An explicit opt-out should persist within one file but not across files."""
    state = {"file_path": "/data/first.h5", "geometry": None}

    _, same_choice, same_changed = geometry_choice_for_file(
        "/sdf/data/neutrino/first.h5", state, "disabled"
    )
    _, new_choice, new_changed = geometry_choice_for_file(
        "/data/second.h5", state, "disabled"
    )

    assert (same_choice, same_changed) == ("disabled", False)
    assert (new_choice, new_changed) == ("auto", True)


def test_geometry_choice_is_auto_for_the_first_file():
    """An empty initial dropdown must not disable embedded file geometry."""
    _, choice, changed = geometry_choice_for_file("/data/nd-lar.h5", None, "disabled")

    assert (choice, changed) == ("auto", False)


def test_embedded_geometry_reflection_accepts_pending_tag():
    """Populating automatic geometry controls should not request a redraw."""
    state = {"geometry": {"detector": "nd-lar", "tag": "up4-1"}}

    assert is_embedded_geometry_selection("nd-lar", None, state)
    assert is_embedded_geometry_selection("ND-LAR", "up4-1", state)
    assert not is_embedded_geometry_selection("nd-lar", "up3", state)
    assert not is_embedded_geometry_selection("2x2", None, state)


def test_registered_control_callbacks(callback_app, monkeypatch):
    """Server callbacks should apply capabilities, geometry and picker options."""
    display = registered_callback(callback_app, "update_display_controls")
    assert display(None) == (no_update,) * 13
    control_state = {
        "run_options": [{"label": "Reco", "value": "reco"}],
        "run_value": "reco",
        "object_options": [{"label": "Particles", "value": "particles"}],
        "object_value": "particles",
        "draw_options": [
            {"label": label, "value": value, "disabled": False}
            for label, value in callback_module.DRAW_MODE_OPTIONS
        ],
        "draw_value": ["point", "flash_match_only", "crt"],
        "truth_point_options": [
            {"label": "Label", "value": "points", "disabled": False}
        ],
        "truth_point_value": "points",
        "truth_point_style": {"display": "none"},
    }
    result = display(control_state)
    assert result[1] == "reco"
    assert result[5] == ["point"]
    assert result[7] == "matched"
    assert result[9] == "all"

    monkeypatch.setattr(
        "spine.geo.factories.geo_dict",
        lambda: {
            "old": {"name": "2x2", "tag": "v1", "version": "1.0"},
            "new": {"name": "2x2", "tag": "v2", "version": "2.0"},
            "other": {"name": "icarus", "tag": "", "version": "3.0"},
        },
    )
    tags = registered_callback(callback_app, "update_tag_options")
    assert tags(None, None) == ([], None)
    options, selected = tags("2X2", {"geometry": {"detector": "2x2", "tag": "v1"}})
    assert [option["value"] for option in options] == ["v2", "v1"]
    assert selected == "v1"
    assert tags("icarus", {"geometry": {"detector": "2x2"}})[1] == "3.0"

    embedded = registered_callback(callback_app, "show_embedded_geometry")
    assert embedded(None, 0) is no_update
    assert embedded({}, 0) is None
    assert embedded({"geometry": {"detector": "ND-LAr"}}, 1) == "nd-lar"

    restore = registered_callback(callback_app, "update_geometry_restore")
    assert restore(None, None) == (True, "No detected geometry to restore")
    detected = {"geometry": {"detector": "ND-LAr", "tag": "up4-1"}}
    assert restore(detected, None) == (
        False,
        "Restore detected geometry: ND-LAr · up4-1",
    )
    assert restore(detected, "nd-lar")[0] is True

    monkeypatch.setattr(
        callback_module,
        "attribute_options",
        lambda *args: ([{"value": "x"}], [{"value": ""}]),
    )
    attributes = registered_callback(callback_app, "update_attribute_options")
    hover, color, payload = attributes("reco", "particles", "points", "x")
    assert payload == {"hover": hover, "color": color}


def test_registered_login_entry_and_source_callbacks(callback_app, monkeypatch):
    """Form callbacks should expose every validation and display state."""
    login = registered_callback(callback_app, "handle_login")
    assert login(0, None, None) == ("", None)
    assert login(1, None, "secret") == ("Please select an experiment", None)
    assert login(1, "dune", None) == ("Please enter a password", None)
    monkeypatch.setattr("spinal_tap.app.check_password", lambda *args: True)
    assert login(1, "dune", "secret") == (
        "",
        {"experiment": "dune", "password": "secret"},
    )
    monkeypatch.setattr("spinal_tap.app.check_password", lambda *args: False)
    assert login(1, "dune", "wrong") == ("Invalid credentials", None)

    entry = registered_callback(callback_app, "update_entry_input")
    entry_state = entry("entry", {"file_path": "a.h5"})
    assert entry_state[0]["display"] == "block"
    assert entry_state[1]["display"] == "none"
    assert entry_state[4] is False
    assert entry_state[-1] is False
    run_state = entry("run", None)
    assert run_state[0]["display"] == "none"
    assert run_state[1]["display"] == "block"
    assert all(run_state[index] for index in (4, 5, 6, 7, 9))

    source = registered_callback(callback_app, "update_source_mode")
    assert source("browse")[1:4] == (
        True,
        {"display": "none"},
        {"display": "grid"},
    )
    assert source("url")[0].startswith("HTTPS URL")
    assert source("path")[0].startswith("HDF5")


class FakeReader:
    """Minimal reader contract used by update-graph tests."""

    run_map = {(1, 2, 3): 0}

    def __len__(self):
        return 2

    def get_run_event_index(self, run, subrun, event):
        if (run, subrun, event) != (1, 2, 3):
            raise KeyError(
                f"Could not find (run={run}, subrun={subrun}, event={event})."
            )
        return 0


class FakeDrawer:
    """Capture renderer requests while returning portable stand-ins."""

    calls = []
    fail = False

    def __init__(self, data, **kwargs):
        self.calls.append(("init", data, kwargs))

    def get_scene(self, *args, **kwargs):
        if self.fail:
            raise ValueError("cannot draw")
        self.calls.append(("scene", args, kwargs))
        return SimpleNamespace(metadata={"up_dir": [0.0, 1.0, 0.0]}, views=[])

    def get(self, *args, **kwargs):
        self.calls.append(("plotly", args, kwargs))
        return go.Figure(layout={"scene": {}})


def graph_arguments(**overrides):
    """Return a complete keyword argument set for the graph callback."""
    values = {
        "n_clicks_load": 1,
        "source_request": None,
        "n_submit_source": 0,
        "share_pending": None,
        "n_clicks_go": 0,
        "n_submit_entry": 0,
        "n_submit_run": 0,
        "n_submit_subrun": 0,
        "n_submit_event": 0,
        "n_clicks_prev": 0,
        "n_clicks_next": 0,
        "draw_attr": None,
        "appearance_render_request": None,
        "colorscale": "Inferno",
        "point_size": 1.0,
        "point_opacity": 1.0,
        "color_transform": "linear",
        "color_domain_mode": "auto",
        "color_min": None,
        "color_max": None,
        "visible_range_mode": "all",
        "visible_min": None,
        "visible_max": None,
        "filter_render_request": None,
        "object_filter": [],
        "renderer": [],
        "mode": "reco",
        "truth_point_mode": "points",
        "obj": "particles",
        "detector": None,
        "detector_tag": None,
        "dropdown_commit": None,
        "core_draw_modes": [],
        "flash_mode": "off",
        "crt_mode": "off",
        "draw_mode_2": ["split_scene", "sync"],
        "axes": ["axes"],
        "file_path": "/tmp/events.h5",
        "source_mode": "path",
        "entry": 0,
        "run": None,
        "subrun": None,
        "event": None,
        "entry_mode": "entry",
        "theme": [],
        "attrs": [],
        "geometry_choice": "auto",
        "entry_state": None,
        "loaded_event": None,
        "previous_control_state": None,
        "share_applied": None,
    }
    values.update(overrides)
    return values


@pytest.fixture
def graph_callback(callback_app, monkeypatch):
    """Prepare the graph callback with deterministic lightweight dependencies."""
    FakeDrawer.calls = []
    FakeDrawer.fail = False
    reader = FakeReader()
    data = {"reco_particles": [SimpleNamespace(id=0, match_ids=[])]}
    monkeypatch.setattr(callback_module, "Drawer", FakeDrawer)
    monkeypatch.setattr(
        callback_module, "validate_file_access", lambda path: (True, None)
    )
    monkeypatch.setattr(callback_module, "classify_source", lambda path: ("hdf5", path))
    monkeypatch.setattr(callback_module, "initialize_reader", lambda *args: reader)
    monkeypatch.setattr(
        callback_module, "get_reader_products", lambda reader: {"reco_particles"}
    )
    monkeypatch.setattr(
        callback_module,
        "load_data",
        lambda *args: (data, {"detector": "2x2"}, 1, 2, 3),
    )
    monkeypatch.setattr(
        callback_module,
        "build_object_filter_options",
        lambda data, prefix, obj: [{"label": "Particle 0", "value": f"{prefix}:0"}],
    )
    monkeypatch.setattr(
        callback_module,
        "filter_event_objects",
        lambda data, mode, obj, active: (data, len(active), 1),
    )
    monkeypatch.setattr(callback_module, "build_object_match_links", lambda *args: {})
    monkeypatch.setattr(callback_module, "configure_geometry", lambda *args: None)
    monkeypatch.setattr(callback_module, "object_attributes", lambda *args: [])
    monkeypatch.setattr(callback_module.scene_store, "put", lambda scene: "scene-token")
    monkeypatch.setattr("spinal_tap.cache.cache_manager.owns_path", lambda path: False)
    return registered_callback(callback_app, "update_graph")


def test_graph_callback_renders_webgl_and_plotly(graph_callback, monkeypatch):
    """Both renderers should use the same loaded event and control payload."""
    monkeypatch.setattr(
        callback_module, "ctx", SimpleNamespace(triggered_id="button-load")
    )
    result = graph_callback(**graph_arguments())
    assert isinstance(result[0], html.Div)
    assert result[0].id == "webgl-viewer"
    assert result[0].to_plotly_json()["props"]["data-scene-url"] == (
        "/scene/scene-token.bin"
    )
    assert result[0].to_plotly_json()["props"]["data-show-axes"] == "true"
    assert json.loads(result[0].to_plotly_json()["props"]["data-appearance"]) == {
        "point_size": 1.0,
        "opacity": 1.0,
        "colorscale": "Inferno",
        "transform": "linear",
        "domain_mode": "auto",
        "color_min": None,
        "color_max": None,
        "range_mode": "all",
        "visible_min": None,
        "visible_max": None,
    }
    assert result[14]["file_path"] == "/tmp/events.h5"
    assert result[14]["num_entries"] == 2
    assert result[15]["run_value"] == "reco"
    assert result[7] == "log-panel is-success"
    init_call = next(call for call in FakeDrawer.calls if call[0] == "init")
    assert init_call[2]["truth_point_mode"] == "points"
    assert init_call[2]["truth_dep_mode"] == "depositions"

    result = graph_callback(**graph_arguments(renderer=["plotly"]))
    assert isinstance(result[0], dcc.Graph)
    assert result[0].figure.layout.showlegend is False
    assert result[0].figure.layout.scene.xaxis.visible is True
    assert any(call[0] == "plotly" for call in FakeDrawer.calls)

    result = graph_callback(**graph_arguments(renderer=["plotly"], axes=[]))
    assert result[0].figure.layout.scene.xaxis.visible is False
    result = graph_callback(**graph_arguments(axes=[]))
    assert result[0].to_plotly_json()["props"]["data-show-axes"] == "false"

    # A saved point source that the new event cannot provide falls back to
    # labels before Drawer sees it.
    FakeDrawer.calls.clear()
    result = graph_callback(**graph_arguments(truth_point_mode="points_g4"))
    init_call = next(call for call in FakeDrawer.calls if call[0] == "init")
    assert init_call[2]["truth_point_mode"] == "points"
    assert result[15]["truth_point_value"] == "points"


def test_shared_link_pending_state_opens_its_scene(graph_callback, monkeypatch):
    """A decoded share link should render without a separate Open or Go click."""
    monkeypatch.setattr(
        callback_module, "ctx", SimpleNamespace(triggered_id="store-share-pending")
    )
    shared = {
        "version": 1,
        "file": "/tmp/shared-events.h5",
        "entry": 1,
        "renderer": "webgl",
        "display": {
            "run_mode": "reco",
            "truth_points": "points",
            "object": "particles",
            "overlays": [],
            "view": ["split_scene", "sync"],
            "axes": False,
        },
        "attributes": {
            "hover": [],
            "color": "",
            "colorscale": "Inferno",
            "appearance": {"point_size": 1.5, "opacity": 0.75},
        },
        "geometry": {"mode": "auto"},
    }

    result = graph_callback(**graph_arguments(share_pending=shared))

    assert isinstance(result[0], html.Div)
    assert result[1] == 1
    assert result[14]["file_path"] == "/tmp/shared-events.h5"
    assert result[14]["entry"] == 1
    appearance = json.loads(result[0].to_plotly_json()["props"]["data-appearance"])
    assert appearance["point_size"] == 1.5
    assert appearance["opacity"] == 0.75
    assert result[0].to_plotly_json()["props"]["data-show-axes"] == "false"

    assert graph_callback(**graph_arguments(share_pending=None)) == (no_update,) * 17


def test_shared_link_rejects_nested_view_source(graph_callback, monkeypatch):
    """A share URL must resolve directly to data rather than another view."""
    monkeypatch.setattr(
        callback_module, "ctx", SimpleNamespace(triggered_id="store-share-pending")
    )
    monkeypatch.setattr(callback_module, "classify_source", lambda path: ("json", path))
    shared = {
        "version": 1,
        "file": "/tmp/nested-view.json",
        "entry": 0,
    }

    result = graph_callback(**graph_arguments(share_pending=shared))

    assert result[7] == "log-panel has-error"
    assert "cannot reference another shared view" in result[5]


def test_graph_callback_adds_raw_deposition_to_webgl_hover(graph_callback, monkeypatch):
    """Raw WebGL hover should include deposition without selecting it in the UI."""
    monkeypatch.setattr(
        callback_module, "ctx", SimpleNamespace(triggered_id="button-load")
    )
    monkeypatch.setattr(
        callback_module, "object_attributes", lambda *args: ["depositions"]
    )
    monkeypatch.setattr(
        callback_module,
        "get_reader_products",
        lambda reader: {"reco_particles", "points", "depositions"},
    )

    result = graph_callback(**graph_arguments(core_draw_modes=["raw"]))

    scene_call = next(call for call in FakeDrawer.calls if call[0] == "scene")
    assert scene_call[1][1] == ["depositions"]
    assert scene_call[2]["color_attr"] == "depositions"
    assert result[0].to_plotly_json()["props"]["data-color-attribute"] == (
        "depositions"
    )

    result = graph_callback(
        **graph_arguments(core_draw_modes=["raw"], renderer=["plotly"])
    )
    assert isinstance(result[0], dcc.Graph)
    plotly_call = next(call for call in FakeDrawer.calls if call[0] == "plotly")
    assert plotly_call[2]["draw_raw"] is True
    assert plotly_call[1][1] == ["depositions"]
    assert plotly_call[2]["color_attr"] == "depositions"


def test_graph_callback_restores_json_and_reports_draw_errors(
    graph_callback, monkeypatch
):
    """View imports and renderer failures should remain visible in production."""
    monkeypatch.setattr(
        callback_module, "ctx", SimpleNamespace(triggered_id="button-load")
    )
    monkeypatch.setattr(
        callback_module,
        "classify_source",
        lambda path: (
            ("hdf5", path) if path == "/tmp/events.h5" else ("json", "/tmp/view.json")
        ),
    )
    monkeypatch.setattr(
        callback_module,
        "load_view_state",
        lambda path: {
            "version": 1,
            "file": "/tmp/events.h5",
            "entry": 0,
            "objects": {"reco": [], "truth": "all"},
        },
    )
    result = graph_callback(
        **graph_arguments(file_path="/tmp/view.json", source_mode="browse")
    )
    assert isinstance(result[0], html.Div)
    assert result[16]["import_mode"] == "browse"
    assert result[7] == "log-panel is-success"
    assert result[9] == []
    assert result[14]["reco_filter"] == []
    assert result[0].to_plotly_json()["props"]["data-selection"] == ""

    monkeypatch.setattr(callback_module, "classify_source", lambda path: ("hdf5", path))
    FakeDrawer.fail = True
    result = graph_callback(**graph_arguments())
    assert result[7] == "log-panel has-error"
    assert "Could not draw reco particles" in result[5]


def test_graph_callback_opens_uploaded_source_atomically(graph_callback, monkeypatch):
    """Browse completion should not observe a stale Path control value."""
    monkeypatch.setattr(
        callback_module, "ctx", SimpleNamespace(triggered_id="store-source-request")
    )
    assert graph_callback(**graph_arguments(source_request=None)) == (no_update,) * 17

    request = {
        "file_path": "/tmp/uploaded-view.json",
        "source_mode": "browse",
        "revision": 1,
    }
    monkeypatch.setattr(
        callback_module,
        "classify_source",
        lambda path: (
            ("json", path) if path == "/tmp/uploaded-view.json" else ("hdf5", path)
        ),
    )
    monkeypatch.setattr(
        callback_module,
        "load_view_state",
        lambda path: {"version": 1, "file": "/tmp/events.h5", "entry": 1},
    )
    result = graph_callback(
        **graph_arguments(
            file_path="/tmp/previous-events.h5",
            source_mode="path",
            source_request=request,
        )
    )

    assert isinstance(result[0], html.Div)
    assert result[1] == 1
    assert result[14]["file_path"] == "/tmp/events.h5"
    assert result[16]["import_mode"] == "browse"
    assert result[16]["entry"] == 1


def test_graph_callback_rejects_invalid_shared_view_sources(
    graph_callback, monkeypatch
):
    """Shared views should report inaccessible, unreadable and nested sources."""
    monkeypatch.setattr(
        callback_module, "ctx", SimpleNamespace(triggered_id="store-source-request")
    )
    request = {
        "file_path": "/tmp/uploaded-view.json",
        "source_mode": "browse",
    }
    monkeypatch.setattr(
        callback_module,
        "load_view_state",
        lambda path: {"version": 1, "file": "/tmp/target.h5", "entry": 0},
    )
    monkeypatch.setattr(
        callback_module,
        "classify_source",
        lambda path: ("json", path) if "uploaded" in path else ("hdf5", path),
    )
    monkeypatch.setattr(
        callback_module,
        "validate_file_access",
        lambda path: (path != "/tmp/target.h5", "target denied"),
    )
    result = graph_callback(**graph_arguments(source_request=request))
    assert result[7] == "log-panel has-error"
    assert result[5] == "target denied"

    monkeypatch.setattr(
        callback_module, "validate_file_access", lambda path: (True, None)
    )

    def unreadable_target(path):
        if path == "/tmp/target.h5":
            raise OSError("target unavailable")
        return "json", path

    monkeypatch.setattr(callback_module, "classify_source", unreadable_target)
    result = graph_callback(**graph_arguments(source_request=request))
    assert result[7] == "log-panel has-error"
    assert "target unavailable" in result[5]

    monkeypatch.setattr(callback_module, "classify_source", lambda path: ("json", path))
    result = graph_callback(**graph_arguments(source_request=request))
    assert result[7] == "log-panel has-error"
    assert "cannot reference another shared view" in result[5]


def test_graph_callback_renders_shared_view_atomically(graph_callback, monkeypatch):
    """Shared state should render without waiting for control propagation."""
    monkeypatch.setattr(
        callback_module, "ctx", SimpleNamespace(triggered_id="store-source-request")
    )
    monkeypatch.setattr(
        callback_module,
        "get_reader_products",
        lambda reader: {"reco_particles", "flashes", "crthits"},
    )
    monkeypatch.setattr(
        callback_module, "object_attributes", lambda *args: ["energy", "shape"]
    )

    pending = {
        "file": "https://example.org/shared-events.h5",
        "entry": 1,
        "import_mode": "browse",
        "renderer": "plotly",
        "display": {
            "run_mode": "reco",
            "object": "particles",
            "overlays": ["direction", "flash", "flash_match_only", "crt"],
            "view": ["sync"],
        },
        "attributes": {"hover": ["energy", "shape"], "color": "shape"},
        "geometry": {"mode": "manual", "detector": "2x2", "tag": "v1"},
        "objects": {"reco": [], "truth": "all"},
    }
    monkeypatch.setattr(
        callback_module,
        "classify_source",
        lambda path: (
            ("json", path) if path == "/tmp/uploaded-view.json" else ("hdf5", path)
        ),
    )
    monkeypatch.setattr(callback_module, "load_view_state", lambda path: pending)
    result = graph_callback(
        **graph_arguments(
            file_path="/tmp/previous-events.h5",
            entry=0,
            renderer=[],
            source_request={
                "file_path": "/tmp/uploaded-view.json",
                "source_mode": "browse",
            },
        )
    )

    assert isinstance(result[0], dcc.Graph)
    assert result[1] == 1
    assert result[14]["file_path"] == "https://example.org/shared-events.h5"
    assert result[9] == []
    assert result[14]["reco_filter"] == []
    plotly_call = next(call for call in FakeDrawer.calls if call[0] == "plotly")
    assert plotly_call[1][1] == ["energy", "shape"]
    assert plotly_call[2]["color_attr"] == "shape"
    assert plotly_call[2]["draw_directions"] is True
    assert plotly_call[2]["draw_crthits"] is True


@pytest.mark.parametrize(
    "trigger,overrides,message",
    [
        (None, {}, None),
        ("button-load", {"file_path": ""}, "Must specify a file path"),
        ("input-file-path", {"file_path": ""}, "Must specify a file path"),
        ("button-load", {"entry": "bad"}, "must be integers"),
        ("button-load", {"entry": None}, "Must provide an entry number"),
        (
            "button-load",
            {"entry_mode": "run", "run": None, "subrun": None, "event": None},
            "Must provide run, subrun and event",
        ),
        (
            "button-go",
            {
                "entry_mode": "run",
                "run": 0,
                "subrun": 0,
                "event": 11,
                "loaded_event": {
                    "file_path": "/tmp/events.h5",
                    "entry": 0,
                    "use_run": True,
                },
            },
            "(run=0, subrun=0, event=11) was not found.",
        ),
        ("button-load", {"entry": 3}, "Entry 3 not found"),
    ],
)
def test_graph_callback_validates_navigation(
    graph_callback, monkeypatch, trigger, overrides, message
):
    """Invalid navigation requests should stop before drawing an event."""
    monkeypatch.setattr(callback_module, "ctx", SimpleNamespace(triggered_id=trigger))
    result = graph_callback(**graph_arguments(**overrides))
    if message is None:
        assert result == (no_update,) * 17
    else:
        assert result[7] == "log-panel has-error"
        assert message in result[5]


def test_graph_callback_run_and_boundary_navigation(graph_callback, monkeypatch):
    """Run lookup and previous/next boundaries should be deterministic."""
    monkeypatch.setattr(
        callback_module, "ctx", SimpleNamespace(triggered_id="button-load")
    )
    result = graph_callback(
        **graph_arguments(entry_mode="run", run=1, subrun=2, event=3)
    )
    assert result[1] == 0

    monkeypatch.setattr(
        callback_module, "ctx", SimpleNamespace(triggered_id="button-previous")
    )
    result = graph_callback(
        **graph_arguments(loaded_event={"file_path": "/tmp/events.h5", "entry": 0})
    )
    assert result == (no_update,) * 17

    monkeypatch.setattr(
        callback_module, "ctx", SimpleNamespace(triggered_id="button-next")
    )
    loaded = {"file_path": "/tmp/events.h5", "entry": 0, "use_run": False}
    result = graph_callback(**graph_arguments(loaded_event=loaded))
    assert result[1] == 1

    loaded["entry"] = 1
    assert (
        graph_callback(**graph_arguments(loaded_event=loaded, entry=1))
        == (no_update,) * 17
    )

    monkeypatch.setattr(
        callback_module, "ctx", SimpleNamespace(triggered_id="button-previous")
    )
    result = graph_callback(**graph_arguments(loaded_event=loaded, entry=1))
    assert result[1] == 0

    monkeypatch.setattr(
        callback_module, "ctx", SimpleNamespace(triggered_id="button-load")
    )
    result = graph_callback(
        **graph_arguments(entry_mode="run", run=9, subrun=9, event=9)
    )
    assert result[7] == "log-panel has-error"
    assert "not found" in result[5]


def test_graph_callback_fast_refresh_shortcuts(graph_callback, monkeypatch):
    """Client-side-only changes should not rebuild a WebGL scene."""
    monkeypatch.setattr(
        callback_module, "ctx", SimpleNamespace(triggered_id="radio-run-mode")
    )
    assert graph_callback(**graph_arguments()) == (no_update,) * 17
    loaded = {
        "file_path": "/tmp/events.h5",
        "entry": 0,
        "run": 1,
        "subrun": 2,
        "event": 3,
        "use_run": False,
    }
    pending = {"restore_id": "new-view"}
    assert (
        graph_callback(**graph_arguments(loaded_event=loaded, share_pending=pending))
        == (no_update,) * 17
    )
    result = graph_callback(**graph_arguments(loaded_event=loaded))
    assert isinstance(result[0], html.Div)

    monkeypatch.setattr(
        callback_module,
        "ctx",
        SimpleNamespace(triggered_id="store-filter-render-request"),
    )
    assert isinstance(
        graph_callback(**graph_arguments(loaded_event=loaded))[0], html.Div
    )
    monkeypatch.setattr(
        callback_module, "ctx", SimpleNamespace(triggered_id="dropdown-attr-color")
    )
    assert graph_callback(**graph_arguments(loaded_event=loaded)) == (no_update,) * 17

    monkeypatch.setattr(
        callback_module, "ctx", SimpleNamespace(triggered_id="dropdown-geo-tag")
    )
    state = {"geometry": {"detector": "2x2", "tag": "v1"}}
    assert (
        graph_callback(
            **graph_arguments(
                loaded_event=loaded,
                detector="2x2",
                detector_tag="v1",
                entry_state=state,
            )
        )
        == (no_update,) * 17
    )


@pytest.mark.parametrize(
    "failure,message",
    [
        ("access", "Access denied"),
        ("classify", "Could not open source"),
        ("manifest", "manifest denied"),
        ("view", "Could not load shared view"),
        ("missing", "File(s) not found"),
        ("reader", "reader exploded"),
        ("load", "Could not load the selected event"),
    ],
)
def test_graph_callback_reports_source_pipeline_failures(
    graph_callback, monkeypatch, failure, message
):
    """Every source pipeline failure should be routed to the visible log."""
    monkeypatch.setattr(
        callback_module, "ctx", SimpleNamespace(triggered_id="button-load")
    )
    if failure == "access":
        monkeypatch.setattr(
            callback_module,
            "validate_file_access",
            lambda path: (False, "Access denied"),
        )
    elif failure == "classify":
        monkeypatch.setattr(
            callback_module,
            "classify_source",
            lambda path: (_ for _ in ()).throw(ValueError("bad source")),
        )
    elif failure == "manifest":
        monkeypatch.setattr(
            callback_module, "classify_source", lambda path: ("manifest", path)
        )
        monkeypatch.setattr(
            callback_module,
            "validate_manifest_access",
            lambda path: (False, "manifest denied"),
        )
    elif failure == "view":
        monkeypatch.setattr(
            callback_module, "classify_source", lambda path: ("json", path)
        )
        monkeypatch.setattr(
            callback_module,
            "load_view_state",
            lambda path: (_ for _ in ()).throw(ValueError("bad view")),
        )
    elif failure == "missing":
        monkeypatch.setattr(
            callback_module,
            "initialize_reader",
            lambda *args: (_ for _ in ()).throw(FileNotFoundError()),
        )
    elif failure == "reader":
        monkeypatch.setattr(
            callback_module,
            "initialize_reader",
            lambda *args: (_ for _ in ()).throw(RuntimeError("reader exploded")),
        )
    elif failure == "load":
        monkeypatch.setattr(
            callback_module,
            "load_data",
            lambda *args: (_ for _ in ()).throw(RuntimeError("load exploded")),
        )
    result = graph_callback(**graph_arguments())
    assert result[7] == "log-panel has-error"
    assert message in result[5]


def test_graph_callback_geometry_and_filter_details(graph_callback, monkeypatch):
    """Manual geometry changes and partial filters should reach the renderer."""
    loaded = {"file_path": "/tmp/events.h5", "entry": 0, "use_run": False}
    monkeypatch.setattr(
        callback_module, "ctx", SimpleNamespace(triggered_id="dropdown-geo")
    )
    result = graph_callback(
        **graph_arguments(
            detector=None,
            geometry_choice="auto",
            loaded_event=loaded,
            object_filter=[],
        )
    )
    assert result[7] == "log-panel is-success"
    assert "Showing 0 of 1 particles" in result[5]

    monkeypatch.setattr(
        callback_module, "ctx", SimpleNamespace(triggered_id="dropdown-geo-tag")
    )
    result = graph_callback(
        **graph_arguments(
            detector="2x2",
            detector_tag="manual",
            loaded_event=loaded,
            entry_state={"file_path": "/tmp/old.h5"},
        )
    )
    assert result[7] == "log-panel is-success"
