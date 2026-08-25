(function () {
    "use strict";

    const setProps = function (id, props) {
        if (window.dash_clientside?.set_props) {
            window.dash_clientside.set_props(id, props);
        }
    };

    const sourceState = window.spinalTapSourceState || {
        active: null,
        values: {}
    };
    window.spinalTapSourceState = sourceState;

    const responseJson = async function (response) {
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload.error || `Request failed (${response.status})`);
        }
        return payload;
    };

    const uploadFile = async function (file, status, progress) {
        const selectedMode = (
            document.querySelector("#source-mode input:checked")?.value ||
            sourceState.active || "browse"
        );
        status.textContent = `Preparing ${file.name}…`;
        progress.value = 0;
        progress.classList.add("is-active");
        const initialized = await responseJson(await fetch("/api/uploads", {
            method: "POST",
            credentials: "same-origin",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({name: file.name, size: file.size})
        }));
        const headers = {"X-Upload-Token": initialized.upload_token};

        try {
            for (let index = 0; index < initialized.chunk_count; index += 1) {
                const start = index * initialized.chunk_size;
                const chunk = file.slice(start, start + initialized.chunk_size);
                let response;
                for (let attempt = 0; attempt < 3; attempt += 1) {
                    response = await fetch(
                        `/api/uploads/${initialized.upload_id}/${index}`,
                        {
                            method: "PUT",
                            credentials: "same-origin",
                            headers,
                            body: chunk
                        }
                    );
                    if (response.ok) break;
                    if (attempt === 2) await responseJson(response);
                }
                progress.value = Math.round(
                    100 * (index + 1) / initialized.chunk_count
                );
                status.textContent = (
                    `Uploading ${file.name} · ${progress.value}%`
                );
            }

            const completed = await responseJson(await fetch(
                `/api/uploads/${initialized.upload_id}/complete`,
                {method: "POST", credentials: "same-origin", headers}
            ));
            setProps("input-file-path", {value: completed.path});
            sourceState.values[selectedMode] = completed.path;
            sourceState.active = selectedMode;
            status.textContent = `${completed.name} · opening…`;
            setProps("store-source-request", {
                data: {
                    file_path: completed.path,
                    source_mode: selectedMode,
                    revision: Date.now()
                }
            });
            status.textContent = completed.name;
        } catch (error) {
            fetch(`/api/uploads/${initialized.upload_id}`, {
                method: "DELETE", credentials: "same-origin", headers
            }).catch(() => undefined);
            throw error;
        }
    };

    const bindSourceModes = function () {
        const control = document.getElementById("source-mode");
        const path = document.getElementById("input-file-path");
        if (!control || !path || control.dataset.bound === "true") return;
        control.dataset.bound = "true";
        sourceState.active = (
            control.querySelector("input:checked")?.value ||
            sourceState.active || "path"
        );
        control.addEventListener("change", function (event) {
            const next = event.target?.value;
            if (!next || next === sourceState.active) return;
            sourceState.values[sourceState.active] = path.value || "";
            sourceState.active = next;
            setProps("input-file-path", {
                value: sourceState.values[next] || ""
            });
        });
    };

    const bindUpload = function () {
        const input = document.getElementById("upload-source-file");
        const status = document.getElementById("upload-source-status");
        const progress = document.getElementById("upload-source-progress");
        if (!input || !status || !progress || input.dataset.bound === "true") return;
        input.dataset.bound = "true";
        input.addEventListener("change", async function () {
            const file = input.files && input.files[0];
            if (!file) return;
            input.disabled = true;
            try {
                await uploadFile(file, status, progress);
            } catch (error) {
                status.textContent = `Upload failed: ${error.message || error}`;
                progress.value = 0;
            } finally {
                progress.classList.remove("is-active");
                input.disabled = false;
                input.value = "";
            }
        });
    };

    const bindEventInputs = function () {
        const fields = document.querySelector(".event-fields");
        if (!fields || fields.dataset.focusBound === "true") return;
        fields.dataset.focusBound = "true";
        fields.addEventListener("click", function (event) {
            if (event.target.closest("input")) return;
            const input = Array.from(fields.querySelectorAll("input")).find(
                candidate => !candidate.disabled && candidate.offsetParent !== null
            );
            if (input) input.focus();
        });
    };

    const bind = function () {
        bindSourceModes();
        bindUpload();
        bindEventInputs();
    };

    document.addEventListener("DOMContentLoaded", bind);
    new MutationObserver(bind).observe(document.documentElement, {
        childList: true,
        subtree: true
    });
}());
