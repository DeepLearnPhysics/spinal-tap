(function () {
    "use strict";

    const bindings = new Map([
        ["arrowleft", {selector: "#button-previous", label: "Previous entry"}],
        ["arrowright", {selector: "#button-next", label: "Next entry"}],
        ["r", {selector: "#button-reset-view", label: "Reset view"}],
        ["a", {
            selector: '#checklist-show-axes input[value="axes"]',
            label: "Toggle axes"
        }],
        ["s", {selector: "#button-save-png", label: "Save PNG"}],
        ["e", {selector: "#button-export-view", label: "Export view JSON"}],
        ["?", {selector: "#help-menu > summary", label: "Open / close help"}]
    ]);

    function hasTextFocus(target) {
        if (!(target instanceof Element)) return false;
        return Boolean(target.closest(
            "input, textarea, select, button, summary, [contenteditable='true'], " +
            "[role='combobox'], [role='listbox'], .dash-dropdown"
        ));
    }

    function activate(key) {
        const binding = bindings.get(String(key).toLowerCase());
        if (!binding) return false;

        const control = document.querySelector(binding.selector);
        if (!control || control.disabled) return false;

        control.click();
        return true;
    }

    document.addEventListener("keydown", event => {
        const helpSummaryFocused = event.key === "?" &&
            event.target instanceof Element &&
            event.target.closest("#help-menu > summary");
        if (
            event.defaultPrevented || event.repeat || event.metaKey ||
            event.ctrlKey || event.altKey ||
            (hasTextFocus(event.target) && !helpSummaryFocused)
        ) return;

        if (activate(event.key)) event.preventDefault();
    });

    window.spinalTapShortcuts = {
        activate,
        bindings: Object.fromEntries(
            [...bindings].map(([key, value]) => [key, value.label])
        )
    };
})();
