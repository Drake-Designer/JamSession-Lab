/**
 * Cover / photo crop editor and display.
 *
 * The bright frame is the exact region object-fit:cover will show on the site
 * (same aspect ratio). Focus values are real CSS object-position percentages,
 * converted to/from the frame's top-left — not the frame centre (those differ
 * except at 50%).
 *
 * Configure the picker via data attributes on #cover-focus-picker:
 *   data-cover-ratio   — width/height (default 2.4 community covers; use 1 for squares)
 *   data-focus-x-id    — hidden input id (default id_cover_focus_x)
 *   data-focus-y-id    — hidden input id (default id_cover_focus_y)
 *   data-file-input    — CSS selector for the file input (default [data-cover-focus-input])
 */
(function () {
    const DEFAULT_COVER_RATIO = 2.4; // community covers — keep in sync with community.css

    const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

    const visibleFractions = (imageWidth, imageHeight, coverRatio) => {
        const imageAR = imageWidth / imageHeight;
        if (imageAR >= coverRatio) {
            // Wider than the cover frame: full height is kept, sides are cropped.
            return { vw: coverRatio / imageAR, vh: 1 };
        }
        // Taller/narrower: full width is kept, top/bottom are cropped.
        return { vw: 1, vh: imageAR / coverRatio };
    };

    /**
     * object-position percentage ↔ crop top-left as a fraction of the image.
     * CSS: visibleTop = (1 - vh) * (objectPositionY / 100)
     */
    const objectPositionFromCrop = (cropLeftFrac, cropTopFrac, vw, vh) => {
        let x = 50;
        let y = 50;
        if (vw < 1 - 1e-6) {
            x = (100 * cropLeftFrac) / (1 - vw);
        }
        if (vh < 1 - 1e-6) {
            y = (100 * cropTopFrac) / (1 - vh);
        }
        return {
            x: clamp(x, 0, 100),
            y: clamp(y, 0, 100),
        };
    };

    const cropFromObjectPosition = (xPos, yPos, vw, vh) => {
        let cropLeftFrac = 0;
        let cropTopFrac = 0;
        if (vw < 1 - 1e-6) {
            cropLeftFrac = (xPos / 100) * (1 - vw);
        }
        if (vh < 1 - 1e-6) {
            cropTopFrac = (yPos / 100) * (1 - vh);
        }
        return { cropLeftFrac, cropTopFrac };
    };

    const applyCoverFocus = () => {
        document.querySelectorAll("[data-cover-focus-x]").forEach((element) => {
            const x = element.getAttribute("data-cover-focus-x");
            const y = element.getAttribute("data-cover-focus-y");
            if (x === null || y === null) {
                return;
            }
            element.style.objectPosition = `${x}% ${y}%`;
        });
    };

    const initCoverFocusPicker = () => {
        const picker = document.getElementById("cover-focus-picker");
        if (!picker) {
            return;
        }

        const coverRatio =
            parseFloat(picker.getAttribute("data-cover-ratio") || "") ||
            DEFAULT_COVER_RATIO;
        const focusXId =
            picker.getAttribute("data-focus-x-id") || "id_cover_focus_x";
        const focusYId =
            picker.getAttribute("data-focus-y-id") || "id_cover_focus_y";
        const fileSelector =
            picker.getAttribute("data-file-input") || "[data-cover-focus-input]";

        const fileInput = document.querySelector(fileSelector);
        const previewImage = document.getElementById("cover-focus-preview");
        const focusXInput = document.getElementById(focusXId);
        const focusYInput = document.getElementById(focusYId);
        const workspace = document.getElementById("cover-focus-workspace");
        const crop = document.getElementById("cover-focus-crop");
        const resultImage = document.getElementById("cover-focus-result-image");

        if (
            !previewImage
            || !focusXInput
            || !focusYInput
            || !workspace
            || !crop
            || !resultImage
        ) {
            return;
        }

        const existingSrc = picker.getAttribute("data-existing-cover-url") || "";

        let imageLeft = 0;
        let imageTop = 0;
        let imageWidth = 0;
        let imageHeight = 0;
        let cropWidth = 0;
        let cropHeight = 0;
        let cropX = 0;
        let cropY = 0;
        let vw = 1;
        let vh = 1;
        let isDragging = false;
        let dragOffsetX = 0;
        let dragOffsetY = 0;

        const readFocus = () => ({
            x: clamp(parseFloat(focusXInput.value) || 50, 0, 100),
            y: clamp(parseFloat(focusYInput.value) || 50, 0, 100),
        });

        const writeFocus = (x, y) => {
            const nextX = Math.round(clamp(x, 0, 100) * 10) / 10;
            const nextY = Math.round(clamp(y, 0, 100) * 10) / 10;
            focusXInput.value = String(nextX);
            focusYInput.value = String(nextY);
            resultImage.style.objectPosition = `${nextX}% ${nextY}%`;
        };

        const syncFocusFromCrop = () => {
            if (!imageWidth || !imageHeight) {
                return;
            }
            const cropLeftFrac = (cropX - imageLeft) / imageWidth;
            const cropTopFrac = (cropY - imageTop) / imageHeight;
            const focus = objectPositionFromCrop(cropLeftFrac, cropTopFrac, vw, vh);
            writeFocus(focus.x, focus.y);
        };

        const placeCropFromFocus = () => {
            if (!imageWidth || !imageHeight || !cropWidth || !cropHeight) {
                return;
            }
            const focus = readFocus();
            const { cropLeftFrac, cropTopFrac } = cropFromObjectPosition(
                focus.x,
                focus.y,
                vw,
                vh,
            );
            cropX = imageLeft + cropLeftFrac * imageWidth;
            cropY = imageTop + cropTopFrac * imageHeight;
            cropX = clamp(cropX, imageLeft, imageLeft + imageWidth - cropWidth);
            cropY = clamp(cropY, imageTop, imageTop + imageHeight - cropHeight);
            crop.style.transform = `translate(${cropX}px, ${cropY}px)`;
            syncFocusFromCrop();
        };

        const layout = () => {
            if (!previewImage.naturalWidth) {
                return;
            }

            const workspaceRect = workspace.getBoundingClientRect();
            const pad = 16;
            const maxW = Math.max(0, workspaceRect.width - pad * 2);
            const maxH = Math.max(0, workspaceRect.height - pad * 2);
            const natW = previewImage.naturalWidth;
            const natH = previewImage.naturalHeight;
            const containScale = Math.min(maxW / natW, maxH / natH);

            imageWidth = natW * containScale;
            imageHeight = natH * containScale;
            imageLeft = (workspaceRect.width - imageWidth) / 2;
            imageTop = (workspaceRect.height - imageHeight) / 2;

            previewImage.style.width = `${imageWidth}px`;
            previewImage.style.height = `${imageHeight}px`;
            previewImage.style.transform = `translate(${imageLeft}px, ${imageTop}px)`;

            ({ vw, vh } = visibleFractions(imageWidth, imageHeight, coverRatio));
            cropWidth = vw * imageWidth;
            cropHeight = vh * imageHeight;

            crop.style.width = `${cropWidth}px`;
            crop.style.height = `${cropHeight}px`;
            placeCropFromFocus();
        };

        const showPicker = (src) => {
            picker.hidden = false;
            resultImage.src = src;

            const onReady = () => {
                layout();
            };

            previewImage.onload = onReady;
            previewImage.src = src;
            if (previewImage.complete && previewImage.naturalWidth) {
                onReady();
            }
        };

        if (existingSrc) {
            showPicker(existingSrc);
        }

        if (fileInput) {
            fileInput.addEventListener("change", () => {
                const file = fileInput.files && fileInput.files[0];
                const looksLikeImage =
                    file
                    && (
                        (file.type && file.type.startsWith("image/"))
                        || /\.(jpe?g|png|gif|webp|heic|heif)$/i.test(
                            file.name || ""
                        )
                    );
                if (!looksLikeImage) {
                    if (existingSrc) {
                        showPicker(existingSrc);
                    } else {
                        picker.hidden = true;
                        previewImage.removeAttribute("src");
                        resultImage.removeAttribute("src");
                    }
                    return;
                }

                const reader = new FileReader();
                reader.onload = () => {
                    if (!existingSrc) {
                        writeFocus(50, 50);
                    }
                    showPicker(reader.result);
                };
                reader.readAsDataURL(file);
            });
        }

        crop.addEventListener("pointerdown", (event) => {
            if (picker.hidden) {
                return;
            }
            isDragging = true;
            dragOffsetX = event.clientX - cropX;
            dragOffsetY = event.clientY - cropY;
            crop.classList.add("is-dragging");
            crop.setPointerCapture(event.pointerId);
            event.preventDefault();
        });

        crop.addEventListener("pointermove", (event) => {
            if (!isDragging) {
                return;
            }
            cropX = clamp(
                event.clientX - dragOffsetX,
                imageLeft,
                imageLeft + imageWidth - cropWidth,
            );
            cropY = clamp(
                event.clientY - dragOffsetY,
                imageTop,
                imageTop + imageHeight - cropHeight,
            );
            crop.style.transform = `translate(${cropX}px, ${cropY}px)`;
            syncFocusFromCrop();
        });

        const endDrag = (event) => {
            if (!isDragging) {
                return;
            }
            isDragging = false;
            crop.classList.remove("is-dragging");
            if (crop.hasPointerCapture(event.pointerId)) {
                crop.releasePointerCapture(event.pointerId);
            }
        };

        crop.addEventListener("pointerup", endDrag);
        crop.addEventListener("pointercancel", endDrag);

        window.addEventListener("resize", () => {
            if (!picker.hidden && previewImage.naturalWidth) {
                layout();
            }
        });
    };

    document.addEventListener("DOMContentLoaded", () => {
        applyCoverFocus();
        initCoverFocusPicker();
    });
})();
