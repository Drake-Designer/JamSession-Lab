document.addEventListener("DOMContentLoaded", () => {
    AOS.init({
        duration: 700,
        easing: "ease-out-cubic",
        once: true,
        offset: 80,
        disable: () => window.matchMedia("(max-width: 767px)").matches,
    });
});
