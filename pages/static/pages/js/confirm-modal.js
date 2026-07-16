/**
 * Site-wide confirmation modal (Alpine.js store).
 *
 * Usage: mark a form with class "js-confirm-delete" and optional
 * data-confirm-message / data-confirm-label / data-cancel-label.
 * On submit the native browser confirm() is never used — the shared
 * modal asks first, then submits the form only if the user confirms.
 * Server-side permission checks are unchanged.
 */
document.addEventListener("alpine:init", () => {
    Alpine.store("confirmModal", {
        open: false,
        message: "",
        confirmLabel: "Confirm",
        cancelLabel: "Cancel",
        _form: null,

        ask({ message, confirmLabel, cancelLabel, form } = {}) {
            this.message = message || "Are you sure?";
            this.confirmLabel = confirmLabel || "Confirm";
            this.cancelLabel = cancelLabel || "Cancel";
            this._form = form || null;
            this.open = true;
        },

        confirm() {
            const form = this._form;
            this.open = false;
            this._form = null;
            if (form) {
                // Native submit() does not re-fire the "submit" listener,
                // so the modal is not shown again in a loop.
                HTMLFormElement.prototype.submit.call(form);
            }
        },

        cancel() {
            this.open = false;
            this._form = null;
        },
    });
});

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("form.js-confirm-delete").forEach((form) => {
        form.addEventListener("submit", (event) => {
            event.preventDefault();

            if (typeof Alpine === "undefined" || !Alpine.store("confirmModal")) {
                return;
            }

            Alpine.store("confirmModal").ask({
                message: form.dataset.confirmMessage || "Are you sure?",
                confirmLabel: form.dataset.confirmLabel || "Confirm",
                cancelLabel: form.dataset.cancelLabel || "Cancel",
                form,
            });
        });
    });
});
