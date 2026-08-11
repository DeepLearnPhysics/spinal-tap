"""Tests for Spinal Tap layout controls."""

from spinal_tap.layout import display_controls


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


def test_display_controls_use_object_filter():
    """The display should expose filtering without the split-trace option."""
    controls = display_controls()
    object_filter = component_by_id(controls, "dropdown-object-filter")
    draw_mode = component_by_id(controls, "checklist-draw-mode-2")

    assert object_filter is not None
    assert object_filter.multi is True
    assert object_filter.value == []
    assert "split_traces" not in {option["value"] for option in draw_mode.options}
