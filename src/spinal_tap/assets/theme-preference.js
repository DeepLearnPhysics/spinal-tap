(function () {
    "use strict";

    const STORAGE_KEY = "spinal-tap-theme";
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    let expectedBootstrap = null;

    function storedTheme() {
        try {
            const value = window.localStorage.getItem(STORAGE_KEY);
            return value === "light" || value === "dark" ? value : null;
        } catch (_error) {
            return null;
        }
    }

    function resolvedTheme() {
        return storedTheme() || (media.matches ? "dark" : "light");
    }

    function apply(theme) {
        document.documentElement.dataset.spinalTapTheme = theme;
    }

    function initializeToggle() {
        const theme = resolvedTheme();
        expectedBootstrap = theme;
        apply(theme);
        return theme === "dark" ? ["dark"] : [];
    }

    function select(theme) {
        apply(theme);
        if (theme === expectedBootstrap) {
            expectedBootstrap = null;
            return;
        }
        expectedBootstrap = null;
        try {
            window.localStorage.setItem(STORAGE_KEY, theme);
        } catch (_error) {
            // A private browser may reject persistent storage. The selected
            // theme still applies for the lifetime of the current document.
        }
    }

    function followSystem() {
        if (storedTheme()) return;
        const theme = media.matches ? "dark" : "light";
        expectedBootstrap = theme;
        apply(theme);
        if (window.dash_clientside?.set_props) {
            window.dash_clientside.set_props("theme-toggle", {
                value: theme === "dark" ? ["dark"] : []
            });
        }
    }

    window.spinalTapTheme = {
        initializeToggle,
        resolvedTheme,
        select
    };
    apply(resolvedTheme());
    media.addEventListener?.("change", followSystem);
})();
