/**
 * Community page scripts.
 *
 * Destructive-action confirmation is handled site-wide by
 * pages/js/confirm-modal.js (forms with class js-confirm-delete).
 *
 * Members sidebar accordion (mobile) is registered as an Alpine component.
 */
document.addEventListener("alpine:init", () => {
    Alpine.data("membersSidebar", () => ({
        open: false,
        toggle() {
            this.open = !this.open;
        },
    }));
});
