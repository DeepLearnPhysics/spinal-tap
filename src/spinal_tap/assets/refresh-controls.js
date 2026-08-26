(function () {
    "use strict";

    const controls = new Set([
        "attribute-picker",
        "appearance-picker",
        "truth-point-control",
        "log-panel",
        "export-branding-menu",
        "help-menu"
    ]);
    const owners = new Map([
        ["dropdown-attr", "attribute-picker"],
        ["dropdown-attr-color", "attribute-picker"]
    ]);
    const state = new Map();
    let revision = 0;

    function isOpen(root) {
        if (!root) return false;
        if (root.matches("details")) return root.open;
        const dropdown = root.matches(".dash-dropdown")
            ? root
            : root.querySelector(".dash-dropdown");
        return Boolean(dropdown && (
            dropdown.getAttribute("aria-expanded") === "true" ||
            dropdown.getAttribute("data-state") === "open"
        ));
    }

    function placeAttributePicker(picker) {
        if (!picker?.open) return;

        const rail = picker.closest(".control-rail");
        const trigger = picker.querySelector(".attribute-picker-trigger");
        if (!rail || !trigger) return;

        const railBounds = rail.getBoundingClientRect();
        const triggerBounds = trigger.getBoundingClientRect();
        const spaceAbove = Math.max(0, triggerBounds.top - railBounds.top - 12);
        const spaceBelow = Math.max(0, railBounds.bottom - triggerBounds.bottom - 12);
        const opensUpward = spaceAbove > spaceBelow;
        const available = Math.max(opensUpward ? spaceAbove : spaceBelow, 160);

        picker.classList.toggle("opens-upward", opensUpward);
        picker.style.setProperty("--attribute-picker-space", `${available}px`);
        alignAttributeHeading(picker);
    }

    function alignAttributeHeading(picker) {
        const list = picker?.querySelector(".attribute-picker-list");
        if (!list) return;

        const scrollbarWidth = Math.max(0, list.offsetWidth - list.clientWidth);
        picker.style.setProperty(
            "--attribute-scrollbar-width", `${scrollbarWidth}px`
        );
    }

    function commit(id) {
        const current = state.get(id);
        if (!current || !current.dirty) return;

        current.dirty = false;
        window.dash_clientside?.set_props("store-dropdown-commit", {
            data: {control: id, revision: ++revision}
        });
    }

    function pinSelectedAttributeRows() {
        const list = document.getElementById("attribute-picker-list");
        if (!list) return;

        const rows = [...list.querySelectorAll(".attribute-picker-row")];
        rows.sort((left, right) => (
            Number(Boolean(right.querySelector(".attribute-picker-hover-input")?.checked))
            - Number(Boolean(left.querySelector(".attribute-picker-hover-input")?.checked))
        ));
        rows.forEach(row => list.appendChild(row));
    }

    function scan() {
        controls.forEach(id => {
            const root = document.getElementById(id);
            const current = state.get(id) || {open: false, dirty: false};
            const open = isOpen(root);
            if (id === "attribute-picker" && open) {
                placeAttributePicker(root);
                if (!current.open) {
                    setTimeout(() => {
                        document.getElementById("input-attribute-search")
                            ?.focus({preventScroll: true});
                    }, 0);
                }
            }
            if (id === "appearance-picker" && open && !current.open) {
                window.spinalTapWebgl?.refreshAppearanceHistogram();
            }
            if (current.open && !open) {
                if (id === "attribute-picker") pinSelectedAttributeRows();
                commit(id);
                if (id === "attribute-picker") {
                    window.dash_clientside?.set_props(
                        "input-attribute-search", {value: ""}
                    );
                }
            }
            current.open = open;
            state.set(id, current);
        });
    }

    function markDirty(id) {
        id = owners.get(id) || id;
        if (!controls.has(id)) return;
        const root = document.getElementById(id);
        const current = state.get(id) || {open: false, dirty: false};
        current.dirty = true;
        current.open = isOpen(root);
        state.set(id, current);

        // Clearing a closed dropdown should apply immediately. Option changes
        // remain pending while the menu is open and commit on its close edge.
        setTimeout(() => {
            scan();
            if (!isOpen(document.getElementById(id))) commit(id);
        }, 0);
    }

    function renderAttributeRows(payload, selected, color) {
        const list = document.getElementById("attribute-picker-list");
        if (!list) return;

        const clear = document.getElementById("button-clear-attributes");
        if (clear) {
            clear.style.display = (selected || []).length || color ? "block" : "none";
        }

        const hoverOptions = [...(payload?.hover || [])];
        const colorOptions = new Map(
            (payload?.color || []).map(option => [String(option.value), option])
        );
        const selectedAttrs = new Set(selected || []);
        const fragment = document.createDocumentFragment();
        const currentOrder = new Map(
            [...list.querySelectorAll(".attribute-picker-row")].map(
                (row, index) => [row.dataset.value, index]
            )
        );
        const pickerOpen = isOpen(document.getElementById("attribute-picker"));

        // Match the standard multi-select menus: active choices are pinned to
        // the top once the menu closes. While it remains open, retain the
        // current row order so checking an item does not move it away from the
        // pointer in the middle of a selection session.
        hoverOptions.sort((left, right) => (
            pickerOpen && currentOrder.size
                ? (currentOrder.get(String(left.value)) ?? hoverOptions.length)
                    - (currentOrder.get(String(right.value)) ?? hoverOptions.length)
                : Number(selectedAttrs.has(String(right.value)))
                    - Number(selectedAttrs.has(String(left.value)))
        ));

        hoverOptions.forEach(option => {
            const value = String(option.value);
            const isObjectId = value === "id";
            const row = document.createElement("div");
            row.className = "attribute-picker-row";
            row.dataset.value = value;

            const name = document.createElement("span");
            name.className = "attribute-picker-name";
            name.textContent = option.label;
            name.title = option.title || option.label;

            const hoverChoice = document.createElement("label");
            hoverChoice.className = "attribute-picker-choice";
            hoverChoice.title = `Show ${option.label} on hover`;
            const hoverInput = document.createElement("input");
            hoverInput.type = "checkbox";
            hoverInput.className = "attribute-picker-hover-input";
            hoverInput.value = value;
            hoverInput.checked = selectedAttrs.has(value);
            hoverInput.disabled = isObjectId;
            if (isObjectId) {
                hoverChoice.classList.add("attribute-picker-choice-unavailable");
                hoverChoice.title = "Object ID is always shown in the tooltip";
            }
            hoverInput.addEventListener("change", () => {
                // Search deliberately hides non-matching rows, including
                // selected ones. Start from the complete Dash selection and
                // merge the state of every currently rendered checkbox so a
                // visible edit cannot silently clear hidden hover/color data.
                const next = new Set(selectedAttrs);
                list.querySelectorAll(".attribute-picker-hover-input").forEach(
                    input => {
                        if (input.checked) next.add(input.value);
                        else next.delete(input.value);
                    }
                );
                window.dash_clientside?.set_props("dropdown-attr", {
                    value: [...next]
                });
            });
            hoverChoice.appendChild(hoverInput);

            const colorValue = value === "id" ? "" : value;
            const colorOption = colorOptions.get(colorValue);
            const colorChoice = document.createElement("label");
            colorChoice.className = "attribute-picker-choice";
            const colorInput = document.createElement("input");
            colorInput.type = "radio";
            colorInput.name = "attribute-color";
            colorInput.value = colorValue;
            colorInput.checked = colorValue === String(color || "");
            colorInput.disabled = !colorOption || Boolean(colorOption.disabled);
            colorChoice.title = colorOption?.title ||
                "This attribute cannot define colors";
            colorInput.addEventListener("change", () => {
                if (!colorInput.checked || colorInput.disabled) return;
                window.dash_clientside?.set_props("dropdown-attr-color", {
                    value: colorInput.value
                });
            });
            colorChoice.appendChild(colorInput);

            row.append(name, hoverChoice, colorChoice);
            row.addEventListener("click", event => {
                if (isObjectId
                        || event.target.closest(".attribute-picker-choice")) return;
                hoverInput.click();
            });
            fragment.appendChild(row);
        });

        list.replaceChildren(fragment);
        requestAnimationFrame(() => alignAttributeHeading(
            document.getElementById("attribute-picker")
        ));
    }

    window.spinalTapRefreshControls = {markDirty, renderAttributeRows};

    document.addEventListener("pointerdown", event => {
        controls.forEach(id => {
            const picker = document.getElementById(id);
            if (picker?.open && !picker.contains(event.target)) picker.open = false;
        });
        setTimeout(scan, 0);
    });

    document.addEventListener("click", event => {
        const clear = event.target.closest("#button-clear-attributes");
        if (!clear) return;
        event.preventDefault();
        event.stopPropagation();
        window.dash_clientside?.set_props("dropdown-attr", {value: []});
        window.dash_clientside?.set_props("dropdown-attr-color", {value: ""});
    });

    window.addEventListener("resize", () => {
        placeAttributePicker(document.getElementById("attribute-picker"));
    });

    new MutationObserver(scan).observe(document.documentElement, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["aria-expanded", "data-state", "open"]
    });
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", scan);
    } else {
        scan();
    }
})();
