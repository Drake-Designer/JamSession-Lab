/**
 * Admin Tool — tabs stay as links; this script handles selection, bulk
 * delete / approve / reject, and the in-page media lightbox.
 *
 * Bulk delete uses the shared confirm modal (forms with class js-confirm-delete).
 * Select-all is scoped per section.
 */
document.addEventListener("DOMContentLoaded", () => {
    const selectionBar = document.getElementById("admin-tool-selection-bar");
    const countEl = selectionBar?.querySelector(".admin-tool-bar__count");
    const cancelBtn = selectionBar?.querySelector("[data-admin-tool-cancel]");
    const deleteSelectedBtn = selectionBar?.querySelector(
        "[data-admin-tool-delete-selected]"
    );
    const approveSelectedBtn = selectionBar?.querySelector(
        "[data-admin-tool-approve-selected]"
    );
    const rejectSelectedBtn = selectionBar?.querySelector(
        "[data-admin-tool-reject-selected]"
    );
    const bulkForm = document.getElementById("admin-tool-bulk-form");
    const bulkFields = document.getElementById("admin-tool-bulk-fields");
    const bulkModerateForm = document.getElementById("admin-tool-bulk-moderate-form");
    const bulkModerateFields = document.getElementById(
        "admin-tool-bulk-moderate-fields"
    );
    const bulkModerateAction = document.getElementById(
        "admin-tool-bulk-moderate-action"
    );
    const bulkModerateReason = document.getElementById(
        "admin-tool-bulk-moderate-reason"
    );

    const getCheckboxes = () => document.querySelectorAll(".admin-tool-check");

    const getSectionCheckboxes = (section) =>
        section.querySelectorAll(".admin-tool-check");

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

    const fillIdFields = (container, selected) => {
        container.innerHTML = "";

        selected.gallery.forEach((id) => {
            const input = document.createElement("input");
            input.type = "hidden";
            input.name = "gallery_ids";
            input.value = id;
            container.appendChild(input);
        });

        selected.post.forEach((id) => {
            const input = document.createElement("input");
            input.type = "hidden";
            input.name = "post_ids";
            input.value = id;
            container.appendChild(input);
        });

        selected.comment.forEach((id) => {
            const input = document.createElement("input");
            input.type = "hidden";
            input.name = "comment_ids";
            input.value = id;
            container.appendChild(input);
        });
    };

    const updateSelectAllStates = () => {
        document.querySelectorAll("[data-admin-tool-section]").forEach((section) => {
            const selectAll = section.querySelector("[data-select-all-section]");
            if (!selectAll) {
                return;
            }

            const kindCheckboxes = [...getSectionCheckboxes(section)];
            const checkedCount = kindCheckboxes.filter((checkbox) => checkbox.checked)
                .length;

            selectAll.checked =
                kindCheckboxes.length > 0 && checkedCount === kindCheckboxes.length;
            selectAll.indeterminate =
                checkedCount > 0 && checkedCount < kindCheckboxes.length;
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
        checkbox.addEventListener("click", (event) => {
            event.stopPropagation();
        });
    });

    document.querySelectorAll("[data-admin-tool-section]").forEach((section) => {
        const selectAll = section.querySelector("[data-select-all-section]");
        if (!selectAll) {
            return;
        }

        selectAll.addEventListener("change", () => {
            const shouldCheck = selectAll.checked;
            getSectionCheckboxes(section).forEach((checkbox) => {
                checkbox.checked = shouldCheck;
            });
            updateSelectionBar();
        });
    });

    cancelBtn?.addEventListener("click", () => {
        getCheckboxes().forEach((checkbox) => {
            checkbox.checked = false;
        });

        document.querySelectorAll("[data-select-all-section]").forEach((selectAll) => {
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

        fillIdFields(bulkFields, selected);

        bulkForm.dataset.confirmMessage =
            count === 1
                ? "Delete 1 item? This cannot be undone."
                : `Delete ${count} items? This cannot be undone.`;

        bulkForm.requestSubmit();
    });

    const submitBulkModerate = (action) => {
        if (!bulkModerateForm || !bulkModerateFields || !bulkModerateAction) {
            return;
        }

        const selected = getSelectedByKind();
        const count = getSelectedCount();

        if (count === 0) {
            return;
        }

        let reason = "";
        if (action === "reject") {
            reason = window.prompt("Rejection reason (optional):", "") || "";
        }

        fillIdFields(bulkModerateFields, selected);
        bulkModerateAction.value = action;
        if (bulkModerateReason) {
            bulkModerateReason.value = reason;
        }
        bulkModerateForm.requestSubmit();
    };

    approveSelectedBtn?.addEventListener("click", () => {
        submitBulkModerate("approve");
    });

    rejectSelectedBtn?.addEventListener("click", () => {
        submitBulkModerate("reject");
    });

    /* Auto-save gallery pin order when a pin field changes (digits only). */
    const getCsrfToken = () => {
        const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return input ? input.value : "";
    };

    const digitsOnly = (value) => String(value || "").replace(/\D/g, "").slice(0, 3);

    const normalisedPinValue = (value) => {
        const digits = digitsOnly(value);
        if (digits === "" || Number.parseInt(digits, 10) === 0) {
            return "";
        }
        return digits;
    };

    const clearPinState = (input, statusEl) => {
        input.classList.remove("is-saving", "is-saved", "is-error");
        if (statusEl) {
            statusEl.textContent = "";
            statusEl.classList.remove("is-error");
        }
    };

    const savePinOrder = (input) => {
        const url = input.dataset.pinUrl;
        if (!url || input.dataset.saving === "1") {
            return;
        }

        const nextValue = normalisedPinValue(input.value);
        if (input.value !== nextValue) {
            input.value = nextValue;
        }

        const initialValue = input.dataset.pinInitial || "";
        if (nextValue === initialValue) {
            return;
        }

        const statusEl = input
            .closest(".admin-tool-pin-form")
            ?.querySelector(".admin-tool-pin-form__status");

        clearPinState(input, statusEl);
        input.classList.add("is-saving");
        input.dataset.saving = "1";

        const body = new FormData();
        body.append("pin_order", nextValue);
        body.append("csrfmiddlewaretoken", getCsrfToken());

        fetch(url, {
            method: "POST",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": getCsrfToken(),
            },
            body,
            credentials: "same-origin",
        })
            .then(async (response) => {
                let data = {};
                try {
                    data = await response.json();
                } catch (error) {
                    data = {};
                }

                input.dataset.saving = "0";
                input.classList.remove("is-saving");

                if (!response.ok || !data.ok) {
                    input.classList.add("is-error");
                    if (
                        Object.prototype.hasOwnProperty.call(data, "pin_order")
                    ) {
                        const restored =
                            data.pin_order === null || data.pin_order === undefined
                                ? ""
                                : String(data.pin_order);
                        input.value = restored;
                        input.dataset.pinInitial = restored;
                    }
                    if (statusEl) {
                        statusEl.textContent = data.message || "Could not save";
                        statusEl.classList.add("is-error");
                    }
                    return;
                }

                const saved =
                    data.pin_order === null || data.pin_order === undefined
                        ? ""
                        : String(data.pin_order);
                input.value = saved;
                input.dataset.pinInitial = saved;
                input.classList.add("is-saved");
                if (statusEl) {
                    statusEl.textContent = "Saved";
                    statusEl.classList.remove("is-error");
                }

                window.setTimeout(() => {
                    clearPinState(input, statusEl);
                }, 1400);
            })
            .catch(() => {
                input.dataset.saving = "0";
                input.classList.remove("is-saving");
                input.classList.add("is-error");
                if (statusEl) {
                    statusEl.textContent = "Could not save";
                    statusEl.classList.add("is-error");
                }
            });
    };

    document.querySelectorAll(".admin-tool-pin-form__input[data-pin-url]").forEach((input) => {
        input.addEventListener("beforeinput", (event) => {
            if (event.inputType && event.inputType.startsWith("insert")) {
                const data = event.data || "";
                if (data && /\D/.test(data)) {
                    event.preventDefault();
                }
            }
        });

        input.addEventListener("input", () => {
            const cleaned = digitsOnly(input.value);
            if (input.value !== cleaned) {
                input.value = cleaned;
            }
        });

        input.addEventListener("paste", (event) => {
            event.preventDefault();
            const pasted = (event.clipboardData || window.clipboardData).getData("text");
            input.value = digitsOnly(pasted);
        });

        input.addEventListener("change", () => {
            input.value = normalisedPinValue(input.value);
            savePinOrder(input);
        });

        input.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                input.blur();
            }
        });
    });

    /* In-page preview lightbox (image / video / text) */
    const lightbox = document.getElementById("admin-tool-lightbox");

    if (!lightbox) {
        updateSelectionBar();
        return;
    }

    const imageEl = lightbox.querySelector(".admin-tool-lightbox__image");
    const videoEl = lightbox.querySelector(".admin-tool-lightbox__video");
    const textEl = lightbox.querySelector(".admin-tool-lightbox__text");
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

        if (textEl) {
            textEl.hidden = true;
            textEl.textContent = "";
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
        const text = trigger.dataset.previewText || "";

        if (!src && type !== "text" && !text) {
            return;
        }

        resetLightboxMedia();

        if (type === "video" && src && videoEl) {
            if (poster) {
                videoEl.poster = poster;
            }
            videoEl.src = src;
            videoEl.hidden = false;
            videoEl.load();
        } else if (type === "text" || (!src && text)) {
            if (textEl) {
                textEl.textContent = text;
                textEl.hidden = false;
            }
        } else if (src && imageEl) {
            imageEl.src = src;
            imageEl.alt = title || "Media preview";
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

    document.querySelectorAll(".admin-tool-preview").forEach((trigger) => {
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
