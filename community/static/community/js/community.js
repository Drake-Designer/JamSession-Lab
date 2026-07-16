document.addEventListener("DOMContentLoaded", () => {
    const deleteForms = document.querySelectorAll(".js-confirm-delete");

    deleteForms.forEach((form) => {
        form.addEventListener("submit", (event) => {
            const message = form.dataset.confirmMessage || "Are you sure?";
            if (!window.confirm(message)) {
                event.preventDefault();
            }
        });
    });
});
