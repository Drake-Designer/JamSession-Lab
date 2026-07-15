document.addEventListener("DOMContentLoaded", () => {
    const carousel = document.querySelector(".jam-carousel");

    if (!carousel || typeof Swiper === "undefined") {
        return;
    }

    const slideCount = carousel.querySelectorAll(".swiper-slide").length;
    const enableLoop = slideCount > 1;

    new Swiper(carousel, {
        loop: enableLoop,
        speed: 500,
        grabCursor: true,
        autoplay: enableLoop
            ? {
                  delay: 4500,
                  disableOnInteraction: false,
                  pauseOnMouseEnter: true,
              }
            : false,
        pagination: {
            el: carousel.querySelector(".swiper-pagination"),
            clickable: true,
            dynamicBullets: slideCount > 5,
        },
        navigation: {
            nextEl: carousel.querySelector(".swiper-button-next"),
            prevEl: carousel.querySelector(".swiper-button-prev"),
        },
        slidesPerView: 1,
        spaceBetween: 0,
        watchOverflow: true,
        a11y: {
            enabled: true,
        },
    });
});
