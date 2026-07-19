/*
 * Immediate profile-picture upload / remove on Edit Profile
 * (no Save Changes needed). Upload reloads the page to show the new photo.
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
        if (!uploadUrl || !fileInput) {
            return;
        }

        fileInput.addEventListener("change", function () {
            if (!fileInput.files || fileInput.files.length === 0) {
                return;
            }

            const file = fileInput.files[0];
            const formData = new FormData();
            formData.append("profile_picture", file);

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
                    fileInput.value = "";
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
