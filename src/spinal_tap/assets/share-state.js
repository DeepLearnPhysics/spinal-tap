(function () {
    "use strict";

    const VERSION = 1;
    let cameraRestoreTimer = null;
    const imageCache = new Map();

    function assetUrl(name) {
        const script = Array.from(document.scripts).find(item =>
            /\/assets\/share-state\.js(?:\?|$)/.test(item.src)
        );
        return new URL(name, script?.src || window.location.href).toString();
    }

    function loadImage(url) {
        if (!imageCache.has(url)) {
            imageCache.set(url, new Promise((resolve, reject) => {
                const image = new Image();
                image.onload = () => resolve(image);
                image.onerror = () => reject(
                    new Error(`Could not load watermark asset: ${url}`)
                );
                image.src = url;
            }));
        }
        return imageCache.get(url);
    }

    function detectorLogo(detector) {
        const name = String(detector || "").toLowerCase().replaceAll("_", "-");
        if (name.includes("icarus")) return "icarus-logo.png";
        if (name.includes("sbnd")) return "sbnd-logo.png";
        if (name.includes("dune") || name.includes("2x2") ||
                name.includes("nd-lar")) {
            return "dune-logo.png";
        }
        return null;
    }

    function darkTheme() {
        return Boolean(document.querySelector("#theme-toggle input")?.checked);
    }

    function sourceStem(source) {
        let value = String(source || "").trim();
        let fallback = "spinal-tap";
        try {
            const url = new URL(value);
            value = url.pathname;
            fallback = url.hostname || fallback;
        } catch (_) {
            value = value.split(/[?#]/, 1)[0];
        }

        const parts = value.replaceAll("\\", "/").split("/").filter(Boolean);
        value = parts.at(-1) || fallback;
        try {
            value = decodeURIComponent(value);
        } catch (_) {
            // Keep malformed URL escapes literal and sanitize them below.
        }
        value = value.replace(/\.(?:h5|hdf5|json|txt|list)$/i, "");
        value = value
            .replace(/[^a-zA-Z0-9_-]+/g, "_")
            .replace(/^_+|_+$/g, "")
            .replace(/_+/g, "_");
        return (value || fallback).slice(0, 48);
    }

    function sourceName(source) {
        let value = String(source || "").trim();
        let fallback = "spinal-tap";
        try {
            const url = new URL(value);
            value = url.pathname;
            fallback = url.hostname || fallback;
        } catch (_) {
            value = value.split(/[?#]/, 1)[0];
        }
        const parts = value.replaceAll("\\", "/").split("/").filter(Boolean);
        try {
            value = decodeURIComponent(parts.at(-1) || fallback);
        } catch (_) {
            value = parts.at(-1) || fallback;
        }
        return value.length > 48 ? `${value.slice(0, 45)}...` : value;
    }

    function exportBaseName(state) {
        const entry = Number.isInteger(state?.entry) ? state.entry : 0;
        const mode = String(state?.display?.run_mode || "reco");
        const object = String(state?.display?.object || "particles");
        return `${sourceStem(state?.file)}_entry-${entry}_${mode}-${object}`;
    }

    async function brandingAssets(state) {
        const branding = state?.branding || {};
        const enabled = new Set(
            branding.labels || branding.watermarks || ["spine", "entry"]
        );
        const requests = [];
        if (enabled.has("detector")) {
            const detector = detectorLogo(
                branding.detector || state?.geometry?.detector
            );
            if (detector) requests.push(["detector", detector]);
        }
        if (enabled.has("spine")) {
            requests.push([
                "spine",
                darkTheme() ? "spine-logo-light.png" : "spine-logo-dark.png"
            ]);
        }
        return Promise.all(requests.map(async item => {
            const image = await loadImage(assetUrl(item[1]));
            return {kind: item[0], image};
        }));
    }

    function exportLabelText(state) {
        const branding = state?.branding || {};
        const enabled = new Set(
            branding.labels || branding.watermarks || ["spine", "entry"]
        );
        const labels = [];
        if (enabled.has("source")) labels.push(sourceName(state?.file));
        if (enabled.has("entry") && Number.isInteger(state?.entry)) {
            labels.push(`Entry ${state.entry}`);
        }
        if (enabled.has("run") && [state?.run, state?.subrun, state?.event]
                .every(value => Number.isInteger(value))) {
            labels.push(
                `Run ${state.run} / Subrun ${state.subrun} / Event ${state.event}`
            );
        }
        return labels.join(" · ");
    }

    function hasExportViewTitles(state) {
        return state?.display?.run_mode === "both" &&
            (state?.display?.view || []).includes("split_scene");
    }

    function watermarkDimensions(asset, width, height) {
        const maximumWidth = width * (asset.kind === "spine" ? 0.20 : 0.15);
        // Wide marks such as DUNE are naturally constrained by width. Keep
        // square and portrait detector marks from becoming optically heavier.
        const maximumHeight = height * (asset.kind === "spine" ? 0.09 : 0.10);
        const scale = Math.min(
            maximumWidth / asset.image.width,
            maximumHeight / asset.image.height
        );
        return {
            width: asset.image.width * scale,
            height: asset.image.height * scale
        };
    }

    function drawBranding(context, width, height, assets, state) {
        const margin = Math.max(8, Math.min(width, height) * 0.018);
        assets.forEach(asset => {
            const size = watermarkDimensions(asset, width, height);
            const x = asset.kind === "spine"
                ? width - margin - size.width
                : margin;
            const y = height - margin - size.height;
            context.drawImage(asset.image, x, y, size.width, size.height);
        });
        const label = exportLabelText(state);
        if (label) {
            let fontSize = Math.max(11, Math.min(width, height) * 0.022);
            context.save();
            context.fillStyle = darkTheme() ? "#f4f6f8" : "#172033";
            context.font = `600 ${fontSize}px system-ui, sans-serif`;
            while (fontSize > 10 &&
                    context.measureText(label).width > width - 2 * margin) {
                fontSize -= 1;
                context.font = `600 ${fontSize}px system-ui, sans-serif`;
            }
            context.textAlign = "left";
            context.textBaseline = "top";
            context.fillText(label, margin, margin);
            context.restore();
        }
    }

    function imageDataUrl(image) {
        if (typeof image.toDataURL === "function") {
            return image.toDataURL("image/png");
        }

        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, image.naturalWidth || image.width);
        canvas.height = Math.max(1, image.naturalHeight || image.height);
        const context = canvas.getContext("2d");
        if (!context) throw new Error("Could not prepare a branding asset.");
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        return canvas.toDataURL("image/png");
    }

    function plotlyBrandingImages(graph, assets) {
        const width = Math.max(1, graph.clientWidth || 1000);
        const height = Math.max(1, graph.clientHeight || 700);
        return assets.map(asset => {
            const size = watermarkDimensions(asset, width, height);
            return {
                source: imageDataUrl(asset.image),
                xref: "paper",
                yref: "paper",
                x: asset.kind === "spine" ? 0.99 : 0.01,
                y: 0.01,
                sizex: size.width / width,
                sizey: size.height / height,
                xanchor: asset.kind === "spine" ? "right" : "left",
                yanchor: "bottom",
                sizing: "contain",
                opacity: 1,
                layer: "above"
            };
        });
    }

    function plotlyLabelAnnotations(state) {
        const label = exportLabelText(state);
        if (!label) return [];
        return [{
            text: label.replaceAll("&", "&amp;").replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;"),
            xref: "paper",
            yref: "paper",
            x: 0.01,
            y: 0.99,
            xanchor: "left",
            yanchor: "top",
            showarrow: false,
            font: {
                color: darkTheme() ? "#f4f6f8" : "#172033",
                size: 13
            }
        }];
    }

    function plotlyExportAnnotations(graph, state) {
        const hasLabel = Boolean(exportLabelText(state));
        const annotations = (graph.layout?.annotations || []).map(annotation => {
            const subplotTitle = hasLabel && hasExportViewTitles(state) &&
                annotation.xref === "paper" && annotation.yref === "paper" &&
                Number(annotation.y) >= 0.95;
            return subplotTitle
                ? {...annotation, y: 0.93, yanchor: "top"}
                : annotation;
        });
        return [...annotations, ...plotlyLabelAnnotations(state)];
    }

    function base64UrlEncode(value) {
        const bytes = new TextEncoder().encode(JSON.stringify(value));
        let binary = "";
        const chunkSize = 0x8000;
        for (let offset = 0; offset < bytes.length; offset += chunkSize) {
            binary += String.fromCharCode(
                ...bytes.subarray(offset, offset + chunkSize)
            );
        }
        return btoa(binary)
            .replaceAll("+", "-")
            .replaceAll("/", "_")
            .replace(/=+$/, "");
    }

    function base64UrlDecode(value) {
        const base64 = value.replaceAll("-", "+").replaceAll("_", "/");
        const padded = base64 + "=".repeat((4 - base64.length % 4) % 4);
        const binary = atob(padded);
        const bytes = Uint8Array.from(binary, character => character.charCodeAt(0));
        return JSON.parse(new TextDecoder().decode(bytes));
    }

    function validateState(state) {
        if (!state || typeof state !== "object" || state.version !== VERSION) {
            throw new Error(`Unsupported view-state version; expected ${VERSION}`);
        }
        if (typeof state.file !== "string" || !state.file.length) {
            throw new Error("The view state does not contain a file path");
        }
        if (!Number.isInteger(Number(state.entry)) || Number(state.entry) < 0) {
            throw new Error("The view state contains an invalid entry number");
        }
        const display = state.display || {};
        const attributes = state.attributes || {};
        const objects = state.objects || {};
        [display.overlays, display.view, attributes.hover].forEach(value => {
            if (value != null && !Array.isArray(value)) {
                throw new Error("A view-state option list is malformed");
            }
        });
        [objects.reco, objects.truth].forEach(value => {
            if (value != null && value !== "all" && !Array.isArray(value)) {
                throw new Error("A view-state object selection is malformed");
            }
        });
        return state;
    }

    function decodeHash(hash) {
        const params = new URLSearchParams((hash || "").replace(/^#/, ""));
        const encoded = params.get("view");
        if (!encoded) return null;

        return validateState(base64UrlDecode(encoded));
    }

    function stateWithCamera(state) {
        return Object.assign({}, validateState(state), {
            camera: captureCamera(state.renderer)
        });
    }

    function rememberPlotlyCamera(graph) {
        if (!graph?.layout || graph._spinalTapInitialCameras) return;
        const cameras = {};
        ["scene", "scene2", "scene3"].forEach(name => {
            if (graph.layout[name]?.camera) cameras[name] = graph.layout[name].camera;
        });
        graph._spinalTapInitialCameras = JSON.parse(JSON.stringify(cameras));
    }

    function captureCamera(renderer) {
        if (renderer === "webgl") {
            const viewer = document.querySelector(".webgl-viewer")
                ?._spinalTapViewer;
            if (!viewer) return null;
            return Object.assign({renderer: "webgl"}, viewer.cameraState());
        }

        const graph = document.querySelector("#graph-evd .js-plotly-plot");
        if (!graph?.layout) return null;
        const scenes = {};
        ["scene", "scene2", "scene3"].forEach(name => {
            if (graph.layout[name]?.camera) {
                scenes[name] = graph.layout[name].camera;
            }
        });
        return Object.keys(scenes).length
            ? {renderer: "plotly", scenes}
            : null;
    }

    function restoreCamera(camera) {
        if (!camera) return;

        cancelCameraRestore();
        let lastTarget = null;
        let attempts = 0;
        let stableAttempts = 0;
        cameraRestoreTimer = window.setInterval(() => {
            attempts += 1;
            let target = null;

            if (camera.renderer === "webgl") {
                const root = document.querySelector(".webgl-viewer");
                const viewer = root?._spinalTapViewer;
                if (viewer) {
                    target = viewer;
                    if (target !== lastTarget) viewer.restoreCamera(camera);
                }
            } else if (camera.renderer === "plotly") {
                const graph = document.querySelector("#graph-evd .js-plotly-plot");
                if (graph?.layout && window.Plotly) {
                    target = graph;
                    if (target !== lastTarget) {
                        rememberPlotlyCamera(graph);
                        const update = {};
                        Object.entries(camera.scenes || {}).forEach(entry => {
                            update[`${entry[0]}.camera`] = entry[1];
                        });
                        if (Object.keys(update).length) Plotly.relayout(graph, update);
                    }
                }
            }

            if (target) {
                stableAttempts = target === lastTarget ? stableAttempts + 1 : 0;
                lastTarget = target;
            } else {
                stableAttempts = 0;
            }

            // Allow the staged restore to replace its viewer, then disarm the
            // imported camera. Later entry navigation must own its own camera.
            if (stableAttempts >= 10 || attempts >= 600) {
                cancelCameraRestore();
            }
        }, 100);
    }

    function cancelCameraRestore() {
        if (cameraRestoreTimer !== null) {
            window.clearInterval(cameraRestoreTimer);
            cameraRestoreTimer = null;
        }
    }

    function resetView() {
        const viewer = document.querySelector(".webgl-viewer")
            ?._spinalTapViewer;
        if (viewer) {
            viewer.resetCamera();
            return;
        }

        const graph = document.querySelector("#graph-evd .js-plotly-plot");
        if (!graph?.layout || !window.Plotly) return;
        rememberPlotlyCamera(graph);
        const update = {};
        Object.entries(graph._spinalTapInitialCameras || {}).forEach(entry => {
            update[`${entry[0]}.camera`] = entry[1];
        });
        if (Object.keys(update).length) Plotly.relayout(graph, update);
    }

    async function saveImage(state) {
        const assets = await brandingAssets(state);
        const viewer = document.querySelector(".webgl-viewer")
            ?._spinalTapViewer;
        if (viewer) {
            await viewer.saveImage(
                `${exportBaseName(state)}.png`,
                (context, width, height) => {
                    drawBranding(context, width, height, assets, state);
                },
                Boolean(exportLabelText(state))
            );
            return;
        }

        const graph = document.querySelector("#graph-evd .js-plotly-plot");
        if (!graph || !window.Plotly) return;
        const original = graph.layout.images || [];
        const originalAnnotations = graph.layout.annotations || [];
        const watermarks = plotlyBrandingImages(graph, assets);
        const annotations = plotlyExportAnnotations(graph, state);
        await Plotly.relayout(graph, {
            images: [...original, ...watermarks],
            annotations: annotations
        });
        try {
            await Plotly.downloadImage(graph, {
                format: "png",
                filename: exportBaseName(state),
                scale: 2
            });
        } finally {
            await Plotly.relayout(graph, {
                images: original,
                annotations: originalAnnotations
            });
        }
    }

    async function saveGif(progress, state) {
        const viewer = document.querySelector(".webgl-viewer")
            ?._spinalTapViewer;
        if (!viewer) throw new Error("GIF export is available in WebGL mode.");
        const assets = await brandingAssets(state);
        await viewer.saveGif(
            progress,
            `${exportBaseName(state)}.gif`,
            (context, width, height) => {
                drawBranding(context, width, height, assets, state);
            },
            Boolean(exportLabelText(state))
        );
    }

    function serializablePlotlyFigure(graph) {
        const replacer = function(key, value) {
            if (ArrayBuffer.isView(value)) return Array.from(value);
            return value;
        };
        const figure = JSON.parse(JSON.stringify({
            data: graph.data || [],
            layout: graph.layout || {}
        }, replacer));

        // Plotly keeps the live camera in the fully resolved layout. Copy it
        // explicitly so the exported file opens at exactly the current view.
        Object.keys(graph._fullLayout || {}).forEach(name => {
            if (!/^scene\d*$/.test(name)) return;
            const camera = graph._fullLayout[name]?.camera;
            if (!camera) return;
            figure.layout[name] = figure.layout[name] || {};
            figure.layout[name].camera = JSON.parse(JSON.stringify(camera));
        });
        return figure;
    }

    async function plotlySource() {
        const script = Array.from(document.scripts).find(item =>
            /(?:package_data\/)?plotly(?:\.min)?\.js(?:\?|$)/i.test(item.src)
        );
        if (!script?.src) {
            throw new Error("Could not locate the loaded Plotly library.");
        }
        const response = await fetch(script.src);
        if (!response.ok) {
            throw new Error(`Could not embed Plotly (${response.status}).`);
        }
        return (await response.text()).replace(/<\/script/gi, "<\\/script");
    }

    async function saveHtml(state) {
        const graph = document.querySelector("#graph-evd .js-plotly-plot");
        if (!graph || !window.Plotly) {
            throw new Error("HTML export is available in Plotly mode.");
        }

        const figure = serializablePlotlyFigure(graph);
        const assets = await brandingAssets(state);
        figure.layout.images = [
            ...(figure.layout.images || []),
            ...plotlyBrandingImages(graph, assets)
        ];
        figure.layout.annotations = plotlyExportAnnotations(figure, state);
        const figureJson = JSON.stringify(figure).replace(/</g, "\\u003c");
        const source = await plotlySource();
        const documentText = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Spinal Tap event display</title>
  <style>
    html, body, #spinal-tap-plot { width: 100%; height: 100%; margin: 0; }
  </style>
</head>
<body>
  <div id="spinal-tap-plot"></div>
  <script>${source}</script>
  <script>
    const figure = ${figureJson};
    Plotly.newPlot("spinal-tap-plot", figure.data, figure.layout, {
      responsive: true,
      displaylogo: false,
      scrollZoom: true
    });
  </script>
</body>
</html>`;
        const blob = new Blob([documentText], {type: "text/html"});
        const link = document.createElement("a");
        const objectUrl = URL.createObjectURL(blob);
        link.href = objectUrl;
        link.download = `${exportBaseName(state)}.html`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
    }

    function downloadJson(state) {
        const payload = stateWithCamera(state);
        const blob = new Blob([JSON.stringify(payload, null, 2) + "\n"], {
            type: "application/json"
        });
        const link = document.createElement("a");
        const objectUrl = URL.createObjectURL(blob);
        link.href = objectUrl;
        link.download = `${exportBaseName(payload)}.json`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
    }

    function reportError(message, action = "Viewer action failed") {
        window.dash_clientside?.set_props("text-info", {
            value: `${action}:\n${message}`
        });
        window.dash_clientside?.set_props("log-panel", {
            className: "log-panel has-error"
        });
    }

    async function copyLink(state) {
        const payload = stateWithCamera(state);
        const url = new URL(window.location.href);
        url.hash = `view=${base64UrlEncode(payload)}`;
        const text = url.toString();

        if (navigator.clipboard?.writeText) {
            try {
                await navigator.clipboard.writeText(text);
                return text;
            } catch (error) {
                // Local or non-TLS deployments may expose the Clipboard API
                // but reject writes. Fall through to the user-gesture-backed
                // copy path used by older browsers.
                console.warn("Clipboard API unavailable; using fallback", error);
            }
        }

        const input = document.createElement("textarea");
        input.value = text;
        input.style.position = "fixed";
        input.style.opacity = "0";
        document.body.appendChild(input);
        input.select();
        const copied = document.execCommand("copy");
        input.remove();
        if (!copied) throw new Error("Could not copy the shared-view link");
        return text;
    }

    window.spinalTapShare = {
        version: VERSION,
        copyLink,
        cancelCameraRestore,
        decodeHash,
        downloadJson,
        exportBaseName,
        rememberPlotlyCamera,
        reportError,
        resetView,
        restoreCamera,
        saveGif,
        saveHtml,
        saveImage,
        validateState
    };

})();
