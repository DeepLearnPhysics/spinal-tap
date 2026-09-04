(function () {
    "use strict";

    const CAMERA_FOV = Math.PI / 4;

    const VERTEX_SHADER = `#version 300 es
        in vec3 aPosition;
        in vec4 aColor;
        uniform mat4 uMvp;
        uniform float uPointSize;
        out vec4 vColor;
        void main() {
            gl_Position = uMvp * vec4(aPosition, 1.0);
            gl_PointSize = uPointSize;
            vColor = aColor;
        }
    `;
    const FRAGMENT_SHADER = `#version 300 es
        precision mediump float;
        precision mediump int;
        in vec4 vColor;
        uniform int uSymbol;
        out vec4 outColor;
        void main() {
            vec2 point = gl_PointCoord - vec2(0.5);
            float radius = length(point);
            float distanceToEdge = 0.5 - radius;
            if (uSymbol == 2) {
                distanceToEdge = min(0.5 - radius, radius - 0.30);
            } else if (uSymbol == 3) {
                distanceToEdge = 0.5 - abs(point.x) - abs(point.y);
            }
            // Translucent marker edges still write to the depth buffer. When
            // nearby voxels overlap on screen, those edge fragments can then
            // hide the opaque centers behind them and make colors depend on
            // the camera distance. Use a binary shape mask instead; the
            // high-DPI canvas supplies the final display-space smoothing.
            if (uSymbol != 0 && distanceToEdge < 0.0) discard;
            outColor = vColor;
        }
    `;
    const SIMPLE_FRAGMENT_SHADER = `#version 300 es
        precision mediump float;
        in vec4 vColor;
        out vec4 outColor;
        void main() { outColor = vColor; }
    `;

    function appearanceControlValue(id, fallback) {
        const control = document.getElementById(id);
        const checked = control?.querySelector("input:checked");
        if (checked) return checked.value;
        const input = control?.querySelector("input") || control;
        return input?.value ?? fallback;
    }

    function formatHistogramValue(value) {
        if (!Number.isFinite(value)) return "\u2014";
        const magnitude = Math.abs(value);
        if (magnitude && (magnitude >= 1e4 || magnitude < 1e-2)) {
            return value.toExponential(2);
        }
        return Number(value.toPrecision(4)).toString();
    }

    function histogramRawValue(value, transform) {
        return transform === "log" ? Math.pow(10, value) : value;
    }

    function drawAppearanceHistogram(canvas) {
        const state = canvas._appearanceHistogram;
        if (!state) return;
        const ratio = window.devicePixelRatio || 1;
        const width = Math.max(1, Math.floor(canvas.clientWidth * ratio));
        const height = Math.max(1, Math.floor(canvas.clientHeight * ratio));
        canvas.width = width;
        canvas.height = height;
        const context = canvas.getContext("2d");
        context.clearRect(0, 0, width, height);
        if (!state.bins.length) return;

        const styles = getComputedStyle(document.documentElement);
        const orange = styles.getPropertyValue("--spine-orange").trim()
            || "#f47c13";
        const line = styles.getPropertyValue("--line-strong").trim()
            || "#c7ccd3";
        const plotTop = 4 * ratio;
        const plotBottom = height - 5 * ratio;
        const plotHeight = plotBottom - plotTop;
        const peak = state.bins.reduce(
            (value, count) => Math.max(value, count), 1
        );

        context.strokeStyle = line;
        context.lineWidth = ratio;
        context.beginPath();
        context.moveTo(0, plotBottom);
        context.lineTo(width, plotBottom);
        context.stroke();
        state.bins.forEach((count, index) => {
            const barWidth = width / state.bins.length;
            const barHeight = plotHeight * count / peak;
            context.fillStyle = orange;
            context.fillRect(
                index * barWidth,
                plotBottom - barHeight,
                Math.max(ratio, barWidth - ratio),
                barHeight
            );
        });

        let selection = state.preview || state.selection;
        if (selection) {
            const span = (state.max - state.min) || 1;
            const left = width * (selection[0] - state.min) / span;
            const right = width * (selection[1] - state.min) / span;
            context.fillStyle = "rgba(244, 124, 19, 0.15)";
            context.fillRect(left, plotTop, right - left, plotHeight);
            context.strokeStyle = orange;
            context.lineWidth = 2 * ratio;
            [left, right].forEach(position => {
                context.beginPath();
                context.moveTo(position, plotTop);
                context.lineTo(position, plotBottom);
                context.stroke();
            });
        }
    }

    function bindAppearanceHistogram(canvas) {
        if (canvas._appearanceHistogramBound) return;
        canvas._appearanceHistogramBound = true;
        const position = event => {
            const state = canvas._appearanceHistogram;
            const bounds = canvas.getBoundingClientRect();
            const ratio = Math.max(0, Math.min(
                1, (event.clientX - bounds.left) / (bounds.width || 1)
            ));
            return state.min + ratio * (state.max - state.min);
        };
        canvas.addEventListener("pointerdown", event => {
            if (!canvas._appearanceHistogram?.bins.length) return;
            canvas.setPointerCapture(event.pointerId);
            canvas._appearanceHistogram.start = position(event);
            canvas._appearanceHistogram.startX = event.clientX;
            canvas._appearanceHistogram.preview = [
                canvas._appearanceHistogram.start,
                canvas._appearanceHistogram.start
            ];
            drawAppearanceHistogram(canvas);
        });
        canvas.addEventListener("pointermove", event => {
            const state = canvas._appearanceHistogram;
            if (state?.start == null) return;
            const current = position(event);
            state.preview = [
                Math.min(state.start, current),
                Math.max(state.start, current)
            ];
            drawAppearanceHistogram(canvas);
        });
        const finish = event => {
            const state = canvas._appearanceHistogram;
            if (state?.start == null) return;
            const current = position(event);
            const clicked = Math.abs(event.clientX - state.startX) < 3;
            const selected = clicked
                ? [current, state.max]
                : [Math.min(state.start, current), Math.max(state.start, current)];
            state.start = null;
            state.preview = null;
            state.selection = selected;
            drawAppearanceHistogram(canvas);
            const minimum = histogramRawValue(selected[0], state.transform);
            const maximum = histogramRawValue(selected[1], state.transform);
            window.dash_clientside?.set_props("radio-visible-range", {
                value: "range"
            });
            window.dash_clientside?.set_props("input-visible-min", {
                value: minimum
            });
            window.dash_clientside?.set_props("input-visible-max", {
                value: maximum
            });
        };
        canvas.addEventListener("pointerup", finish);
        canvas.addEventListener("pointercancel", finish);
    }

    function renderAppearanceHistogramData(canvas, histogram, appearance) {
        if (!canvas) return;
        const bins = Uint32Array.from(histogram?.bins || []);
        const count = Number(histogram?.count) || 0;
        const min = Number(histogram?.min);
        const max = Number(histogram?.max);
        const transform = appearance?.transform || "linear";
        const lower = Number(appearance?.visible_min);
        const upper = Number(appearance?.visible_max);
        const selection = appearance?.range_mode === "range"
            && Number.isFinite(lower) && Number.isFinite(upper)
            ? [
                transform === "log" ? Math.log10(lower) : lower,
                transform === "log" ? Math.log10(upper) : upper
            ]
            : null;
        canvas._appearanceHistogram = {bins, min, max, transform, selection};
        bindAppearanceHistogram(canvas);
        const minLabel = document.getElementById("histogram-min-label");
        const maxLabel = document.getElementById("histogram-max-label");
        if (minLabel) minLabel.textContent = count
            ? formatHistogramValue(histogramRawValue(min, transform)) : "\u2014";
        if (maxLabel) maxLabel.textContent = count
            ? formatHistogramValue(histogramRawValue(max, transform)) : "\u2014";
        canvas.title = count
            ? `${count.toLocaleString()} values; drag to filter`
            : "No scalar values available";
        drawAppearanceHistogram(canvas);
    }

    function renderAppearanceHistogram(canvas, values, appearance) {
        const finite = values.filter(Number.isFinite);
        let min = Infinity;
        let max = -Infinity;
        finite.forEach(value => {
            min = Math.min(min, value);
            max = Math.max(max, value);
        });
        const bins = finite.length ? new Uint32Array(36) : new Uint32Array();
        finite.forEach(value => {
            const index = Math.min(bins.length - 1, Math.max(0, Math.floor(
                bins.length * (value - min) / ((max - min) || 1)
            )));
            bins[index]++;
        });
        renderAppearanceHistogramData(canvas, {
            bins,
            count: finite.length,
            min,
            max
        }, appearance);
    }

    function multiply(a, b) {
        const out = new Float32Array(16);
        for (let column = 0; column < 4; column++) {
            for (let row = 0; row < 4; row++) {
                let value = 0;
                for (let inner = 0; inner < 4; inner++) {
                    value += a[inner * 4 + row] * b[column * 4 + inner];
                }
                out[column * 4 + row] = value;
            }
        }
        return out;
    }

    function perspective(fov, aspect, near, far) {
        const f = 1 / Math.tan(fov / 2);
        const out = new Float32Array(16);
        out[0] = f / aspect;
        out[5] = f;
        out[10] = (far + near) / (near - far);
        out[11] = -1;
        out[14] = 2 * far * near / (near - far);
        return out;
    }

    function normalize(vector) {
        const length = Math.hypot(vector[0], vector[1], vector[2]) || 1;
        return vector.map(value => value / length);
    }

    function cross(a, b) {
        return [
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]
        ];
    }

    function dot(a, b) {
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    }

    function detectorBasis(upDir) {
        const up = normalize(upDir || [0, 1, 0]);
        let reference = [0, 0, 1];
        if (Math.abs(dot(reference, up)) > 1 - 1e-8) {
            reference = [0, 1, 0];
        }
        const forward = normalize(reference.map(
            (value, axis) => value - dot(reference, up) * up[axis]
        ));
        return {right: normalize(cross(up, forward)), up, forward};
    }

    function orientCameraVector(vector, basis) {
        return [0, 1, 2].map(axis => (
            vector[0] * basis.right[axis]
            + vector[1] * basis.up[axis]
            + vector[2] * basis.forward[axis]
        ));
    }

    function cameraDirection(camera, basis) {
        const horizontal = Math.cos(camera.pitch);
        return orientCameraVector([
            horizontal * Math.cos(camera.yaw),
            Math.sin(camera.pitch),
            horizontal * Math.sin(camera.yaw)
        ], basis);
    }

    function lookAt(eye, center, up) {
        const z = normalize([
            eye[0] - center[0], eye[1] - center[1], eye[2] - center[2]
        ]);
        const x = normalize(cross(up, z));
        const y = cross(z, x);
        return new Float32Array([
            x[0], y[0], z[0], 0,
            x[1], y[1], z[1], 0,
            x[2], y[2], z[2], 0,
            -x[0] * eye[0] - x[1] * eye[1] - x[2] * eye[2],
            -y[0] * eye[0] - y[1] * eye[1] - y[2] * eye[2],
            -z[0] * eye[0] - z[1] * eye[1] - z[2] * eye[2], 1
        ]);
    }

    function compile(gl, type, source) {
        const shader = gl.createShader(type);
        gl.shaderSource(shader, source);
        gl.compileShader(shader);
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
            throw new Error(gl.getShaderInfoLog(shader));
        }
        return shader;
    }

    function createProgram(gl, fragmentSource = FRAGMENT_SHADER) {
        const program = gl.createProgram();
        gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, VERTEX_SHADER));
        gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, fragmentSource));
        gl.linkProgram(program);
        if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
            throw new Error(gl.getProgramInfoLog(program));
        }
        return program;
    }

    const NAMED_COLORS = {
        black: [0, 0, 0, 1], white: [1, 1, 1, 1], red: [1, 0, 0, 1],
        green: [0, 0.5, 0, 1], blue: [0, 0, 1, 1], orange: [1, 0.5, 0, 1],
        gray: [0.5, 0.5, 0.5, 1], grey: [0.5, 0.5, 0.5, 1],
        yellow: [1, 1, 0, 1], purple: [0.5, 0, 0.5, 1], cyan: [0, 1, 1, 1]
    };

    function parseColor(value, opacity, dark) {
        if (Array.isArray(value) && value.length >= 3
                && typeof value[0] === "number") {
            const scale = Math.max(...value.slice(0, 3)) > 1 ? 255 : 1;
            return [value[0] / scale, value[1] / scale, value[2] / scale,
                value.length > 3 ? value[3] : (opacity ?? 1)];
        }
        if (typeof value !== "string") return [0.95, 0.45, 0.08, opacity ?? 1];
        const lower = value.toLowerCase();
        if (dark && lower === "black") return [0.88, 0.9, 0.94, opacity ?? 1];
        if (NAMED_COLORS[lower]) {
            const result = NAMED_COLORS[lower].slice();
            result[3] = opacity ?? result[3];
            return result;
        }
        if (lower[0] === "#" && (lower.length === 7 || lower.length === 4)) {
            const text = lower.length === 4
                ? lower.slice(1).split("").map(item => item + item).join("")
                : lower.slice(1);
            return [
                parseInt(text.slice(0, 2), 16) / 255,
                parseInt(text.slice(2, 4), 16) / 255,
                parseInt(text.slice(4, 6), 16) / 255,
                opacity ?? 1
            ];
        }
        const match = lower.match(/rgba?\(([^)]+)\)/);
        if (match) {
            const parts = match[1].split(",").map(Number);
            return [parts[0] / 255, parts[1] / 255, parts[2] / 255,
                opacity ?? (parts[3] ?? 1)];
        }
        return [0.6, 0.6, 0.6, opacity ?? 1];
    }

    const NAMED_COLOR_SCALES = {
        inferno: ["#000004", "#420a68", "#932667", "#dd513a", "#fca50a", "#fcffa4"],
        viridis: ["#440154", "#414487", "#2a788e", "#22a884", "#7ad151", "#fde725"],
        cividis: ["#00204c", "#2e4a7d", "#666970", "#9a8954", "#d2b43c", "#fee838"],
        turbo: ["#30123b", "#4662d7", "#1ae4b6", "#a4fc3c", "#f9ba38", "#e4430a", "#7a0403"],
        rainbow: ["#96005a", "#0000c8", "#0019ff", "#0098ff", "#2cff96", "#97ff00", "#ffea00", "#ff6f00", "#ff0000"],
        hot: ["#000000", "#e60000", "#ffd200", "#ffffff"]
    };

    function ramp(value, colorscale, dark) {
        const t = Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0));
        const namedScale = NAMED_COLOR_SCALES[
            String(colorscale || "").toLowerCase()
        ];
        if (namedScale) colorscale = namedScale;
        if (Array.isArray(colorscale) && colorscale.length) {
            if (typeof colorscale[0] === "string") {
                // SPINE categorical palettes are ordered color arrays, whereas
                // continuous Plotly scales contain explicit [position, color]
                // stops. Interpolate the former over evenly spaced positions.
                if (colorscale.length === 1) {
                    return parseColor(colorscale[0], 1, dark);
                }
                const scaled = t * (colorscale.length - 1);
                const index = Math.min(Math.floor(scaled), colorscale.length - 2);
                const fraction = scaled - index;
                const a = parseColor(colorscale[index], 1, dark);
                const b = parseColor(colorscale[index + 1], 1, dark);
                return a.map((channel, channelIndex) =>
                    channel + fraction * (b[channelIndex] - channel)
                );
            }
            let left = colorscale[0], right = colorscale[colorscale.length - 1];
            for (let index = 1; index < colorscale.length; index++) {
                if (t <= colorscale[index][0]) {
                    left = colorscale[index - 1];
                    right = colorscale[index];
                    break;
                }
            }
            const fraction = (t - left[0]) / ((right[0] - left[0]) || 1);
            const a = parseColor(left[1], 1, dark);
            const b = parseColor(right[1], 1, dark);
            return a.map((channel, index) => channel + fraction * (b[index] - channel));
        }
        return [0.27 + 0.72 * t, 0.05 + 0.85 * Math.sin(Math.PI * t),
            0.33 + 0.45 * (1 - t), 1];
    }

    function parseScene(buffer) {
        const view = new DataView(buffer);
        const headerLength = view.getUint32(0, true);
        const header = JSON.parse(new TextDecoder().decode(
            new Uint8Array(buffer, 4, headerLength)
        ));
        const base = Math.ceil((4 + headerLength) / 4) * 4;
        const array = descriptor => {
            if (!descriptor) return null;
            const offset = base + descriptor.offset;
            const count = descriptor.length / 4;
            return descriptor.dtype === "int32"
                ? new Int32Array(buffer, offset, count)
                : new Float32Array(buffer, offset, count);
        };
        header.views.forEach(viewItem => viewItem.layers.forEach(layer => {
            ["positions", "values", "object_ids", "object_offsets", "segments",
                "origins", "vectors", "vertices", "faces", "bounds"].forEach(key => {
                layer[key] = array(layer[key]);
            });
            Object.entries(layer.attributes || {}).forEach(entry => {
                layer.attributes[entry[0]] = array(entry[1]);
            });
        }));
        return header;
    }

    function repeatIds(ids, repeats) {
        if (!ids) return null;
        const output = new Int32Array(ids.length * repeats);
        ids.forEach((id, index) => output.fill(id, index * repeats, (index + 1) * repeats));
        return output;
    }

    function repeatIndices(count, repeats) {
        const output = new Int32Array(count * repeats);
        for (let index = 0; index < count; index++) {
            output.fill(index, index * repeats, (index + 1) * repeats);
        }
        return output;
    }

    function svgElement(name, attributes = {}) {
        const element = document.createElementNS("http://www.w3.org/2000/svg", name);
        Object.entries(attributes).forEach(([key, value]) => {
            element.setAttribute(key, value);
        });
        return element;
    }

    function formatCoordinate(value, span) {
        const magnitude = Math.abs(value);
        if ((magnitude && magnitude >= 10000) || (magnitude && magnitude < 0.01)) {
            return value.toExponential(2);
        }
        const decimals = span < 10 ? 2 : span < 100 ? 1 : 0;
        return value.toFixed(decimals);
    }

    function formatPointCoordinate(value) {
        if (!Number.isFinite(value)) return String(value);
        if (Math.abs(value) >= 10000 || (value && Math.abs(value) < 0.001)) {
            return value.toExponential(3);
        }
        return Number(value.toFixed(3)).toString();
    }

    function formatAttributeValue(value) {
        const normalized = value.trim().toLowerCase();
        if (["inf", "+inf", "infinity", "+infinity"].includes(normalized)) {
            return "∞";
        }
        if (["-inf", "-infinity"].includes(normalized)) return "−∞";
        if (normalized === "true") return "True";
        if (normalized === "false") return "False";
        const number = Number(value);
        if (!Number.isFinite(number) || Number.isInteger(number)) return value.trim();
        return Number(number.toPrecision(6)).toString();
    }

    function normalizedAttributeName(value) {
        return value.toLowerCase().replace(/[^a-z0-9]/g, "").replace(/s$/, "");
    }

    class Viewer {
        constructor(root, scene) {
            this.root = root;
            this.scene = scene;
            this.dark = root.dataset.dark === "true";
            this.showAxes = root.dataset.showAxes !== "false";
            this.filterEnabled = root.dataset.filterEnabled !== "false";
            this.syncCameras = root.dataset.syncCameras !== "false";
            this.colorAttribute = root.dataset.colorAttribute || "";
            try {
                this.appearance = JSON.parse(root.dataset.appearance || "{}");
            } catch (_error) {
                this.appearance = {};
            }
            this.selection = new Set(
                (root.dataset.selection || "").split(",").filter(Boolean)
            );
            this.canvas = document.createElement("canvas");
            this.canvas.className = "webgl-canvas";
            this.axes = svgElement("svg", {class: "webgl-axes"});
            this.axes.setAttribute("aria-hidden", "true");
            this.hoverMarker = document.createElement("div");
            this.hoverMarker.className = "webgl-hover-marker";
            this.hoverMarker.hidden = true;
            this.tooltip = document.createElement("div");
            this.tooltip.className = "webgl-tooltip";
            this.titles = document.createElement("div");
            this.titles.className = "webgl-view-titles";
            scene.views.forEach(view => {
                const title = document.createElement("span");
                title.textContent = view.name;
                this.titles.appendChild(title);
            });
            root.replaceChildren(
                this.canvas, this.axes, this.hoverMarker, this.titles,
                this.tooltip
            );
            this.gl = this.canvas.getContext("webgl2", {
                antialias: true, alpha: false, preserveDrawingBuffer: true
            });
            if (!this.gl) throw new Error("WebGL 2 is not available; select Plotly.");
            try {
                this.program = createProgram(this.gl);
                this.supportsMarkerSymbols = true;
            } catch (error) {
                // Some WebGL drivers reject gl_PointCoord even though WebGL 2
                // exposes it. Keep rendering available with square points.
                console.warn("Marker-symbol shader unavailable:", error);
                this.program = createProgram(this.gl, SIMPLE_FRAGMENT_SHADER);
                this.supportsMarkerSymbols = false;
            }
            this.positionLocation = this.gl.getAttribLocation(this.program, "aPosition");
            this.colorLocation = this.gl.getAttribLocation(this.program, "aColor");
            this.mvpLocation = this.gl.getUniformLocation(this.program, "uMvp");
            this.pointSizeLocation = this.gl.getUniformLocation(this.program, "uPointSize");
            this.symbolLocation = this.gl.getUniformLocation(this.program, "uSymbol");
            this.layers = scene.views.map(view => view.layers.map(layer => this.prepare(layer)));
            this.mixedObjectViews = scene.views.map(view => {
                const prefixes = new Set(view.layers.map(layer =>
                    layer.metadata?.object_name?.split("_", 1)[0]
                ).filter(Boolean));
                return prefixes.has("reco") && prefixes.has("truth");
            });
            this.pickFramebuffer = null;
            this.pickTexture = null;
            this.pickDepth = null;
            this.pickRanges = [];
            this.pickDataDirty = true;
            this.pickDirty = true;
            this.hoverPositionBuffer = this.gl.createBuffer();
            this.hoverColorBuffer = this.gl.createBuffer();
            this.hoverHaloBuffer = this.gl.createBuffer();
            this.hoverCount = 0;
            this.selectedPositionBuffer = this.gl.createBuffer();
            this.selectedColorBuffer = this.gl.createBuffer();
            this.selectedHaloBuffer = this.gl.createBuffer();
            this.selectedCount = 0;
            this.matchedPositionBuffer = this.gl.createBuffer();
            this.matchedColorBuffer = this.gl.createBuffer();
            this.matchedHaloBuffer = this.gl.createBuffer();
            this.matchedCount = 0;
            this.initializeCamera();
            this.installEvents();
            this.resizeObserver = new ResizeObserver(() => this.draw());
            this.resizeObserver.observe(root);
            this.setSelection([...this.selection]);
            this.drawHistogram();
        }

        initializeCamera() {
            this.cameraBasis = detectorBasis(this.scene.metadata.up_dir);
            const bounds = this.scene.metadata.bounds;
            let cameraBounds;
            if (bounds) {
                this.target = bounds.map(pair => (pair[0] + pair[1]) / 2);
                this.radius = Math.max(...bounds.map(pair => pair[1] - pair[0])) || 1;
                cameraBounds = bounds;
            } else {
                const low = [Infinity, Infinity, Infinity];
                const high = [-Infinity, -Infinity, -Infinity];
                let positionCount = 0;
                this.layers.flat().forEach(item => {
                    for (let index = 0; index < item.basePositions.length; index += 3) {
                        for (let axis = 0; axis < 3; axis++) {
                            low[axis] = Math.min(low[axis], item.basePositions[index + axis]);
                            high[axis] = Math.max(high[axis], item.basePositions[index + axis]);
                        }
                        positionCount++;
                    }
                });
                if (positionCount) {
                    this.target = low.map((value, axis) => (value + high[axis]) / 2);
                    this.radius = Math.max(...low.map((value, axis) => high[axis] - value)) || 1;
                    cameraBounds = low.map((value, axis) => [value, high[axis]]);
                } else {
                    this.target = [0, 0, 0];
                    this.radius = 1;
                    cameraBounds = [[-0.5, 0.5], [-0.5, 0.5], [-0.5, 0.5]];
                }
            }

            // Match SPINE's Plotly camera. Plotly expresses eye and center in
            // normalized scene coordinates, where one unit is the longest
            // displayed axis. Convert that specification into the spherical
            // camera used by this viewer rather than approximating its angles.
            const plotlyEye = orientCameraVector(
                [-2.0, 1.0, -0.01], this.cameraBasis
            );
            const plotlyCenter = orientCameraVector(
                [0.0, -0.1, -0.01], this.cameraBasis
            );
            const sceneScale = this.radius;
            const offset = plotlyEye.map(
                (value, axis) => (value - plotlyCenter[axis]) * sceneScale
            );
            this.target = this.target.map(
                (value, axis) => value + plotlyCenter[axis] * sceneScale
            );
            const cameraBack = normalize(offset);
            const cameraRight = normalize(cross(this.cameraBasis.up, cameraBack));
            const cameraUp = cross(cameraBack, cameraRight);
            const viewWidth = this.root.clientWidth / this.layers.length;
            const aspect = viewWidth > 0 && this.root.clientHeight > 0
                ? viewWidth / this.root.clientHeight
                : 1;
            const tangent = Math.tan(CAMERA_FOV / 2);
            const frameFraction = 0.75;
            let fitDistance = 0;

            // Fit the projected box instead of scaling by its longest side.
            // A long detector axis directed toward the eye then contributes
            // depth, but does not incorrectly shrink the on-screen geometry.
            for (let corner = 0; corner < 8; corner++) {
                const point = cameraBounds.map(
                    (pair, axis) => pair[(corner >> axis) & 1]
                );
                const relative = point.map(
                    (value, axis) => value - this.target[axis]
                );
                const depth = dot(relative, cameraBack);
                fitDistance = Math.max(
                    fitDistance,
                    depth + Math.abs(dot(relative, cameraRight))
                        / (tangent * aspect * frameFraction),
                    depth + Math.abs(dot(relative, cameraUp))
                        / (tangent * frameFraction)
                );
            }
            const distance = Math.max(fitDistance, this.radius * 0.1);
            const basisDirection = [
                dot(cameraBack, this.cameraBasis.right),
                dot(cameraBack, this.cameraBasis.up),
                dot(cameraBack, this.cameraBasis.forward)
            ];
            this.initialCamera = {
                target: this.target.slice(),
                distance,
                yaw: Math.atan2(basisDirection[2], basisDirection[0]),
                pitch: Math.asin(Math.max(-1, Math.min(1, basisDirection[1])))
            };
            this.resetCamera(false);
        }

        copyCamera(camera) {
            return {
                target: camera.target.slice(),
                distance: camera.distance,
                yaw: camera.yaw,
                pitch: camera.pitch
            };
        }

        resetCamera(draw = true, viewIndex = null) {
            if (!this.cameras) {
                this.cameras = this.layers.map(
                    () => this.copyCamera(this.initialCamera)
                );
            } else if (viewIndex == null || this.syncCameras) {
                this.cameras = this.layers.map(
                    () => this.copyCamera(this.initialCamera)
                );
            } else if (this.cameras[viewIndex]) {
                this.cameras[viewIndex] = this.copyCamera(this.initialCamera);
            }
            if (draw) this.draw();
        }

        cameraState() {
            return {
                cameras: this.cameras.map(camera => this.copyCamera(camera))
            };
        }

        restoreCamera(camera) {
            if (!camera) return;
            const cached = Array.isArray(camera.cameras)
                ? camera.cameras
                : Array.isArray(camera.target) ? [camera] : [];
            if (!cached.length) return;

            if (this.syncCameras) {
                this.cameras = this.layers.map(
                    () => this.copyCamera(cached[0])
                );
            } else {
                this.cameras = this.layers.map((_, index) => this.copyCamera(
                    cached[index] || cached[0]
                ));
            }
            this.draw();
        }

        setRotationCenter(position, viewIndex = 0) {
            const target = Array.from(position || [], Number);
            if (!this.cameras.length || target.length !== 3 ||
                    !target.every(Number.isFinite)) return false;

            const index = Math.max(0, Math.min(
                this.cameras.length - 1,
                Math.trunc(Number(viewIndex) || 0)
            ));
            if (this.syncCameras) {
                this.cameras.forEach(camera => {
                    camera.target = target.slice();
                });
            } else if (this.cameras[index]) {
                this.cameras[index].target = target.slice();
            } else {
                return false;
            }
            this.tooltip.hidden = true;
            this.hoverItem = null;
            this.hoverObject = null;
            this.hoverCount = 0;
            this.hoverMarker.hidden = true;
            this.draw();
            return true;
        }

        viewIndexAt(clientX) {
            const bounds = this.canvas.getBoundingClientRect();
            const fraction = bounds.width
                ? (clientX - bounds.left) / bounds.width
                : 0;
            return Math.max(0, Math.min(
                this.layers.length - 1,
                Math.floor(fraction * this.layers.length)
            ));
        }

        updateLinkedCameras(sourceIndex) {
            if (!this.syncCameras) return;
            const source = this.cameras[sourceIndex];
            this.cameras = this.cameras.map(
                () => this.copyCamera(source)
            );
        }

        async saveImage(
            filename = "spinal_tap_event_display.png",
            overlay = null,
            reserveLabelRow = false
        ) {
            this.draw();
            const output = document.createElement("canvas");
            output.width = this.canvas.width;
            output.height = this.canvas.height;
            const context = output.getContext("2d");
            if (!context) throw new Error("Could not create the export canvas.");
            context.drawImage(this.canvas, 0, 0);
            await this.drawGifOverlay(
                context, output.width, output.height, reserveLabelRow
            );
            if (overlay) await overlay(context, output.width, output.height);
            const link = document.createElement("a");
            link.download = filename;
            link.href = output.toDataURL("image/png");
            link.click();
        }

        async drawGifOverlay(context, width, height, reserveLabelRow = false) {
            if (this.showAxes && this.axes.childNodes.length) {
                const axes = this.axes.cloneNode(true);
                axes.setAttribute("xmlns", "http://www.w3.org/2000/svg");
                axes.setAttribute("width", this.root.clientWidth);
                axes.setAttribute("height", this.root.clientHeight);
                const style = document.createElementNS(
                    "http://www.w3.org/2000/svg", "style"
                );
                style.textContent = `
                    .webgl-axis-box,.webgl-axis-line,.webgl-axis-tick {
                        fill:none;vector-effect:non-scaling-stroke
                    }
                    .webgl-axis-box {stroke-width:1px}
                    .webgl-axis-line {stroke-width:1.4px}
                    .webgl-axis-tick {stroke-width:1px}
                    .webgl-axis-label {
                        font-family:system-ui,sans-serif;font-size:11px;
                        font-weight:650;paint-order:stroke;stroke-width:3px;
                        stroke-linejoin:round
                    }
                    .webgl-axis-title {font-size:12px;font-weight:800}
                `;
                axes.prepend(style);
                const blob = new Blob(
                    [new XMLSerializer().serializeToString(axes)],
                    {type: "image/svg+xml"}
                );
                const url = URL.createObjectURL(blob);
                try {
                    const image = await new Promise((resolve, reject) => {
                        const overlay = new Image();
                        overlay.onload = () => resolve(overlay);
                        overlay.onerror = () => reject(
                            new Error("Could not render GIF axes.")
                        );
                        overlay.src = url;
                    });
                    context.drawImage(image, 0, 0, width, height);
                } finally {
                    URL.revokeObjectURL(url);
                }
            }

            const titles = Array.from(this.titles.children);
            // A lone object-family title (for example, "Particles") merely
            // repeats the active control. Dual-view titles carry the useful
            // reconstructed/truth distinction and remain in exports.
            if (titles.length < 2) return;
            const scale = width / Math.max(1, this.root.clientWidth);
            context.fillStyle = this.dark ? "#f3f4f6" : "#17191d";
            context.font = `800 ${Math.max(9, 13 * scale)}px system-ui`;
            context.textAlign = "center";
            context.textBaseline = "top";
            const labelOffset = reserveLabelRow
                ? Math.max(11, Math.min(width, height) * 0.022) * 1.35
                : 0;
            titles.forEach((title, index) => {
                context.fillText(
                    title.textContent,
                    width * (index + 0.5) / titles.length,
                    Math.max(8, 12 * scale) + labelOffset
                );
            });
        }

        async saveGif(
            progress = () => {},
            filename = "spinal_tap_event_display.gif",
            overlay = null,
            reserveLabelRow = false
        ) {
            if (!window.spinalTapGif?.Encoder) {
                throw new Error("The GIF encoder is not available.");
            }

            const frames = 180;
            const frameDelay = 2;
            const maximumSize = 900;
            const scale = Math.min(
                1, maximumSize / Math.max(this.canvas.width, this.canvas.height)
            );
            const width = Math.max(1, Math.round(this.canvas.width * scale));
            const height = Math.max(1, Math.round(this.canvas.height * scale));
            const output = document.createElement("canvas");
            output.width = width;
            output.height = height;
            const context = output.getContext("2d", {willReadFrequently: true});
            if (!context) throw new Error("Could not create the GIF canvas.");
            const encoder = new window.spinalTapGif.Encoder(
                width, height, frameDelay
            );
            const original = this.cameras.map(camera => this.copyCamera(camera));
            const hoverCount = this.hoverCount;
            const hoverHidden = this.hoverMarker.hidden;
            this.hoverCount = 0;
            this.hoverMarker.hidden = true;
            this.tooltip.hidden = true;

            try {
                for (let frame = 0; frame < frames; frame++) {
                    const angle = 2 * Math.PI * frame / frames;
                    this.cameras = original.map(camera => Object.assign(
                        this.copyCamera(camera), {yaw: camera.yaw + angle}
                    ));
                    this.draw();
                    context.drawImage(this.canvas, 0, 0, width, height);
                    await this.drawGifOverlay(
                        context, width, height, reserveLabelRow
                    );
                    if (overlay) await overlay(context, width, height);
                    encoder.addFrame(
                        context.getImageData(0, 0, width, height).data
                    );
                    progress(frame + 1, frames);
                    await new Promise(resolve => requestAnimationFrame(resolve));
                }

                const blob = encoder.finish();
                const url = URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.download = filename;
                link.href = url;
                link.click();
                setTimeout(() => URL.revokeObjectURL(url), 0);
            } finally {
                this.cameras = original.map(camera => this.copyCamera(camera));
                this.hoverCount = hoverCount;
                this.hoverMarker.hidden = hoverHidden;
                this.draw();
            }
        }

        valuesFor(item, attribute) {
            const layer = item.source;
            if (attribute && layer.attributes && layer.attributes[attribute]) {
                return layer.attributes[attribute];
            }
            return layer.values;
        }

        colors(item, indices, attribute = this.colorAttribute) {
            const layer = item.source;
            const baseStyle = layer.style || layer.line_style || layer.mesh_style || {};
            const attributeStyle = attribute
                ? layer.metadata.attribute_styles?.[attribute]
                : null;
            const style = Object.assign({}, baseStyle, attributeStyle || {});
            const sourceValues = this.valuesFor(item, attribute);
            const continuous = typeof style.colorscale === "string";
            if (continuous && this.appearance.colorscale) {
                style.colorscale = this.appearance.colorscale;
            }
            const output = new Float32Array(indices.length * 4);
            const sharedNumeric = typeof layer.shared_value === "number"
                ? layer.shared_value
                : null;
            const fixed = sharedNumeric != null
                ? ramp((sharedNumeric - (style.cmin ?? 0)) /
                    (((style.cmax ?? 1) - (style.cmin ?? 0)) || 1),
                    style.colorscale, this.dark)
                : parseColor(style.color ?? layer.shared_value, style.opacity, this.dark);
            if (sharedNumeric != null) fixed[3] *= style.opacity ?? 1;
            // Attribute styles may declare a stable domain for categorical or
            // otherwise schema-defined values. Only infer limits when SPINE did
            // not provide them; deriving enum limits from the current layer
            // would make the same enum value change color between events.
            let min = style.cmin;
            let max = style.cmax;
            if (sourceValues && (min == null || max == null)) {
                min = Infinity;
                max = -Infinity;
                for (const value of sourceValues) {
                    if (Number.isFinite(value)) {
                        min = Math.min(min, value);
                        max = Math.max(max, value);
                    }
                }
            }
            if (continuous && this.appearance.domain_mode === "manual") {
                min = this.appearance.color_min ?? min;
                max = this.appearance.color_max ?? max;
            }
            const logarithmic = continuous
                && this.appearance.transform === "log";
            if (logarithmic && sourceValues && (!(min > 0) || !(max > 0))) {
                let positiveMin = Infinity;
                let positiveMax = -Infinity;
                for (const value of sourceValues) {
                    if (Number.isFinite(value) && value > 0) {
                        positiveMin = Math.min(positiveMin, value);
                        positiveMax = Math.max(positiveMax, value);
                    }
                }
                if (Number.isFinite(positiveMin)) {
                    if (!(min > 0)) min = positiveMin;
                    if (!(max > 0)) max = positiveMax;
                }
            }
            const transformed = value => logarithmic
                ? (value > 0 ? Math.log10(value) : NaN)
                : value;
            min = transformed(min);
            max = transformed(max);
            indices.forEach((sourceIndex, index) => {
                const rgba = sourceValues
                    ? ramp((transformed(sourceValues[sourceIndex]) - min) /
                        ((max - min) || 1),
                        style.colorscale, this.dark)
                    : fixed;
                const displayed = rgba.slice();
                if (sourceValues) displayed[3] *= style.opacity ?? 1;
                if (item.source.type === "point") {
                    displayed[3] *= this.appearance.opacity ?? 1;
                }
                if (layer.metadata.kind === "geometry") {
                    // Geometry is structural UI, so keep it legible when the
                    // theme changes without requiring a new scene payload.
                    const channel = this.dark ? 0.82 : 0.18;
                    displayed[0] = channel;
                    displayed[1] = channel;
                    displayed[2] = channel;
                    displayed[3] = Math.max(displayed[3], this.dark ? 0.65 : 0.45);
                } else if (layer.type === "vector" && this.dark
                        && displayed[0] < 0.15
                        && displayed[1] < 0.15
                        && displayed[2] < 0.15) {
                    // Direction arrows default to black in SPINE. Lift that
                    // neutral color in dark mode without changing colored arrows.
                    displayed[0] = 0.88;
                    displayed[1] = 0.88;
                    displayed[2] = 0.88;
                }
                output.set(displayed, index * 4);
            });
            return output;
        }

        prepare(layer) {
            let positions = layer.positions;
            let indices = null;
            let sourceIndices = null;
            let selectionIds = layer.object_ids;
            let mode = this.gl.POINTS;
            let symbol = layer.type === "marker"
                ? ({circle: 1, "circle-open": 2, diamond: 3}[layer.symbol] || 1)
                : 1;

            if (layer.type === "point" || layer.type === "marker") {
                const count = positions.length / 3;
                sourceIndices = repeatIndices(count, 1);
                if (layer.object_offsets && layer.metadata.object_name) {
                    selectionIds = new Int32Array(count);
                    for (let object = 0; object < layer.object_offsets.length - 1; object++) {
                        selectionIds.fill(object, layer.object_offsets[object],
                            layer.object_offsets[object + 1]);
                    }
                }
            } else if (layer.type === "line") {
                positions = layer.segments;
                const count = positions.length / 6;
                selectionIds = repeatIds(layer.object_ids, 2);
                sourceIndices = repeatIndices(count, 2);
                mode = this.gl.LINES;
                symbol = 0;
            } else if (layer.type === "vector") {
                const count = layer.origins.length / 3;
                const radialSegments = 10;
                const verticesPerVector = radialSegments * 12;
                const output = [];
                for (let index = 0; index < count; index++) {
                    const offset = index * 3;
                    const origin = Array.from(layer.origins.subarray(offset, offset + 3));
                    const vector = Array.from(layer.vectors.subarray(offset, offset + 3))
                        .map(value => value * layer.scale);
                    const tip = origin.map((value, axis) => value + vector[axis]);
                    const length = Math.hypot(...vector) || 1;
                    const direction = normalize(vector);
                    const reference = Math.abs(direction[2]) < 0.9 ? [0, 0, 1] : [0, 1, 0];
                    const side = normalize(cross(direction, reference));
                    const up = normalize(cross(direction, side));
                    const headLength = length * layer.head_size;
                    const headBase = tip.map(
                        (value, axis) => value - direction[axis] * headLength
                    );
                    const shaftRadius = length
                        * Math.max(layer.style?.width || 2, 1) * 0.0025;
                    const headRadius = Math.max(
                        shaftRadius * 2.4, headLength * 0.4
                    );

                    const ringPoint = function(center, radius, angle) {
                        return center.map((value, axis) => value + radius * (
                            side[axis] * Math.cos(angle)
                            + up[axis] * Math.sin(angle)
                        ));
                    };
                    for (let segment = 0; segment < radialSegments; segment++) {
                        const angle = 2 * Math.PI * segment / radialSegments;
                        const nextAngle = 2 * Math.PI
                            * (segment + 1) / radialSegments;
                        const originA = ringPoint(origin, shaftRadius, angle);
                        const originB = ringPoint(origin, shaftRadius, nextAngle);
                        const shaftA = ringPoint(headBase, shaftRadius, angle);
                        const shaftB = ringPoint(headBase, shaftRadius, nextAngle);
                        const headA = ringPoint(headBase, headRadius, angle);
                        const headB = ringPoint(headBase, headRadius, nextAngle);

                        // Two shaft triangles, one cone-side triangle and one
                        // back cap make a solid arrow from every camera angle.
                        output.push(
                            ...originA, ...shaftA, ...shaftB,
                            ...originA, ...shaftB, ...originB,
                            ...tip, ...headA, ...headB,
                            ...headBase, ...headB, ...headA
                        );
                    }
                }
                positions = new Float32Array(output);
                selectionIds = repeatIds(layer.object_ids, verticesPerVector);
                sourceIndices = repeatIndices(count, verticesPerVector);
                mode = this.gl.TRIANGLES;
                symbol = 0;
            } else if (layer.type === "mesh") {
                if (layer.style?.wireframe) {
                    const output = [];
                    const mappedIndices = [];
                    for (let face = 0; face < layer.faces.length; face += 3) {
                        const a = layer.faces[face];
                        const b = layer.faces[face + 1];
                        const c = layer.faces[face + 2];
                        [a, b, b, c, c, a].forEach(vertex => {
                            output.push(...layer.vertices.subarray(vertex * 3, vertex * 3 + 3));
                            mappedIndices.push(vertex);
                        });
                    }
                    positions = new Float32Array(output);
                    sourceIndices = new Int32Array(mappedIndices);
                    mode = this.gl.LINES;
                } else {
                    positions = layer.vertices;
                    indices = new Uint32Array(layer.faces);
                    sourceIndices = repeatIndices(positions.length / 3, 1);
                    mode = this.gl.TRIANGLES;
                }
                selectionIds = null;
                symbol = 0;
            } else if (layer.type === "box") {
                const corners = [[0,0,0],[1,0,0],[1,1,0],[0,1,0],
                    [0,0,1],[1,0,1],[1,1,1],[0,1,1]];
                const edges = [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],
                    [6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
                const faces = [[0,1,2],[0,2,3],[4,6,5],[4,7,6],[0,4,5],
                    [0,5,1],[1,5,6],[1,6,2],[2,6,7],[2,7,3],[3,7,4],[3,4,0]];
                const repeats = layer.draw_faces ? 36 : 24;
                const output = [];
                for (let box = 0; box < layer.bounds.length / 6; box++) {
                    const low = layer.bounds.subarray(box * 6, box * 6 + 3);
                    const high = layer.bounds.subarray(box * 6 + 3, box * 6 + 6);
                    const points = corners.map(corner => corner.map(
                        (bit, axis) => bit ? high[axis] : low[axis]
                    ));
                    const templates = layer.draw_faces ? faces : edges;
                    templates.forEach(template => template.forEach(vertex => {
                        output.push(...points[vertex]);
                    }));
                }
                positions = new Float32Array(output);
                selectionIds = repeatIds(layer.object_ids, repeats);
                sourceIndices = repeatIndices(layer.bounds.length / 6, repeats);
                mode = layer.draw_faces ? this.gl.TRIANGLES : this.gl.LINES;
                symbol = 0;
            }

            const item = {
                source: layer,
                mode,
                symbol,
                indices,
                selectionIds,
                activeSelectionIds: selectionIds,
                basePositions: positions,
                baseSourceIndices: sourceIndices,
                activeSourceIndices: sourceIndices,
                positions,
                positionBuffer: this.gl.createBuffer(),
                colorBuffer: this.gl.createBuffer(),
                indexBuffer: indices ? this.gl.createBuffer() : null,
                count: indices ? indices.length : positions.length / 3
            };
            item.colors = this.colors(item, item.activeSourceIndices);
            this.upload(item);
            return item;
        }

        upload(item) {
            const gl = this.gl;
            gl.bindBuffer(gl.ARRAY_BUFFER, item.positionBuffer);
            gl.bufferData(gl.ARRAY_BUFFER, item.positions, gl.STATIC_DRAW);
            gl.bindBuffer(gl.ARRAY_BUFFER, item.colorBuffer);
            gl.bufferData(gl.ARRAY_BUFFER, item.colors, gl.STATIC_DRAW);
            if (item.indices) {
                gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, item.indexBuffer);
                gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, item.indices, gl.STATIC_DRAW);
            }
        }

        setSelection(selection) {
            this.selection = new Set(selection || []);
            this.root.dataset.selection = [...this.selection].join(",");
            this.refreshFilters();
        }

        scalarVisible(item, sourceIndex) {
            if (this.appearance.range_mode !== "range") return true;
            const layer = item.source;
            const baseStyle = layer.style || layer.line_style || {};
            const attributeStyle = this.colorAttribute
                ? layer.metadata.attribute_styles?.[this.colorAttribute]
                : null;
            const style = Object.assign({}, baseStyle, attributeStyle || {});
            if (typeof style.colorscale !== "string") return true;
            const values = this.valuesFor(item, this.colorAttribute);
            if (!values || sourceIndex >= values.length) return true;
            const value = values[sourceIndex];
            const lower = this.appearance.visible_min;
            const upper = this.appearance.visible_max;
            return Number.isFinite(value)
                && (lower == null || value >= lower)
                && (upper == null || value <= upper)
                && (this.appearance.transform !== "log" || value > 0);
        }

        refreshFilters() {
            this.layers.flat().forEach(item => {
                const layer = item.source;
                const objectName = layer.metadata.object_name;
                const scalarRange = this.appearance.range_mode === "range"
                    && layer.type === "point";
                if ((!this.filterEnabled || !item.selectionIds || !objectName)
                        && !scalarRange) {
                    item.colors = this.colors(item, item.activeSourceIndices);
                    this.upload(item);
                    return;
                }
                const prefix = objectName ? objectName.split("_", 1)[0] : "";
                const objectIds = new Set(item.selectionIds || []);
                const allSelected = !this.filterEnabled || !item.selectionIds
                    || !objectName || [...objectIds].every(
                        object => this.selection.has(prefix + ":" + object)
                    );

                // Keep the original GPU-ready buffers when a complete layer
                // is selected instead of copying every point during refresh.
                if (allSelected && !scalarRange) {
                    item.positions = item.basePositions;
                    item.activeSourceIndices = item.baseSourceIndices;
                    item.activeSelectionIds = item.selectionIds;
                    item.colors = this.colors(item, item.activeSourceIndices);
                    item.indices = null;
                    item.count = item.positions.length / 3;
                    this.upload(item);
                    return;
                }

                const positions = [];
                const sourceIndices = [];
                const selectionIds = item.selectionIds ? [] : null;
                const count = item.basePositions.length / 3;
                for (let vertex = 0; vertex < count; vertex++) {
                    if (!allSelected && !this.selection.has(
                        prefix + ":" + item.selectionIds[vertex]
                    )) continue;
                    if (!this.scalarVisible(item, item.baseSourceIndices[vertex])) {
                        continue;
                    }
                    positions.push(...item.basePositions.subarray(vertex * 3, vertex * 3 + 3));
                    sourceIndices.push(item.baseSourceIndices[vertex]);
                    if (selectionIds) {
                        selectionIds.push(item.selectionIds[vertex]);
                    }
                }
                item.positions = new Float32Array(positions);
                item.activeSourceIndices = new Int32Array(sourceIndices);
                item.activeSelectionIds = selectionIds
                    ? new Int32Array(selectionIds)
                    : null;
                item.colors = this.colors(item, item.activeSourceIndices);
                item.indices = null;
                item.count = item.positions.length / 3;
                this.upload(item);
            });
            this.hoverItem = null;
            this.hoverCount = 0;
            this.hoverMarker.hidden = true;
            this.tooltip.hidden = true;
            this.pickDataDirty = true;
            this.draw();
        }

        setAppearance(settings) {
            this.appearance = Object.assign({}, this.appearance, settings || {});
            this.root.dataset.appearance = JSON.stringify(this.appearance);
            this.refreshFilters();
            this.drawHistogram();
        }

        drawHistogram() {
            const canvas = document.getElementById("appearance-histogram");
            if (!canvas) return;
            const values = [];
            this.layers.flat().forEach(item => {
                const layer = item.source;
                const baseStyle = layer.style || layer.line_style || {};
                const attributeStyle = this.colorAttribute
                    ? layer.metadata.attribute_styles?.[this.colorAttribute]
                    : null;
                const style = Object.assign({}, baseStyle, attributeStyle || {});
                if (typeof style.colorscale !== "string") return;
                const source = this.valuesFor(item, this.colorAttribute);
                if (!source || typeof source === "string"
                        || typeof source[Symbol.iterator] !== "function") return;
                for (const value of source) {
                    if (Number.isFinite(value) &&
                            (this.appearance.transform !== "log" || value > 0)) {
                        values.push(this.appearance.transform === "log"
                            ? Math.log10(value) : value);
                    }
                }
            });
            renderAppearanceHistogram(canvas, values, this.appearance);
        }

        setColorAttribute(attribute) {
            this.colorAttribute = attribute || "";
            this.root.dataset.colorAttribute = this.colorAttribute;
            this.refreshFilters();
            this.drawHistogram();
            this.hoverItem = null;
            this.hoverCount = 0;
            this.hoverMarker.hidden = true;
            this.tooltip.hidden = true;
            this.draw();
        }

        setDark(dark) {
            this.dark = dark;
            this.root.dataset.dark = String(dark);
            this.layers.flat().forEach(item => {
                item.colors = this.colors(item, item.activeSourceIndices);
                this.upload(item);
            });
            this.hoverItem = null;
            this.hoverCount = 0;
            this.hoverMarker.hidden = true;
            this.tooltip.hidden = true;
            this.draw();
        }

        setAxesVisible(visible) {
            this.showAxes = Boolean(visible);
            this.root.dataset.showAxes = String(this.showAxes);
            if (this.showAxes) {
                this.drawAxes(this.root.clientWidth, this.root.clientHeight);
            } else {
                this.axes.replaceChildren();
            }
        }

        installEvents() {
            let active = false;
            let button = 0;
            let lastX = 0;
            let lastY = 0;
            let moved = 0;
            let activeView = 0;
            this.canvas.addEventListener("pointerdown", event => {
                active = true;
                button = event.button;
                activeView = this.viewIndexAt(event.clientX);
                lastX = event.clientX;
                lastY = event.clientY;
                moved = 0;
                this.canvas.setPointerCapture(event.pointerId);
            });
            this.canvas.addEventListener("pointerup", event => {
                active = false;
                if (moved < 3) this.pick(event, true);
            });
            this.canvas.addEventListener("pointermove", event => {
                if (!active) {
                    this.queuePick(event);
                    return;
                }
                const dx = event.clientX - lastX;
                const dy = event.clientY - lastY;
                moved += Math.abs(dx) + Math.abs(dy);
                lastX = event.clientX;
                lastY = event.clientY;
                const camera = this.cameras[activeView];
                if (button === 2 || event.shiftKey) {
                    const scale = camera.distance * 0.0015;
                    const eyeDirection = cameraDirection(
                        camera, this.cameraBasis
                    );
                    const right = normalize(cross(
                        this.cameraBasis.up, eyeDirection
                    ));
                    for (let axis = 0; axis < 3; axis++) {
                        camera.target[axis] -= right[axis] * dx * scale;
                        camera.target[axis] += (
                            this.cameraBasis.up[axis] * dy * scale
                        );
                    }
                } else {
                    camera.yaw -= dx * 0.008;
                    camera.pitch = Math.max(
                        -1.5, Math.min(1.5, camera.pitch + dy * 0.008)
                    );
                }
                this.updateLinkedCameras(activeView);
                this.tooltip.hidden = true;
                this.clearHover();
                this.draw();
            });
            this.canvas.addEventListener("pointerleave", () => {
                this.hoverEvent = null;
                this.tooltip.hidden = true;
                this.clearHover();
            });
            this.canvas.addEventListener("contextmenu", event => event.preventDefault());
            this.canvas.addEventListener("wheel", event => {
                event.preventDefault();
                const viewIndex = this.viewIndexAt(event.clientX);
                const camera = this.cameras[viewIndex];
                camera.distance *= Math.exp(event.deltaY * 0.001);
                camera.distance = Math.max(this.radius * 0.02, camera.distance);
                this.updateLinkedCameras(viewIndex);
                this.tooltip.hidden = true;
                this.clearHover();
                this.draw();
            }, {passive: false});
            this.canvas.addEventListener("dblclick", event => {
                this.resetCamera(true, this.viewIndexAt(event.clientX));
            });
            this.canvas.addEventListener("webglcontextlost", event => {
                event.preventDefault();
                this.showMessage("WebGL context was lost; select Plotly or reload the event.");
            });
        }

        queuePick(event) {
            this.hoverEvent = {clientX: event.clientX, clientY: event.clientY};
            if (this.pickFrame) return;
            this.pickFrame = requestAnimationFrame(() => {
                this.pickFrame = null;
                if (this.hoverEvent) this.pick(this.hoverEvent);
            });
        }

        showMessage(message, x, y) {
            this.tooltip.textContent = message;
            this.tooltip.hidden = false;
            if (x != null) {
                const bounds = this.root.getBoundingClientRect();
                this.tooltip.style.left = `${x - bounds.left + 12}px`;
                this.tooltip.style.top = `${y - bounds.top + 12}px`;
            }
        }

        clearHover() {
            if (!this.hoverItem && this.hoverMarker.hidden) return;
            this.hoverItem = null;
            this.hoverObject = null;
            this.hoverCount = 0;
            this.hoverMarker.hidden = true;
            this.draw(false);
        }

        clearInspection() {
            this.selectedItem = null;
            this.selectedObject = null;
            this.selectedCount = 0;
            this.matchedItem = null;
            this.matchedCount = 0;
            this.draw(false);
        }

        setInspectionMatches(selection, matches) {
            this.matchedItem = null;
            this.matchedCount = 0;
            if (!selection?.family || !(matches || []).length) {
                this.draw(false);
                return;
            }

            const matchPrefix = selection.prefix === "reco" ? "truth" : "reco";
            const targetName = `${matchPrefix}_${selection.family}`;
            const matchIds = new Set((matches || []).map(key =>
                Number(String(key).split(":", 2)[1])
            ));
            let matchedItem = null;
            let matchedView = -1;
            this.layers.some((layers, viewIndex) => layers.some(item => {
                if (item.source.metadata.object_name !== targetName ||
                        !item.activeSelectionIds) return false;
                matchedItem = item;
                matchedView = viewIndex;
                return true;
            }));
            if (!matchedItem) {
                this.draw(false);
                return;
            }

            const vertices = [];
            for (let index = 0;
                 index < matchedItem.activeSelectionIds.length;
                 index++) {
                if (matchIds.has(matchedItem.activeSelectionIds[index])) {
                    vertices.push(index);
                }
            }
            const positions = new Float32Array(vertices.length * 3);
            const colors = new Float32Array(vertices.length * 4);
            const halo = new Float32Array(vertices.length * 4);
            vertices.forEach((vertex, index) => {
                positions.set(
                    matchedItem.positions.subarray(vertex * 3, vertex * 3 + 3),
                    index * 3
                );
                colors.set(
                    matchedItem.colors.subarray(vertex * 4, vertex * 4 + 4),
                    index * 4
                );
                halo.set([1.0, 0.49, 0.03, 0.78], index * 4);
            });
            const gl = this.gl;
            gl.bindBuffer(gl.ARRAY_BUFFER, this.matchedPositionBuffer);
            gl.bufferData(gl.ARRAY_BUFFER, positions, gl.DYNAMIC_DRAW);
            gl.bindBuffer(gl.ARRAY_BUFFER, this.matchedColorBuffer);
            gl.bufferData(gl.ARRAY_BUFFER, colors, gl.DYNAMIC_DRAW);
            gl.bindBuffer(gl.ARRAY_BUFFER, this.matchedHaloBuffer);
            gl.bufferData(gl.ARRAY_BUFFER, halo, gl.DYNAMIC_DRAW);
            this.matchedItem = matchedItem;
            this.matchedViewIndex = matchedView;
            this.matchedCount = vertices.length;
            this.draw(false);
        }

        setInspection(best, object) {
            this.selectedItem = best.item;
            this.selectedObject = object;
            this.selectedViewIndex = best.viewIndex;

            const vertices = [];
            if (object != null && best.item.activeSelectionIds) {
                for (let index = 0;
                     index < best.item.activeSelectionIds.length;
                     index++) {
                    if (best.item.activeSelectionIds[index] === object) {
                        vertices.push(index);
                    }
                }
            } else {
                vertices.push(best.vertex);
            }
            const positions = new Float32Array(vertices.length * 3);
            const colors = new Float32Array(vertices.length * 4);
            const halo = new Float32Array(vertices.length * 4);
            vertices.forEach((vertex, index) => {
                positions.set(
                    best.item.positions.subarray(vertex * 3, vertex * 3 + 3),
                    index * 3
                );
                colors.set(
                    best.item.colors.subarray(vertex * 4, vertex * 4 + 4),
                    index * 4
                );
                halo.set([1.0, 0.49, 0.03, 0.92], index * 4);
            });
            const gl = this.gl;
            gl.bindBuffer(gl.ARRAY_BUFFER, this.selectedPositionBuffer);
            gl.bufferData(gl.ARRAY_BUFFER, positions, gl.DYNAMIC_DRAW);
            gl.bindBuffer(gl.ARRAY_BUFFER, this.selectedColorBuffer);
            gl.bufferData(gl.ARRAY_BUFFER, colors, gl.DYNAMIC_DRAW);
            gl.bindBuffer(gl.ARRAY_BUFFER, this.selectedHaloBuffer);
            gl.bufferData(gl.ARRAY_BUFFER, halo, gl.DYNAMIC_DRAW);
            this.selectedCount = vertices.length;
            this.draw(false);
        }

        setHover(best, object) {
            const itemChanged = this.hoverItem !== best.item
                || this.hoverObject !== object;
            this.hoverItem = best.item;
            this.hoverObject = object;
            this.hoverViewIndex = best.viewIndex;

            if (itemChanged) {
                const vertices = [];
                if (object != null && best.item.activeSelectionIds) {
                    for (let index = 0;
                         index < best.item.activeSelectionIds.length;
                         index++) {
                        if (best.item.activeSelectionIds[index] === object) {
                            vertices.push(index);
                        }
                    }
                } else {
                    vertices.push(best.vertex);
                }
                const positions = new Float32Array(vertices.length * 3);
                const colors = new Float32Array(vertices.length * 4);
                const halo = new Float32Array(vertices.length * 4);
                vertices.forEach((vertex, index) => {
                    positions.set(
                        best.item.positions.subarray(vertex * 3, vertex * 3 + 3),
                        index * 3
                    );
                    colors.set(
                        best.item.colors.subarray(vertex * 4, vertex * 4 + 4),
                        index * 4
                    );
                    const sourceColor = best.item.colors.subarray(
                        vertex * 4, vertex * 4 + 4
                    );
                    halo.set([
                        sourceColor[0], sourceColor[1], sourceColor[2], 0.78
                    ], index * 4);
                });
                const gl = this.gl;
                gl.bindBuffer(gl.ARRAY_BUFFER, this.hoverPositionBuffer);
                gl.bufferData(gl.ARRAY_BUFFER, positions, gl.DYNAMIC_DRAW);
                gl.bindBuffer(gl.ARRAY_BUFFER, this.hoverColorBuffer);
                gl.bufferData(gl.ARRAY_BUFFER, colors, gl.DYNAMIC_DRAW);
                gl.bindBuffer(gl.ARRAY_BUFFER, this.hoverHaloBuffer);
                gl.bufferData(gl.ARRAY_BUFFER, halo, gl.DYNAMIC_DRAW);
                this.hoverCount = vertices.length;
            }
            this.positionHoverMarker(best.position, best.viewIndex);
            this.draw(false);
        }

        positionHoverMarker(position, viewIndex) {
            const matrix = this.lastMatrices[viewIndex];
            const x = position[0], y = position[1], z = position[2];
            const clipX = matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12];
            const clipY = matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13];
            const clipW = matrix[3] * x + matrix[7] * y + matrix[11] * z + matrix[15];
            const viewWidth = this.root.clientWidth / this.layers.length;
            this.hoverMarker.style.left = `${viewIndex * viewWidth
                + (clipX / clipW + 1) * viewWidth / 2}px`;
            this.hoverMarker.style.top = `${(1 - clipY / clipW)
                * this.root.clientHeight / 2}px`;
            this.hoverMarker.hidden = false;
        }

        ensurePickTarget() {
            const gl = this.gl;
            if (!this.pickFramebuffer) {
                this.pickFramebuffer = gl.createFramebuffer();
                this.pickTexture = gl.createTexture();
                this.pickDepth = gl.createRenderbuffer();
            }
            if (this.pickWidth === this.canvas.width
                    && this.pickHeight === this.canvas.height) return;

            this.pickWidth = this.canvas.width;
            this.pickHeight = this.canvas.height;
            gl.bindTexture(gl.TEXTURE_2D, this.pickTexture);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
            gl.texImage2D(
                gl.TEXTURE_2D, 0, gl.RGBA, this.pickWidth, this.pickHeight,
                0, gl.RGBA, gl.UNSIGNED_BYTE, null
            );
            gl.bindRenderbuffer(gl.RENDERBUFFER, this.pickDepth);
            gl.renderbufferStorage(
                gl.RENDERBUFFER, gl.DEPTH_COMPONENT16, this.pickWidth, this.pickHeight
            );
            gl.bindFramebuffer(gl.FRAMEBUFFER, this.pickFramebuffer);
            gl.framebufferTexture2D(
                gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D,
                this.pickTexture, 0
            );
            gl.framebufferRenderbuffer(
                gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.RENDERBUFFER,
                this.pickDepth
            );
            if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) {
                throw new Error("WebGL hover framebuffer is incomplete.");
            }
            gl.bindFramebuffer(gl.FRAMEBUFFER, null);
            this.pickDirty = true;
        }

        preparePickBuffers() {
            const gl = this.gl;
            let identifier = 1;
            this.pickRanges = [];
            this.layers.forEach((layers, viewIndex) => {
                layers.forEach(item => {
                    if (item.pickColorBuffer) gl.deleteBuffer(item.pickColorBuffer);
                    item.pickColorBuffer = null;
                    if (item.source.type !== "point"
                            && item.source.type !== "marker"
                            && item.source.type !== "vector") return;

                    // Point primitives need one pick ID per rendered point.
                    // A vector is expanded into many triangles, so give every
                    // vertex of one arrow the same ID. This keeps the encoded
                    // color constant across each triangle and maps the result
                    // back to one source vector.
                    const sourceVertices = [];
                    const sourceIdentifiers = new Map();
                    const pickIdentifiers = new Int32Array(item.count);
                    for (let vertex = 0; vertex < item.count; vertex++) {
                        const sourceIndex = item.activeSourceIndices[vertex];
                        let localIdentifier = sourceIdentifiers.get(sourceIndex);
                        if (localIdentifier == null) {
                            localIdentifier = sourceVertices.length;
                            sourceIdentifiers.set(sourceIndex, localIdentifier);
                            sourceVertices.push(vertex);
                        }
                        pickIdentifiers[vertex] = localIdentifier;
                    }
                    const pickCount = sourceVertices.length;
                    if (identifier + pickCount > 0xffffff) {
                        throw new Error(
                            "WebGL hover supports at most 16,777,214 primitives."
                        );
                    }
                    const colors = new Uint8Array(item.count * 4);
                    for (let vertex = 0; vertex < item.count; vertex++) {
                        const value = identifier + pickIdentifiers[vertex];
                        const offset = vertex * 4;
                        colors[offset] = value & 255;
                        colors[offset + 1] = (value >> 8) & 255;
                        colors[offset + 2] = (value >> 16) & 255;
                        colors[offset + 3] = 255;
                    }
                    item.pickColorBuffer = gl.createBuffer();
                    gl.bindBuffer(gl.ARRAY_BUFFER, item.pickColorBuffer);
                    gl.bufferData(gl.ARRAY_BUFFER, colors, gl.STATIC_DRAW);
                    this.pickRanges.push({
                        start: identifier,
                        end: identifier + pickCount,
                        item,
                        viewIndex,
                        sourceVertices
                    });
                    identifier += pickCount;
                });
            });
            this.pickDataDirty = false;
        }

        renderPickBuffer() {
            const gl = this.gl;
            this.ensurePickTarget();
            if (this.pickDataDirty) this.preparePickBuffers();
            gl.bindFramebuffer(gl.FRAMEBUFFER, this.pickFramebuffer);
            gl.disable(gl.BLEND);
            gl.disable(gl.DITHER);
            gl.enable(gl.DEPTH_TEST);
            gl.depthFunc(gl.LEQUAL);
            gl.disable(gl.SCISSOR_TEST);
            gl.clearColor(0, 0, 0, 0);
            gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
            gl.useProgram(this.program);
            gl.enable(gl.SCISSOR_TEST);
            const count = this.layers.length;
            this.layers.forEach((layers, index) => {
                const viewportWidth = Math.floor(this.canvas.width / count);
                const left = index * viewportWidth;
                const actualWidth = index === count - 1
                    ? this.canvas.width - left
                    : viewportWidth;
                gl.viewport(left, 0, actualWidth, this.canvas.height);
                gl.scissor(left, 0, actualWidth, this.canvas.height);
                gl.clear(gl.DEPTH_BUFFER_BIT);
                layers.forEach(item => {
                    if (!item.pickColorBuffer) return;
                    gl.uniformMatrix4fv(
                        this.mvpLocation, false, this.lastMatrices[index]
                    );
                    const size = Math.max(5, this.pointSize(item))
                        * (window.devicePixelRatio || 1);
                    gl.uniform1f(this.pointSizeLocation, size);
                    if (this.supportsMarkerSymbols) {
                        gl.uniform1i(this.symbolLocation, item.symbol);
                    }
                    gl.bindBuffer(gl.ARRAY_BUFFER, item.positionBuffer);
                    gl.enableVertexAttribArray(this.positionLocation);
                    gl.vertexAttribPointer(
                        this.positionLocation, 3, gl.FLOAT, false, 0, 0
                    );
                    gl.bindBuffer(gl.ARRAY_BUFFER, item.pickColorBuffer);
                    gl.enableVertexAttribArray(this.colorLocation);
                    gl.vertexAttribPointer(
                        this.colorLocation, 4, gl.UNSIGNED_BYTE, true, 0, 0
                    );
                    gl.drawArrays(item.mode, 0, item.count);
                });
            });
            gl.disable(gl.SCISSOR_TEST);
            gl.bindFramebuffer(gl.FRAMEBUFFER, null);
            gl.depthFunc(gl.LESS);
            gl.enable(gl.DITHER);
            gl.enable(gl.BLEND);
            this.pickDirty = false;
        }

        pick(event, inspect = false) {
            if (!this.lastMatrices) return;
            if (this.pickDirty) this.renderPickBuffer();
            const gl = this.gl;
            const bounds = this.canvas.getBoundingClientRect();
            const ratio = window.devicePixelRatio || 1;
            const centerX = Math.floor((event.clientX - bounds.left) * ratio);
            const centerY = Math.floor((bounds.bottom - event.clientY) * ratio);
            const radius = Math.max(4, Math.ceil(7 * ratio));
            const left = Math.max(0, centerX - radius);
            const bottom = Math.max(0, centerY - radius);
            const right = Math.min(this.canvas.width, centerX + radius + 1);
            const top = Math.min(this.canvas.height, centerY + radius + 1);
            const width = right - left;
            const height = top - bottom;
            const pixels = new Uint8Array(width * height * 4);
            gl.bindFramebuffer(gl.FRAMEBUFFER, this.pickFramebuffer);
            gl.readPixels(left, bottom, width, height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
            gl.bindFramebuffer(gl.FRAMEBUFFER, null);

            let identifier = 0;
            let bestDistance = Infinity;
            for (let y = 0; y < height; y++) {
                for (let x = 0; x < width; x++) {
                    const offset = (y * width + x) * 4;
                    const value = pixels[offset]
                        | (pixels[offset + 1] << 8)
                        | (pixels[offset + 2] << 16);
                    if (!value) continue;
                    const distance = Math.hypot(left + x - centerX, bottom + y - centerY);
                    if (distance < bestDistance) {
                        identifier = value;
                        bestDistance = distance;
                    }
                }
            }
            const range = this.pickRanges.find(candidate =>
                identifier >= candidate.start && identifier < candidate.end
            );
            if (!range) {
                this.tooltip.hidden = true;
                this.clearHover();
                if (inspect) {
                    this.clearInspection();
                    window.dash_clientside?.set_props?.(
                        "store-inspected-object", {data: null}
                    );
                }
                return;
            }
            const best = {
                item: range.item,
                vertex: range.sourceVertices[identifier - range.start],
                viewIndex: range.viewIndex
            };
            const offset = best.vertex * 3;
            best.position = Array.from(best.item.positions.subarray(offset, offset + 3));
            const labels = best.item.source.hovertext;
            const object = best.item.activeSelectionIds?.[best.vertex];
            const labelIndex = best.item.source.object_offsets && object != null
                ? object
                : best.item.activeSourceIndices[best.vertex];
            const label = Array.isArray(labels) ? labels[labelIndex] : labels;
            const sourceIndex = best.item.activeSourceIndices[best.vertex];
            const coordinates = best.item.source.type === "vector"
                ? best.item.source.vectors.subarray(
                    sourceIndex * 3, sourceIndex * 3 + 3
                )
                : best.position;
            const coordinateNames = best.item.source.type === "vector"
                ? ["vx", "vy", "vz"]
                : ["x", "y", "z"];
            const coordinateText = Array.from(coordinates).map((value, axis) =>
                `${coordinateNames[axis]}: ${formatPointCoordinate(value)}`
            ).join("\n");
            const fallback = object == null
                ? best.item.source.name || "Point"
                : `${best.item.source.name || "Object"} ${object}`;
            let detail = String(label || fallback)
                .replace(/<br\s*\/?\s*>/gi, "\n")
                .replace(/<[^>]*>/g, "");

            // Hover labels are compacted to one string per object in the
            // binary scene. Replace numeric details with the exact value at
            // the picked source point so long-form attributes remain local.
            const attributeValues = best.item.source.attributes || {};
            const longFormAttributes = new Set(
                best.item.source.metadata.long_form_attributes || []
            );
            const lines = detail.split("\n");
            Object.entries(attributeValues).forEach(([name, values]) => {
                if (!longFormAttributes.has(name)
                        || sourceIndex >= values.length) return;
                const normalizedName = normalizedAttributeName(name);
                const lineIndex = lines.findIndex(line => {
                    const separator = line.indexOf(":");
                    return separator >= 0 && normalizedAttributeName(
                        line.slice(0, separator)
                    ) === normalizedName;
                });
                const label = name.replace(/_/g, " ").replace(/^./, character =>
                    character.toUpperCase()
                );
                const replacement = `${label}: ${values[sourceIndex]}`;
                if (lineIndex >= 0) lines[lineIndex] = replacement;
                else lines.push(replacement);
            });

            // Object-associated raw points are picked through the object layer
            // to preserve whole-instance highlighting. Their deposition is
            // supplied as a hidden point-wise attribute by the server. For an
            // unassociated raw point, read the value directly from the raw
            // layer so both cases expose the same information.
            if (best.item.source.metadata.kind === "raw") {
                const values = best.item.source.values;
                if (values && sourceIndex < values.length) {
                    lines.push(`Deposition: ${values[sourceIndex]}`);
                }
            }
            detail = lines.join("\n");
            if (this.mixedObjectViews[best.viewIndex]) {
                const prefix = best.item.source.metadata.object_name
                    ?.split("_", 1)[0];
                if (prefix === "reco" || prefix === "truth") {
                    const qualifier = prefix === "reco" ? "Reco" : "Truth";
                    const lines = detail.split("\n");
                    if (!lines[0].toLowerCase().startsWith(prefix)) {
                        lines[0] = `${qualifier} ${lines[0]}`;
                    }
                    detail = lines.join("\n");
                }
            }
            this.setHover(best, object);
            this.showHoverMessage(
                coordinateText.split("\n"), detail.split("\n"), best,
                event.clientX, event.clientY
            );
            if (inspect) this.publishInspection(best, object);
        }

        publishInspection(best, object) {
            const objectName = best.item.source.metadata.object_name || "";
            const separator = objectName.indexOf("_");
            const prefix = separator > 0 ? objectName.slice(0, separator) : "";
            const family = separator > 0 ? objectName.slice(separator + 1) : "";
            if (object == null || !["reco", "truth"].includes(prefix) ||
                    !["fragments", "particles", "interactions"].includes(family)) {
                return;
            }
            this.setInspection(best, object);
            window.dash_clientside?.set_props?.("store-inspected-object", {
                data: {
                    key: `${prefix}:${object}`,
                    prefix: prefix,
                    position: Number(object),
                    family: family,
                    renderer: "webgl",
                    view: best.viewIndex,
                    point: Array.from(best.position, Number),
                    revision: Date.now()
                }
            });
        }

        showHoverMessage(coordinates, details, best, x, y) {
            const color = best.item.colors.subarray(
                best.vertex * 4, best.vertex * 4 + 3
            );
            const accent = `rgb(${Array.from(color).map(channel =>
                Math.round(channel * 255)).join(",")})`;
            this.tooltip.style.setProperty("--hover-accent", accent);
            const title = document.createElement("div");
            title.className = "webgl-tooltip-title";
            title.textContent = details.shift() || best.item.source.name || "Point";
            const coordinateGrid = document.createElement("div");
            coordinateGrid.className = "webgl-tooltip-coordinates";
            coordinates.forEach(coordinate => {
                const [name, ...value] = coordinate.split(":");
                const label = document.createElement("span");
                label.textContent = name;
                const number = document.createElement("strong");
                number.textContent = value.join(":").trim();
                coordinateGrid.append(label, number);
            });
            const body = document.createElement("div");
            body.className = "webgl-tooltip-body";
            details.filter(Boolean).forEach(detail => {
                const separator = detail.indexOf(":");
                if (separator < 0) {
                    const line = document.createElement("span");
                    line.className = "webgl-tooltip-detail";
                    line.textContent = detail;
                    body.appendChild(line);
                    return;
                }
                const label = document.createElement("span");
                label.textContent = detail.slice(0, separator);
                const value = document.createElement("strong");
                value.textContent = formatAttributeValue(
                    detail.slice(separator + 1)
                );
                body.append(label, value);
            });
            this.tooltip.replaceChildren(title, coordinateGrid, body);
            this.tooltip.hidden = false;

            const bounds = this.root.getBoundingClientRect();
            let left = x - bounds.left + 14;
            let top = y - bounds.top + 14;
            if (left + this.tooltip.offsetWidth > bounds.width - 8) {
                left = x - bounds.left - this.tooltip.offsetWidth - 14;
            }
            if (top + this.tooltip.offsetHeight > bounds.height - 8) {
                top = y - bounds.top - this.tooltip.offsetHeight - 14;
            }
            this.tooltip.style.left = `${Math.max(8, left)}px`;
            this.tooltip.style.top = `${Math.max(8, top)}px`;
        }

        drawAxes(width, height) {
            const bounds = this.scene.metadata.bounds;
            if (!this.showAxes || !bounds || !this.lastMatrices.length) {
                this.axes.replaceChildren();
                return;
            }

            this.axes.setAttribute("viewBox", `0 0 ${width} ${height}`);
            const fragment = document.createDocumentFragment();
            const viewWidth = width / this.layers.length;
            const low = bounds.map(pair => pair[0]);
            const high = bounds.map(pair => pair[1]);
            const corners = [];
            for (let index = 0; index < 8; index++) {
                corners.push(low.map((value, axis) =>
                    index & (1 << axis) ? high[axis] : value
                ));
            }
            const edges = [
                [0, 1], [0, 2], [0, 4], [1, 3], [1, 5], [2, 3],
                [2, 6], [3, 7], [4, 5], [4, 6], [5, 7], [6, 7]
            ];
            const foreground = this.dark ? "#d5dae3" : "#4b5565";
            const boxColor = this.dark
                ? "rgba(190,200,215,0.28)"
                : "rgba(55,65,80,0.24)";
            const textOutline = this.dark ? "#000" : "#fff";
            const unit = this.scene.metadata.detector_coords ? "cm" : "pixel";

            const project = (point, matrix, left) => {
                const x = point[0], y = point[1], z = point[2];
                const clipX = matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12];
                const clipY = matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13];
                const clipW = matrix[3] * x + matrix[7] * y + matrix[11] * z + matrix[15];
                if (clipW <= 0) return null;
                return [
                    left + (clipX / clipW + 1) * viewWidth / 2,
                    (1 - clipY / clipW) * height / 2
                ];
            };
            const segment = (a, b) => `M${a[0].toFixed(1)},${a[1].toFixed(1)}`
                + `L${b[0].toFixed(1)},${b[1].toFixed(1)}`;

            this.lastMatrices.forEach((matrix, viewIndex) => {
                const left = viewIndex * viewWidth;
                const viewport = svgElement("svg", {
                    x: left,
                    y: 0,
                    width: viewWidth,
                    height,
                    viewBox: `${left} 0 ${viewWidth} ${height}`,
                    overflow: "hidden"
                });
                const projected = corners.map(point => project(point, matrix, left));
                const boxPath = edges.filter(edge =>
                    projected[edge[0]] && projected[edge[1]]
                ).map(edge => segment(projected[edge[0]], projected[edge[1]])).join("");
                viewport.appendChild(svgElement("path", {
                    d: boxPath, class: "webgl-axis-box", stroke: boxColor
                }));

                let axisPath = "";
                let tickPath = "";
                const labels = [];
                for (let axis = 0; axis < 3; axis++) {
                    const end = low.slice();
                    end[axis] = high[axis];
                    const startScreen = project(low, matrix, left);
                    const endScreen = project(end, matrix, left);
                    if (!startScreen || !endScreen) continue;
                    axisPath += segment(startScreen, endScreen);
                    const dx = endScreen[0] - startScreen[0];
                    const dy = endScreen[1] - startScreen[1];
                    const length = Math.hypot(dx, dy) || 1;
                    const offset = [-dy / length, dx / length];
                    const span = high[axis] - low[axis];
                    for (let tick = 0; tick <= 4; tick++) {
                        const fraction = tick / 4;
                        const point = low.slice();
                        point[axis] = low[axis] + span * fraction;
                        const screen = project(point, matrix, left);
                        if (!screen) continue;
                        const a = [screen[0] - offset[0] * 3, screen[1] - offset[1] * 3];
                        const b = [screen[0] + offset[0] * 3, screen[1] + offset[1] * 3];
                        tickPath += segment(a, b);
                        labels.push({
                            x: screen[0] + offset[0] * 9,
                            y: screen[1] + offset[1] * 9,
                            text: formatCoordinate(point[axis], span),
                            title: false
                        });
                    }
                    labels.push({
                        x: endScreen[0] + offset[0] * 20,
                        y: endScreen[1] + offset[1] * 20,
                        text: `${"xyz"[axis]} [${unit}]`,
                        title: true
                    });
                }
                viewport.appendChild(svgElement("path", {
                    d: axisPath, class: "webgl-axis-line", stroke: foreground
                }));
                viewport.appendChild(svgElement("path", {
                    d: tickPath, class: "webgl-axis-tick", stroke: foreground
                }));
                labels.forEach(label => {
                    const text = svgElement("text", {
                        x: label.x.toFixed(1),
                        y: label.y.toFixed(1),
                        class: label.title
                            ? "webgl-axis-label webgl-axis-title"
                            : "webgl-axis-label",
                        fill: foreground,
                        stroke: textOutline,
                        "text-anchor": "middle",
                        "dominant-baseline": "middle"
                    });
                    text.textContent = label.text;
                    viewport.appendChild(text);
                });
                fragment.appendChild(viewport);
            });
            this.axes.replaceChildren(fragment);
        }

        drawLayer(item, mvp) {
            const gl = this.gl;
            gl.uniformMatrix4fv(this.mvpLocation, false, mvp);
            const pixelRatio = window.devicePixelRatio || 1;
            const pointSize = this.pointSize(item);
            gl.uniform1f(this.pointSizeLocation, pointSize * pixelRatio);
            if (this.supportsMarkerSymbols) {
                gl.uniform1i(this.symbolLocation, item.symbol);
            }
            gl.lineWidth(item.source.style?.width || item.source.line_style?.width || 1);
            gl.bindBuffer(gl.ARRAY_BUFFER, item.positionBuffer);
            gl.enableVertexAttribArray(this.positionLocation);
            gl.vertexAttribPointer(this.positionLocation, 3, gl.FLOAT, false, 0, 0);
            gl.bindBuffer(gl.ARRAY_BUFFER, item.colorBuffer);
            gl.enableVertexAttribArray(this.colorLocation);
            gl.vertexAttribPointer(this.colorLocation, 4, gl.FLOAT, false, 0, 0);
            if (item.indices) {
                gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, item.indexBuffer);
                gl.drawElements(item.mode, item.count, gl.UNSIGNED_INT, 0);
            } else {
                gl.drawArrays(item.mode, 0, item.count);
            }
        }

        drawHover(viewIndex, mvp) {
            if (!this.hoverCount || this.hoverViewIndex !== viewIndex) return;
            const gl = this.gl;
            const pixelRatio = window.devicePixelRatio || 1;
            const pointSize = this.pointSize(this.hoverItem);
            gl.uniformMatrix4fv(this.mvpLocation, false, mvp);
            if (this.supportsMarkerSymbols) gl.uniform1i(this.symbolLocation, 1);
            gl.bindBuffer(gl.ARRAY_BUFFER, this.hoverPositionBuffer);
            gl.enableVertexAttribArray(this.positionLocation);
            gl.vertexAttribPointer(this.positionLocation, 3, gl.FLOAT, false, 0, 0);
            gl.depthFunc(gl.LEQUAL);

            // Draw a larger contrast pass, then restore the original point
            // colors in the center to produce an unobtrusive instance outline.
            gl.bindBuffer(gl.ARRAY_BUFFER, this.hoverHaloBuffer);
            gl.enableVertexAttribArray(this.colorLocation);
            gl.vertexAttribPointer(this.colorLocation, 4, gl.FLOAT, false, 0, 0);
            gl.uniform1f(this.pointSizeLocation, (pointSize + 1.5) * pixelRatio);
            gl.drawArrays(gl.POINTS, 0, this.hoverCount);
            gl.bindBuffer(gl.ARRAY_BUFFER, this.hoverColorBuffer);
            gl.vertexAttribPointer(this.colorLocation, 4, gl.FLOAT, false, 0, 0);
            gl.uniform1f(this.pointSizeLocation, (pointSize + 0.5) * pixelRatio);
            gl.drawArrays(gl.POINTS, 0, this.hoverCount);
            gl.depthFunc(gl.LESS);
        }

        drawInspection(viewIndex, mvp) {
            this.drawInspectionBuffer(
                viewIndex, mvp, this.selectedViewIndex, this.selectedItem,
                this.selectedCount, this.selectedPositionBuffer,
                this.selectedColorBuffer, this.selectedHaloBuffer, 2.5
            );
            this.drawInspectionBuffer(
                viewIndex, mvp, this.matchedViewIndex, this.matchedItem,
                this.matchedCount, this.matchedPositionBuffer,
                this.matchedColorBuffer, this.matchedHaloBuffer, 2.0
            );
        }

        drawInspectionBuffer(viewIndex, mvp, targetView, item, count,
                             positionBuffer, colorBuffer, haloBuffer,
                             haloSize) {
            if (!count || targetView !== viewIndex) return;
            const gl = this.gl;
            const pixelRatio = window.devicePixelRatio || 1;
            const pointSize = this.pointSize(item);
            gl.uniformMatrix4fv(this.mvpLocation, false, mvp);
            if (this.supportsMarkerSymbols) gl.uniform1i(this.symbolLocation, 1);
            gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
            gl.enableVertexAttribArray(this.positionLocation);
            gl.vertexAttribPointer(this.positionLocation, 3, gl.FLOAT, false, 0, 0);
            gl.depthFunc(gl.LEQUAL);

            // Keep the object's original colors readable inside a persistent
            // SPINE-orange outline. Hover remains a separate, subtler layer.
            gl.bindBuffer(gl.ARRAY_BUFFER, haloBuffer);
            gl.enableVertexAttribArray(this.colorLocation);
            gl.vertexAttribPointer(this.colorLocation, 4, gl.FLOAT, false, 0, 0);
            gl.uniform1f(this.pointSizeLocation, (pointSize + haloSize) * pixelRatio);
            gl.drawArrays(gl.POINTS, 0, count);
            gl.bindBuffer(gl.ARRAY_BUFFER, colorBuffer);
            gl.vertexAttribPointer(this.colorLocation, 4, gl.FLOAT, false, 0, 0);
            gl.uniform1f(this.pointSizeLocation, (pointSize + 0.5) * pixelRatio);
            gl.drawArrays(gl.POINTS, 0, count);
            gl.depthFunc(gl.LESS);
        }

        pointSize(item) {
            const scale = item.source.type === "point"
                ? (this.appearance.point_size || 1) : 1;
            const size = Math.max(3.5, item.source.style?.size || 3) * scale;

            // SPINE marker sizes follow Plotly's marker scale. Give discrete
            // start/end points and vertices extra screen-space separation in
            // WebGL while leaving the much denser voxel clouds unchanged.
            if (item.source.metadata.kind === "vertex") return 2.25 * size;
            return item.source.type === "marker" ? 1.5 * size : size;
        }

        draw(invalidatePick = true) {
            const gl = this.gl;
            if (invalidatePick) this.pickDirty = true;
            const ratio = window.devicePixelRatio || 1;
            const width = Math.max(1, Math.floor(this.root.clientWidth * ratio));
            const height = Math.max(1, Math.floor(this.root.clientHeight * ratio));
            if (this.canvas.width !== width || this.canvas.height !== height) {
                this.canvas.width = width;
                this.canvas.height = height;
            }
            const background = this.dark ? 0 : 1;
            gl.clearColor(background, background, background, 1);
            gl.enable(gl.DEPTH_TEST);
            gl.enable(gl.BLEND);
            gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
            gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
            gl.useProgram(this.program);
            gl.enable(gl.SCISSOR_TEST);
            const count = this.layers.length;
            this.lastMatrices = [];
            this.layers.forEach((layers, index) => {
                const camera = this.cameras[index];
                const direction = cameraDirection(camera, this.cameraBasis);
                const eye = camera.target.map(
                    (value, axis) => value + camera.distance * direction[axis]
                );
                const view = lookAt(eye, camera.target, this.cameraBasis.up);
                const viewportWidth = Math.floor(width / count);
                const left = index * viewportWidth;
                const actualWidth = index === count - 1 ? width - left : viewportWidth;
                gl.viewport(left, 0, actualWidth, height);
                gl.scissor(left, 0, actualWidth, height);
                gl.clear(gl.DEPTH_BUFFER_BIT);
                const projection = perspective(CAMERA_FOV, actualWidth / height,
                    Math.max(this.radius * 0.001, 0.001), this.radius * 100);
                const mvp = multiply(projection, view);
                this.lastMatrices.push(mvp);
                layers.forEach(layer => this.drawLayer(layer, mvp));
                this.drawInspection(index, mvp);
                this.drawHover(index, mvp);
            });
            gl.disable(gl.SCISSOR_TEST);
            this.drawAxes(this.root.clientWidth, this.root.clientHeight);
        }

        destroy() {
            if (this.pickFrame) cancelAnimationFrame(this.pickFrame);
            this.resizeObserver.disconnect();
            this.gl.deleteBuffer(this.hoverPositionBuffer);
            this.gl.deleteBuffer(this.hoverColorBuffer);
            this.gl.deleteBuffer(this.hoverHaloBuffer);
            this.gl.deleteBuffer(this.selectedPositionBuffer);
            this.gl.deleteBuffer(this.selectedColorBuffer);
            this.gl.deleteBuffer(this.selectedHaloBuffer);
            this.gl.deleteBuffer(this.matchedPositionBuffer);
            this.gl.deleteBuffer(this.matchedColorBuffer);
            this.gl.deleteBuffer(this.matchedHaloBuffer);
            this.layers.flat().forEach(item => {
                if (item.pickColorBuffer) this.gl.deleteBuffer(item.pickColorBuffer);
            });
            if (this.pickFramebuffer) this.gl.deleteFramebuffer(this.pickFramebuffer);
            if (this.pickTexture) this.gl.deleteTexture(this.pickTexture);
            if (this.pickDepth) this.gl.deleteRenderbuffer(this.pickDepth);
            this.gl.getExtension("WEBGL_lose_context")?.loseContext();
            delete this.root._spinalTapViewer;
        }
    }

    const activeViewers = new Set();
    const cameraCache = new Map();
    const sceneLoadReasons = new Set();
    let plotlyFallback = null;
    let plotlyHistogramTimer = null;
    let dashLoadingActive = false;
    let pendingActivityMessage = null;
    let activeActivity = null;

    function statusLog() {
        return document.getElementById("text-info");
    }

    function queueActivity(message) {
        pendingActivityMessage = message;
    }

    function showActivity(message) {
        const log = statusLog();
        if (!log) return;

        if (!activeActivity) {
            activeActivity = {previous: log.value, message: null};
        }
        activeActivity.message = message;
        log.value = message;
    }

    function clearActivity() {
        const log = statusLog();
        if (activeActivity && log?.value === activeActivity.message) {
            log.value = activeActivity.previous;
        }
        activeActivity = null;
    }

    function beginSceneLoad(reason, message = null) {
        sceneLoadReasons.add(reason);
        document.body.classList.add("scene-loading");
        if (message) {
            showActivity(message);
        } else if (reason === "dash" && !activeActivity) {
            showActivity(pendingActivityMessage || "Updating scene…");
            pendingActivityMessage = null;
        }
    }

    function endSceneLoad(reason) {
        sceneLoadReasons.delete(reason);
        if (!sceneLoadReasons.size) {
            document.body.classList.remove("scene-loading");
            clearActivity();
        }
    }

    function sourceActivity() {
        const mode = document.querySelector("#source-mode input:checked")?.value;
        const source = document.getElementById("input-file-path")?.value?.trim();
        if (mode === "url" && source) {
            try {
                const url = new URL(source);
                const name = url.pathname.split("/").filter(Boolean).pop();
                return `Downloading ${name || "file"} from ${url.hostname}…`;
            } catch (_error) {
                return "Downloading URL…";
            }
        }
        if (mode === "upload" || mode === "browse") {
            return "Opening selected file…";
        }
        if (source) {
            const name = source.split(/[\\/]/).filter(Boolean).pop();
            return `Opening ${name || "source"}…`;
        }
        return "Opening source…";
    }

    function rendererActivity() {
        const renderer = document.querySelector(
            "#renderer-toggle input:checked"
        )?.value;
        return `Rendering ${renderer === "plotly" ? "Plotly" : "WebGL"} scene…`;
    }

    function captureActivity(event) {
        const target = event.target instanceof Element ? event.target : null;
        if (!target) return;

        if (target.closest("#button-load")) {
            queueActivity(sourceActivity());
        } else if (target.closest(
            "#button-go, #button-previous, #button-next"
        )) {
            queueActivity("Loading entry…");
        } else if (target.closest("#renderer-toggle")) {
            // A radio's checked state is updated after the click event. Queue
            // this in a microtask so the message names the selected renderer.
            queueMicrotask(() => queueActivity(rendererActivity()));
        } else if (target.closest(
            "#attribute-picker, #radio-run-mode, #radio-truth-point-mode, " +
            "#radio-object-mode, " +
            "#dropdown-geo, #dropdown-geo-tag, #checklist-draw-mode-1, " +
            "#checklist-draw-mode-2, #radio-flash-mode, #radio-crt-mode"
        )) {
            queueActivity("Updating scene…");
        }
    }

    document.addEventListener("click", captureActivity, true);
    document.addEventListener("change", captureActivity, true);

    function afterBrowserPaint(callback) {
        requestAnimationFrame(() => requestAnimationFrame(callback));
    }

    function bindPlotlyCompletion() {
        const plot = document.querySelector("#graph-evd .js-plotly-plot");
        if (!plot || plot._spinalTapLoadingBound) return false;

        const complete = () => {
            plot._spinalTapLoadingBound = false;
            clearTimeout(plotlyFallback);
            plotlyFallback = null;
            afterBrowserPaint(() => endSceneLoad("dash"));
        };
        plot._spinalTapLoadingBound = true;
        if (typeof plot.once === "function") {
            plot.once("plotly_afterplot", complete);
        } else {
            plot.addEventListener("plotly_afterplot", complete, {once: true});
        }
        return true;
    }

    function scanDashLoading() {
        const viewer = document.getElementById("div-evd");
        const loading = viewer?.getAttribute("data-dash-is-loading") === "true";
        if (loading) {
            if (!dashLoadingActive) {
                dashLoadingActive = true;
            }
            clearTimeout(plotlyFallback);
            plotlyFallback = null;
            beginSceneLoad("dash");
            bindPlotlyCompletion();
            return;
        }

        if (!dashLoadingActive) return;
        dashLoadingActive = false;

        if (sceneLoadReasons.has("dash")) {
            // Once Dash has installed a WebGL root, its own loading reason
            // covers the binary fetch and GPU initialization. Do not retain
            // Plotly's render fallback on this fast path.
            if (document.querySelector(".webgl-viewer[data-scene-url]")) {
                clearTimeout(plotlyFallback);
                plotlyFallback = null;
                endSceneLoad("dash");
                return;
            }

            // Plotly finishes its JavaScript work after Dash has delivered the
            // callback response. Keep the overlay through `plotly_afterplot`
            // and two animation frames so the browser has painted the canvas.
            bindPlotlyCompletion();
            if (!plotlyFallback) {
                plotlyFallback = setTimeout(() => {
                    plotlyFallback = null;
                    endSceneLoad("dash");
                }, 1500);
            }
        }
    }

    function rememberCamera(viewer) {
        const key = viewer.root.dataset.cameraKey;
        if (!key) return;
        cameraCache.delete(key);
        cameraCache.set(key, viewer.cameraState());
        if (cameraCache.size > 16) {
            cameraCache.delete(cameraCache.keys().next().value);
        }
    }

    async function initialize(root) {
        const sceneUrl = root.dataset.sceneUrl;
        if (!sceneUrl) return;

        // Dash may reconcile a new event into the existing viewer element and
        // update only its data attributes. Treat a changed scene URL exactly
        // like a replacement node; otherwise the old GPU buffers remain on
        // screen until some later callback happens to replace the element.
        if (root._spinalTapViewer) {
            if (root._spinalTapSceneUrl === sceneUrl) return;
            activeViewers.delete(root._spinalTapViewer);
            root._spinalTapViewer.destroy();
        }
        if (root._spinalTapLoadingUrl === sceneUrl) return;

        const generation = (root._spinalTapLoadGeneration || 0) + 1;
        const loadingReason = `webgl:${generation}`;
        root._spinalTapLoadGeneration = generation;
        root._spinalTapLoadingUrl = sceneUrl;
        beginSceneLoad(loadingReason, "Loading WebGL scene…");
        try {
            const response = await fetch(sceneUrl);
            if (!response.ok) throw new Error(`Scene request failed (${response.status})`);
            const size = Number(response.headers.get("Content-Length"));
            if (Number.isFinite(size) && size > 0) {
                const megabytes = size / (1024 * 1024);
                showActivity(`Loading WebGL scene (${megabytes.toFixed(1)} MB)…`);
            }
            const buffer = await response.arrayBuffer();
            if (!root.isConnected || root.dataset.sceneUrl !== sceneUrl ||
                    root._spinalTapLoadGeneration !== generation) {
                return;
            }
            const scene = parseScene(buffer);
            root._spinalTapViewer = new Viewer(root, scene);
            root._spinalTapSceneUrl = sceneUrl;
            root._spinalTapViewer.restoreCamera(
                cameraCache.get(root.dataset.cameraKey)
            );
            activeViewers.add(root._spinalTapViewer);
        } catch (error) {
            // Replace the shared loading overlay with a persistent error panel
            // so initialization failures never leave an unexplained blank canvas.
            const status = document.createElement("div");
            status.textContent = `WebGL initialization failed: ${error.message}`;
            status.className = "webgl-viewer-status has-error";
            root.replaceChildren(status);
            console.error(error);
        } finally {
            endSceneLoad(loadingReason);
            if (root._spinalTapLoadGeneration === generation) {
                delete root._spinalTapLoadingUrl;
            }
        }
    }

    function scan() {
        const roots = Array.from(
            document.querySelectorAll(".webgl-viewer[data-scene-url]")
        );
        const replacementKeys = new Set(
            roots.map(root => root.dataset.cameraKey).filter(Boolean)
        );
        activeViewers.forEach(viewer => {
            if (!viewer.root.isConnected) {
                const key = viewer.root.dataset.cameraKey;
                if (key && replacementKeys.has(key)) {
                    // Preserve the view only when a display-option refresh is
                    // replacing this exact event in place. Navigating away
                    // deliberately discards its historical camera.
                    rememberCamera(viewer);
                } else {
                    if (key) cameraCache.delete(key);
                    replacementKeys.forEach(
                        replacementKey => cameraCache.delete(replacementKey)
                    );
                }
                viewer.destroy();
                activeViewers.delete(viewer);
            }
        });
        roots.forEach(initialize);
    }

    function drawPlotlyHistogram() {
        plotlyHistogramTimer = null;
        const picker = document.getElementById("appearance-picker");
        const plot = document.querySelector("#graph-evd .js-plotly-plot");
        const canvas = document.getElementById("appearance-histogram");
        if (!picker?.open || !plot?.data || !canvas
                || document.querySelector(".webgl-viewer")) return;
        if (canvas._appearanceHistogram?.start != null) return;

        const appearance = {
            transform: appearanceControlValue(
                "radio-color-transform", "linear"
            ),
            range_mode: appearanceControlValue(
                "radio-visible-range", "all"
            ),
            visible_min: appearanceControlValue("input-visible-min", null),
            visible_max: appearanceControlValue("input-visible-max", null)
        };
        const histogram = plot.layout?.meta?.appearance_histogram
            || plot._fullLayout?.meta?.appearance_histogram;
        if (histogram) {
            renderAppearanceHistogramData(canvas, histogram, appearance);
            return;
        }

        const values = [];
        plot.data.forEach(trace => {
            const color = trace.marker?.color;
            if (!trace.marker?.colorscale || !color
                    || typeof color === "string"
                    || typeof color[Symbol.iterator] !== "function") {
                return;
            }
            for (const value of color) {
                if (Number.isFinite(value)) values.push(value);
            }
        });
        renderAppearanceHistogram(canvas, values, appearance);
    }

    function refreshAppearanceHistogram() {
        const viewer = activeViewers.values().next().value;
        if (viewer) {
            clearTimeout(plotlyHistogramTimer);
            plotlyHistogramTimer = null;
            viewer.drawHistogram();
            return;
        }
        if (!document.getElementById("appearance-picker")?.open) return;

        // Plotly mutates its DOM many times while constructing a figure. Wait
        // until that burst settles, then walk the marker values once. Running
        // this O(points) scan from the general mutation observer made large
        // Plotly scenes appear to hang.
        clearTimeout(plotlyHistogramTimer);
        plotlyHistogramTimer = setTimeout(drawPlotlyHistogram, 100);
    }

    function scanAll() {
        scan();
        scanDashLoading();
        if (!document.querySelector(".webgl-viewer")) {
            refreshAppearanceHistogram();
        }
    }

    window.spinalTapWebgl = {
        applyAppearance(settings) {
            activeViewers.forEach(viewer => viewer.setAppearance(settings));
        },
        refreshAppearanceHistogram
    };

    new MutationObserver(scanAll).observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["data-scene-url", "data-dash-is-loading"],
        childList: true,
        subtree: true
    });
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", scanAll);
    } else {
        scanAll();
    }
})();
