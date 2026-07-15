document.addEventListener("DOMContentLoaded", () => {
    const lightbox = document.getElementById("gallery-lightbox");

    if (!lightbox) {
        return;
    }

    const imageEl = lightbox.querySelector(".gallery-lightbox__image");
    const videoEl = lightbox.querySelector(".gallery-lightbox__video");
    const titleEl = lightbox.querySelector(".gallery-lightbox__title");
    const captionEl = lightbox.querySelector(".gallery-lightbox__caption");
    const creditEl = lightbox.querySelector(".gallery-lightbox__credit");
    const closeBtn = lightbox.querySelector(".gallery-lightbox__close");
    const prevBtn = lightbox.querySelector(".gallery-lightbox__nav--prev");
    const nextBtn = lightbox.querySelector(".gallery-lightbox__nav--next");

    const groups = {
        photos: [],
        videos: [],
    };

    const prefetchedSources = new Set();
    const prefetchedVideos = new Map();
    let activeGroup = null;
    let activeIndex = 0;
    let touchStartX = 0;
    let renderToken = 0;

    const prefetchImage = (src) => {
        if (!src || prefetchedSources.has(src)) {
            return;
        }

        prefetchedSources.add(src);
        const img = new Image();
        img.src = src;
    };

    const prefetchVideo = (src) => {
        if (!src || prefetchedSources.has(src)) {
            return prefetchedVideos.get(src) || null;
        }

        prefetchedSources.add(src);

        const preloadVideo = document.createElement("video");
        preloadVideo.preload = "auto";
        preloadVideo.playsInline = true;
        preloadVideo.muted = true;
        preloadVideo.src = src;
        preloadVideo.load();
        prefetchedVideos.set(src, preloadVideo);

        return preloadVideo;
    };

    const prefetchMedia = (src, type) => {
        if (type === "video") {
            prefetchVideo(src);
            return;
        }

        prefetchImage(src);
    };

    const prefetchAdjacentItems = (items, index) => {
        [index - 1, index + 1].forEach((itemIndex) => {
            const item = items[itemIndex];
            if (item) {
                prefetchMedia(item.src, item.type);
            }
        });
    };

    document.querySelectorAll("[data-gallery-group]").forEach((trigger) => {
        const group = trigger.dataset.galleryGroup;
        if (!groups[group]) {
            groups[group] = [];
        }

        const index = groups[group].length;
        groups[group].push({
            type: trigger.dataset.galleryType,
            src: trigger.dataset.gallerySrc,
            fallbackSrc: trigger.dataset.galleryFallback || "",
            poster: trigger.dataset.galleryPoster,
            title: trigger.dataset.galleryTitle || "",
            caption: trigger.dataset.galleryCaption || "",
            credit: trigger.dataset.galleryCredit || "",
        });

        trigger.addEventListener("pointerenter", () => {
            prefetchMedia(trigger.dataset.gallerySrc, trigger.dataset.galleryType);
        });

        trigger.addEventListener("click", () => {
            openLightbox(group, index);
        });
    });

    const pauseVideo = () => {
        if (!videoEl) {
            return;
        }

        videoEl.pause();
        videoEl.removeAttribute("src");
        videoEl.load();
        videoEl.hidden = true;
    };

    const hideImage = () => {
        if (!imageEl) {
            return;
        }

        imageEl.removeAttribute("src");
        imageEl.hidden = true;
        imageEl.classList.remove("gallery-lightbox__image--loading");
    };

    const updateMeta = (item) => {
        if (titleEl) {
            titleEl.textContent = item.title;
            titleEl.hidden = !item.title;
        }

        if (captionEl) {
            captionEl.textContent = item.caption;
            captionEl.hidden = !item.caption;
        }

        if (creditEl) {
            creditEl.textContent = item.credit;
            creditEl.hidden = !item.credit;
        }
    };

    const updateNavButtons = (items) => {
        prevBtn.disabled = activeIndex <= 0;
        nextBtn.disabled = activeIndex >= items.length - 1;
    };

    const playVideoNow = (video) => {
        const playPromise = video.play();

        if (playPromise !== undefined) {
            playPromise.catch(() => {
                /* Native controls remain available if autoplay is blocked. */
            });
        }
    };

    const renderItem = (item) => {
        const token = ++renderToken;

        pauseVideo();
        hideImage();

        if (item.type === "video" && videoEl) {
            videoEl.poster = item.poster || "";
            videoEl.hidden = false;

            const loadVideoSource = (src) => {
                videoEl.src = src;
                videoEl.load();
                playVideoNow(videoEl);
            };

            loadVideoSource(item.src);

            videoEl.addEventListener(
                "loadeddata",
                () => {
                    if (token !== renderToken || !videoEl.paused) {
                        return;
                    }

                    playVideoNow(videoEl);
                },
                { once: true },
            );

            videoEl.addEventListener(
                "error",
                () => {
                    if (
                        token !== renderToken
                        || !item.fallbackSrc
                        || videoEl.src === item.fallbackSrc
                    ) {
                        return;
                    }

                    loadVideoSource(item.fallbackSrc);
                },
                { once: true },
            );
        } else if (imageEl) {
            imageEl.alt = item.title || "Gallery photo";
            imageEl.hidden = false;
            imageEl.fetchPriority = "high";

            const showFullImage = () => {
                if (token !== renderToken) {
                    return;
                }

                imageEl.src = item.src;
                imageEl.classList.remove("gallery-lightbox__image--loading");
            };

            if (item.poster && item.poster !== item.src) {
                imageEl.src = item.poster;
                imageEl.classList.add("gallery-lightbox__image--loading");

                prefetchImage(item.src);

                const fullImage = new Image();
                fullImage.fetchPriority = "high";
                fullImage.onload = showFullImage;
                fullImage.onerror = showFullImage;
                fullImage.src = item.src;

                if (fullImage.complete) {
                    showFullImage();
                }
            } else {
                imageEl.src = item.src;
            }
        }

        updateMeta(item);
    };

    const openLightbox = (group, index) => {
        const items = groups[group];

        if (!items || !items.length) {
            return;
        }

        activeGroup = group;
        activeIndex = index;

        lightbox.classList.add("is-open");
        lightbox.setAttribute("aria-hidden", "false");
        document.body.classList.add("gallery-lightbox-open");

        renderItem(items[activeIndex]);
        updateNavButtons(items);

        prefetchMedia(items[activeIndex].src, items[activeIndex].type);
        prefetchAdjacentItems(items, activeIndex);

        if (items[activeIndex].type !== "video") {
            closeBtn.focus();
        }
    };

    const closeLightbox = () => {
        lightbox.classList.remove("is-open");
        lightbox.setAttribute("aria-hidden", "true");
        document.body.classList.remove("gallery-lightbox-open");
        pauseVideo();
        hideImage();
        activeGroup = null;
        activeIndex = 0;
    };

    const showRelativeItem = (offset) => {
        const items = groups[activeGroup];

        if (!items) {
            return;
        }

        const nextIndex = activeIndex + offset;

        if (nextIndex < 0 || nextIndex >= items.length) {
            return;
        }

        activeIndex = nextIndex;
        renderItem(items[activeIndex]);
        updateNavButtons(items);
        prefetchMedia(items[activeIndex].src, items[activeIndex].type);
        prefetchAdjacentItems(items, activeIndex);
    };

    closeBtn.addEventListener("click", closeLightbox);
    prevBtn.addEventListener("click", () => showRelativeItem(-1));
    nextBtn.addEventListener("click", () => showRelativeItem(1));

    lightbox.addEventListener("click", (event) => {
        if (event.target === lightbox) {
            closeLightbox();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (!lightbox.classList.contains("is-open")) {
            return;
        }

        if (event.key === "Escape") {
            closeLightbox();
        }

        if (event.key === "ArrowLeft") {
            showRelativeItem(-1);
        }

        if (event.key === "ArrowRight") {
            showRelativeItem(1);
        }
    });

    lightbox.addEventListener(
        "touchstart",
        (event) => {
            touchStartX = event.changedTouches[0].screenX;
        },
        { passive: true },
    );

    lightbox.addEventListener(
        "touchend",
        (event) => {
            const touchEndX = event.changedTouches[0].screenX;
            const deltaX = touchEndX - touchStartX;
            const swipeThreshold = 50;

            if (Math.abs(deltaX) < swipeThreshold) {
                return;
            }

            if (deltaX < 0) {
                showRelativeItem(1);
            } else {
                showRelativeItem(-1);
            }
        },
        { passive: true },
    );
});
