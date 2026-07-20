/*
 * Immediate profile-picture upload / remove on Edit Profile
 * (no Save Changes needed).
 *
 * Upload flow: Choose/Change photo → crop picker → Use this photo → upload
 * (replaces the file on Cloudinary). Focus can only be set at upload time.
 */
(function () {
    "use strict";

    function getCsrfToken() {
        const input = document.querySelector(
            'form.jam-form input[name="csrfmiddlewaretoken"]'
        );
        return input ? input.value : "";
    }

    function setBusy(widget, isBusy) {
        const changeLabel = widget.querySelector(".profile-picture-widget__change");
        const removeBtn = widget.querySelector("[data-profile-picture-remove]");
        const fileInput = widget.querySelector("[data-profile-picture-input]");
        const confirmBtn = widget.querySelector("[data-profile-picture-confirm]");
        const cancelBtn = widget.querySelector("[data-profile-picture-cancel]");

        if (changeLabel) {
            changeLabel.classList.toggle("is-busy", isBusy);
            if (isBusy) {
                changeLabel.setAttribute("aria-busy", "true");
            } else {
                changeLabel.removeAttribute("aria-busy");
            }
        }
        if (removeBtn) {
            removeBtn.disabled = isBusy;
        }
        if (fileInput) {
            fileInput.disabled = isBusy;
        }
        if (confirmBtn) {
            confirmBtn.disabled = isBusy;
            confirmBtn.classList.toggle("is-busy", isBusy);
        }
        if (cancelBtn) {
            cancelBtn.disabled = isBusy;
        }
    }

    function readFocus(widget) {
        const xInput = widget.querySelector("[data-profile-picture-focus-x]");
        const yInput = widget.querySelector("[data-profile-picture-focus-y]");
        const parse = (input, fallback) => {
            if (!input) {
                return fallback;
            }
            const value = parseFloat(input.value);
            if (Number.isNaN(value)) {
                return fallback;
            }
            return Math.min(100, Math.max(0, value));
        };
        return {
            x: parse(xInput, 50),
            y: parse(yInput, 50),
        };
    }

    function resetFocus(widget) {
        const xInput = widget.querySelector("[data-profile-picture-focus-x]");
        const yInput = widget.querySelector("[data-profile-picture-focus-y]");
        if (xInput) {
            xInput.value = "50";
        }
        if (yInput) {
            yInput.value = "50";
        }
    }

    function hidePicker(widget) {
        const picker = widget.querySelector("#cover-focus-picker");
        if (picker) {
            picker.hidden = true;
        }
    }

    function bindRemove(widget) {
        const button = widget.querySelector("[data-profile-picture-remove]");
        const removeUrl = widget.getAttribute("data-immediate-remove-url");
        if (!button || !removeUrl) {
            return;
        }

        button.addEventListener("click", function () {
            if (button.disabled) {
                return;
            }
            setBusy(widget, true);

            fetch(removeUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCsrfToken(),
                    Accept: "application/json",
                },
                credentials: "same-origin",
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("Remove failed");
                    }
                    return response.json();
                })
                .then(function () {
                    window.location.reload();
                })
                .catch(function () {
                    setBusy(widget, false);
                    window.alert(
                        "We couldn't remove your photo. Please try again."
                    );
                });
        });
    }

    function bindUpload(widget) {
        const uploadUrl = widget.getAttribute("data-immediate-upload-url");
        const fileInput = widget.querySelector("[data-profile-picture-input]");
        const confirmBtn = widget.querySelector("[data-profile-picture-confirm]");
        const cancelBtn = widget.querySelector("[data-profile-picture-cancel]");
        if (!uploadUrl || !fileInput || !confirmBtn) {
            return;
        }

        // cover-focus.js opens the picker on file change; we only upload
        // after the user confirms the crop.
        fileInput.addEventListener("change", function () {
            if (!fileInput.files || fileInput.files.length === 0) {
                hidePicker(widget);
                return;
            }
            resetFocus(widget);
        });

        if (cancelBtn) {
            cancelBtn.addEventListener("click", function () {
                if (cancelBtn.disabled) {
                    return;
                }
                fileInput.value = "";
                hidePicker(widget);
                resetFocus(widget);
            });
        }

        confirmBtn.addEventListener("click", function () {
            if (confirmBtn.disabled) {
                return;
            }
            if (!fileInput.files || fileInput.files.length === 0) {
                window.alert("Please choose a photo first.");
                return;
            }

            const crop = widget.querySelector("#cover-focus-crop");
            if (!crop || !crop.classList.contains("is-ready")) {
                window.alert(
                    "Wait for the crop preview to load, or choose a JPG/PNG photo."
                );
                return;
            }

            const file = fileInput.files[0];
            const focus = readFocus(widget);
            const formData = new FormData();
            formData.append("profile_picture", file);
            formData.append("profile_picture_focus_x", String(focus.x));
            formData.append("profile_picture_focus_y", String(focus.y));

            setBusy(widget, true);

            fetch(uploadUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCsrfToken(),
                    Accept: "application/json",
                },
                body: formData,
                credentials: "same-origin",
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        return { ok: response.ok, data: data };
                    });
                })
                .then(function (result) {
                    if (!result.ok || !result.data.ok) {
                        const message =
                            (result.data && result.data.error) ||
                            "We couldn't upload that photo. Please try again.";
                        throw new Error(message);
                    }
                    window.location.reload();
                })
                .catch(function (error) {
                    setBusy(widget, false);
                    window.alert(
                        error.message ||
                            "We couldn't upload that photo. Please try again."
                    );
                });
        });
    }

    function init() {
        const widget = document.querySelector(
            ".profile-picture-widget[data-immediate-upload-url], .profile-picture-widget[data-immediate-remove-url]"
        );
        if (!widget) {
            return;
        }

        bindUpload(widget);
        bindRemove(widget);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
