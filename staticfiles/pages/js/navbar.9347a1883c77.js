document.addEventListener("alpine:init", () => {
    Alpine.data("navbar", () => ({
        mobileOpen: false,
        scrolled: false,

        get headerClass() {
            return this.scrolled
                ? "border-b border-jam-grey-light/80 bg-jam-black/85 shadow-lg shadow-black/40 backdrop-blur-md"
                : "border-b border-transparent bg-jam-black/60 backdrop-blur-sm";
        },

        init() {
            // Toggle dark glass/blur styling once the user scrolls past the hero
            const onScroll = () => {
                this.scrolled = window.scrollY > 20;
            };
            onScroll();
            window.addEventListener("scroll", onScroll, { passive: true });
        },

        toggleMobile() {
            this.mobileOpen = !this.mobileOpen;
        },

        closeMobile() {
            this.mobileOpen = false;
        },
    }));
});
