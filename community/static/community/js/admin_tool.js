/**
 * Admin Tool — bulk selection, delete, and gallery preview lightbox.
 *
 * Bulk delete uses the shared confirm modal (forms with class js-confirm-delete).
 */
document.addEventListener("DOMContentLoaded", () => {
    const selectionBar = document.getElementById("admin-tool-selection-bar");
    const countEl = selectionBar?.querySelector(".admin-tool-bar__count");
    const cancelBtn = selectionBar?.querySelector("[data-admin-tool-cancel]");
    const deleteSelectedBtn = selectionBar?.querySelector("[data-admin-tool-delete-selected]");
    const bulkForm = document.getElementById("admin-tool-bulk-form");
    const bulkFields = document.getElementById("admin-tool-bulk-fields");

    const getCheckboxes = () => document.querySelectorAll(".admin-tool-check");

    const getSelectedByKind = () => {
        const selected = {
            gallery: [],
            post: [],
            comment: [],
        };

        getCheckboxes().forEach((checkbox) => {
            if (!checkbox.checked) {
                return;
            }

            const kind = checkbox.dataset.kind;
            const id = checkbox.dataset.id;

            if (kind && id && Object.prototype.hasOwnProperty.call(selected, kind)) {
                selected[kind].push(id);
            }
        });

        return selected;
    };

    const getSelectedCount = () => {
        let count = 0;
        getCheckboxes().forEach((checkbox) => {
            if (checkbox.checked) {
                count += 1;
            }
        });
        return count;
    };

    const updateSelectAllStates = () => {
        document.querySelectorAll("[data-select-all]").forEach((selectAll) => {
            const kind = selectAll.dataset.selectAll;
            const kindCheckboxes = [...getCheckboxes()].filter(
                (checkbox) => checkbox.dataset.kind === kind
            );
            const checkedCount = kindCheckboxes.filter((checkbox) => checkbox.checked).length;

            selectAll.checked = kindCheckboxes.length > 0 && checkedCount === kindCheckboxes.length;
            selectAll.indeterminate = checkedCount > 0 && checkedCount < kindCheckboxes.length;
        });
    };

    const updateSelectionBar = () => {
        const count = getSelectedCount();

        if (countEl) {
            countEl.textContent = count === 1 ? "1 selected" : `${count} selected`;
        }

        if (selectionBar) {
            selectionBar.classList.toggle("is-hidden", count === 0);
        }

        updateSelectAllStates();
    };

    getCheckboxes().forEach((checkbox) => {
        checkbox.addEventListener("change", updateSelectionBar);
    });

    document.querySelectorAll("[data-select-all]").forEach((selectAll) => {
        selectAll.addEventListener("change", () => {
            const kind = selectAll.dataset.selectAll;
            const shouldCheck = selectAll.checked;

            getCheckboxes().forEach((checkbox) => {
                if (checkbox.dataset.kind === kind) {
                    checkbox.checked = shouldCheck;
                }
            });

            updateSelectionBar();
        });
    });

    cancelBtn?.addEventListener("click", () => {
        getCheckboxes().forEach((checkbox) => {
            checkbox.checked = false;
        });

        document.querySelectorAll("[data-select-all]").forEach((selectAll) => {
            selectAll.checked = false;
            selectAll.indeterminate = false;
        });

        updateSelectionBar();
    });

    deleteSelectedBtn?.addEventListener("click", () => {
        if (!bulkForm || !bulkFields) {
            return;
        }

        const selected = getSelectedByKind();
        const count = getSelectedCount();

        if (count === 0) {
            return;
        }

        bulkFields.innerHTML = "";

        selected.gallery.forEach((id) => {
            const input = document.createElement("input");
            input.type = "hidden";
            input.name = "gallery_ids";
            input.value = id;
            bulkFields.appendChild(input);
        });

        selected.post.forEach((id) => {
            const input = document.createElement("input");
            input.type = "hidden";
            input.name = "post_ids";
            input.value = id;
            bulkFields.appendChild(input);
        });

        selected.comment.forEach((id) => {
            const input = document.createElement("input");
            input.type = "hidden";
            input.name = "comment_ids";
            input.value = id;
            bulkFields.appendChild(input);
        });

        bulkForm.dataset.confirmMessage =
            count === 1
                ? "Delete 1 item? This cannot be undone."
                : `Delete ${count} items? This cannot be undone.`;

        bulkForm.requestSubmit();
    });

    /* Gallery preview lightbox */
    const lightbox = document.getElementById("admin-tool-lightbox");

    if (!lightbox) {
        updateSelectionBar();
        return;
    }

    const imageEl = lightbox.querySelector(".admin-tool-lightbox__image");
    const videoEl = lightbox.querySelector(".admin-tool-lightbox__video");
    const titleEl = lightbox.querySelector(".admin-tool-lightbox__title");
    const closeTriggers = lightbox.querySelectorAll("[data-admin-tool-lightbox-close]");

    const resetLightboxMedia = () => {
        if (imageEl) {
            imageEl.hidden = true;
            imageEl.removeAttribute("src");
            imageEl.alt = "";
        }

        if (videoEl) {
            videoEl.pause();
            videoEl.hidden = true;
            videoEl.removeAttribute("src");
            videoEl.removeAttribute("poster");
            videoEl.load();
        }

        if (titleEl) {
            titleEl.hidden = true;
            titleEl.textContent = "";
        }
    };

    const closeLightbox = () => {
        resetLightboxMedia();
        lightbox.hidden = true;
        document.body.classList.remove("admin-tool-lightbox-open");
    };

    const openLightbox = (trigger) => {
        const src = trigger.dataset.previewSrc || "";
        const poster = trigger.dataset.previewPoster || "";
        const type = trigger.dataset.previewType || "image";
        const title = trigger.dataset.previewTitle || "";

        if (!src) {
            return;
        }

        resetLightboxMedia();

        if (type === "video" && videoEl) {
            if (poster) {
                videoEl.poster = poster;
            }
            videoEl.src = src;
            videoEl.hidden = false;
            videoEl.load();
        } else if (imageEl) {
            imageEl.src = src;
            imageEl.alt = title || "Gallery preview";
            imageEl.hidden = false;
        }

        if (titleEl && title) {
            titleEl.textContent = title;
            titleEl.hidden = false;
        }

        lightbox.hidden = false;
        document.body.classList.add("admin-tool-lightbox-open");
        lightbox.querySelector(".admin-tool-lightbox__close")?.focus();
    };

    document.querySelectorAll(".admin-tool-gallery-preview").forEach((trigger) => {
        trigger.addEventListener("click", () => {
            openLightbox(trigger);
        });
    });

    closeTriggers.forEach((trigger) => {
        trigger.addEventListener("click", closeLightbox);
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !lightbox.hidden) {
            closeLightbox();
        }
    });

    updateSelectionBar();
});
