/**
 * Client-side gate for gallery / community media uploads.
 *
 * - Rejects files over the server limit before a long mobile POST starts
 * - Shows a clear error instead of hanging silently
 * - Puts the form into a busy "Uploading…" state (and blocks double-submit)
 *
 * Opt-in: add data-media-upload-guard to a multipart form. Optional:
 *   data-media-max-bytes — override (default 100 MB)
 *   data-media-error-target — CSS selector for the error container
 *   data-media-status-target — CSS selector for the uploading status region
 */
(() => {
    const DEFAULT_MAX_BYTES = 104_857_600; // 100 MB — keep in sync with gallery.validators
    const FILE_TOO_LARGE_MESSAGE =
        "File exceeds the 100MB limit. Please compress the video or "
        + "reduce its quality before uploading.";
    const MIXED_TOO_LARGE_MESSAGE =
        "One or more files exceed the 100MB limit and were removed. "
        + "Please compress large videos before uploading.";
    const TOTAL_TOO_LARGE_MESSAGE =
        "The selected files together exceed the 100MB upload limit. "
        + "Please upload fewer files, or compress large videos first.";
    const UPLOADING_LABEL = "Uploading…";
    const UPLOADING_HINT =
        "Upload in progress. Please keep this page open — large videos "
        + "can take a few minutes on mobile data.";

    const formatFileSize = (bytes) => {
        if (bytes >= 1048576) {
            return `${(bytes / 1048576).toFixed(1)} MB`;
        }
        if (bytes >= 1024) {
            return `${Math.round(bytes / 1024)} KB`;
        }
        return `${bytes} B`;
    };

    const parseMaxBytes = (form) => {
        const raw = form.getAttribute("data-media-max-bytes");
        if (!raw) {
            return DEFAULT_MAX_BYTES;
        }
        const parsed = Number.parseInt(raw, 10);
        return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_MAX_BYTES;
    };

    const resolveTarget = (form, attrName) => {
        const selector = form.getAttribute(attrName);
        if (!selector) {
            return null;
        }
        return form.querySelector(selector) || document.querySelector(selector);
    };

    const fileInputsInForm = (form) =>
        Array.from(form.querySelectorAll('input[type="file"]'));

    const collectOversized = (inputs, maxBytes) => {
        const oversized = [];
        inputs.forEach((input) => {
            Array.from(input.files || []).forEach((file) => {
                if (file.size > maxBytes) {
                    oversized.push(file);
                }
            });
        });
        return oversized;
    };

    const totalSelectedBytes = (inputs) => {
        let total = 0;
        inputs.forEach((input) => {
            Array.from(input.files || []).forEach((file) => {
                total += file.size || 0;
            });
        });
        return total;
    };

    /**
     * Remove oversized files from an input via DataTransfer when available.
     * Returns the list of removed files.
     */
    const stripOversizedFromInput = (input, maxBytes) => {
        const files = Array.from(input.files || []);
        const kept = files.filter((file) => file.size <= maxBytes);
        const removed = files.filter((file) => file.size > maxBytes);

        if (!removed.length) {
            return [];
        }

        if (typeof DataTransfer === "undefined") {
            // Older browsers: clear the whole selection so submit cannot proceed
            // with an oversized file that we cannot filter selectively.
            input.value = "";
            return removed;
        }

        const transfer = new DataTransfer();
        kept.forEach((file) => transfer.items.add(file));
        input.files = transfer.files;
        return removed;
    };

    const showError = (errorEl, message) => {
        if (!errorEl) {
            window.alert(message);
            return;
        }
        errorEl.hidden = false;
        errorEl.textContent = message;
        errorEl.setAttribute("role", "alert");
    };

    const clearError = (errorEl) => {
        if (!errorEl) {
            return;
        }
        errorEl.hidden = true;
        errorEl.textContent = "";
        errorEl.removeAttribute("role");
    };

    const setUploadingState = (form, statusEl, isUploading) => {
        form.classList.toggle("is-media-uploading", isUploading);
        form.setAttribute("aria-busy", isUploading ? "true" : "false");

        const submitButtons = form.querySelectorAll(
            'button[type="submit"], input[type="submit"]'
        );
        submitButtons.forEach((button) => {
            if (isUploading) {
                if (!button.dataset.mediaOriginalLabel) {
                    button.dataset.mediaOriginalLabel =
                        button.tagName === "INPUT"
                            ? button.value
                            : button.textContent.trim();
                }
                button.disabled = true;
                if (button.tagName === "INPUT") {
                    button.value = UPLOADING_LABEL;
                } else {
                    button.textContent = UPLOADING_LABEL;
                }
            } else {
                button.disabled = false;
                const original = button.dataset.mediaOriginalLabel;
                if (original) {
                    if (button.tagName === "INPUT") {
                        button.value = original;
                    } else {
                        button.textContent = original;
                    }
                }
            }
        });

        fileInputsInForm(form).forEach((input) => {
            // Do not set input.disabled — disabled fields are omitted from
            // the multipart body and the upload would silently send no files.
            input.setAttribute("aria-busy", isUploading ? "true" : "false");
            input.classList.toggle("is-media-upload-locked", isUploading);
        });

        if (!statusEl) {
            return;
        }
        if (isUploading) {
            statusEl.hidden = false;
            statusEl.textContent = UPLOADING_HINT;
        } else {
            statusEl.hidden = true;
            statusEl.textContent = "";
        }
    };

    const notifyFiltered = (form, detail) => {
        form.dispatchEvent(
            new CustomEvent("mediaupload:filtered", {
                bubbles: true,
                detail,
            })
        );
    };

    const validateAndStrip = (form, maxBytes, errorEl) => {
        const inputs = fileInputsInForm(form);
        let removed = [];
        inputs.forEach((input) => {
            removed = removed.concat(stripOversizedFromInput(input, maxBytes));
        });

        if (removed.length) {
            const names = removed
                .map((file) => `${file.name} (${formatFileSize(file.size)})`)
                .join(", ");
            const message =
                removed.length === 1
                    ? `${FILE_TOO_LARGE_MESSAGE} Removed: ${names}.`
                    : `${MIXED_TOO_LARGE_MESSAGE} Removed: ${names}.`;
            showError(errorEl, message);
            notifyFiltered(form, { removed, maxBytes });
            return false;
        }

        const totalBytes = totalSelectedBytes(inputs);
        if (totalBytes > maxBytes) {
            showError(
                errorEl,
                `${TOTAL_TOO_LARGE_MESSAGE} Selected total: ${formatFileSize(totalBytes)}.`
            );
            notifyFiltered(form, { removed: [], maxBytes, totalTooLarge: true });
            return false;
        }

        clearError(errorEl);
        return true;
    };

    const attachGuard = (form) => {
        if (form.dataset.mediaUploadGuardBound === "1") {
            return;
        }
        form.dataset.mediaUploadGuardBound = "1";

        const maxBytes = parseMaxBytes(form);
        const errorEl = resolveTarget(form, "data-media-error-target");
        const statusEl = resolveTarget(form, "data-media-status-target");
        let isSubmitting = false;

        fileInputsInForm(form).forEach((input) => {
            input.addEventListener("change", () => {
                validateAndStrip(form, maxBytes, errorEl);
            });
        });

        form.addEventListener("submit", (event) => {
            if (isSubmitting) {
                event.preventDefault();
                return;
            }

            // Re-check in case DataTransfer stripping was unavailable earlier,
            // or the combined selection still exceeds the request-body cap.
            const inputs = fileInputsInForm(form);
            const stillOversized = collectOversized(inputs, maxBytes);
            const totalBytes = totalSelectedBytes(inputs);
            if (stillOversized.length || totalBytes > maxBytes) {
                event.preventDefault();
                validateAndStrip(form, maxBytes, errorEl);
                return;
            }

            isSubmitting = true;
            setUploadingState(form, statusEl, true);
        });
    };

    const init = () => {
        document
            .querySelectorAll("form[data-media-upload-guard]")
            .forEach(attachGuard);
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }

    // Expose for gallery preview JS (format helpers / max size).
    window.JamMediaUploadGuard = {
        DEFAULT_MAX_BYTES,
        formatFileSize,
        FILE_TOO_LARGE_MESSAGE,
    };
})();
