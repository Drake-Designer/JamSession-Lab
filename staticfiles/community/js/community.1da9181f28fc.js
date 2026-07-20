/**
 * Community page scripts.
 *
 * Destructive-action confirmation is handled site-wide by
 * pages/js/confirm-modal.js (forms with class js-confirm-delete).
 *
 * Members sidebar accordion: closed by default on mobile/tablet.
 * Desktop CSS always shows the panel regardless of this state.
 */
document.addEventListener("alpine:init", () => {
    Alpine.data("membersSidebar", () => ({
        open: false,
        toggle() {
            this.open = !this.open;
        },
    }));
});
