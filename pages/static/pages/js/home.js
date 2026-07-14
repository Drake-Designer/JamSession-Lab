document.addEventListener("DOMContentLoaded", () => {
    const carousel = document.querySelector(".jam-carousel");

    if (!carousel || typeof Swiper === "undefined") {
        return;
    }

    new Swiper(carousel, {
        loop: true,
        autoplay: {
            delay: 4500,
            disableOnInteraction: false,
        },
        pagination: {
            el: carousel.querySelector(".swiper-pagination"),
            clickable: true,
        },
        navigation: {
            nextEl: carousel.querySelector(".swiper-button-next"),
            prevEl: carousel.querySelector(".swiper-button-prev"),
        },
        slidesPerView: 1,
        spaceBetween: 0,
    });
});
