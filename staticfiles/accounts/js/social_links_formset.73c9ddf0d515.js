/*
 * SocialLink formset on Edit Profile:
 * - Add / remove rows
 * - Show Remove only when the URL field has content (or a saved link)
 * - Saved links are deleted immediately via AJAX (no Save Changes)
 */
(function () {
    "use strict";

    function getCsrfToken() {
        const input = document.querySelector(
            'form.jam-form input[name="csrfmiddlewaretoken"]'
        );
        return input ? input.value : "";
    }

    function getTotalFormsInput() {
        return document.getElementById("id_social_links-TOTAL_FORMS");
    }

    function getInitialFormsInput() {
        return document.getElementById("id_social_links-INITIAL_FORMS");
    }

    function visibleRows(container) {
        return Array.from(
            container.querySelectorAll(".social-links-row:not(.is-marked-delete)")
        );
    }

    function visibleRowCount(container) {
        return visibleRows(container).length;
    }

    function updateAddButton(addButton, container, maxForms) {
        if (!addButton) {
            return;
        }
        addButton.disabled = visibleRowCount(container) >= maxForms;
    }

    function hasSavedId(row) {
        const idInput = row.querySelector('input[name$="-id"]');
        return Boolean(idInput && idInput.value);
    }

    function getUrlInput(row) {
        return row.querySelector('input[name$="-url"]');
    }

    function syncRemoveVisibility(row) {
        const wrap = row.querySelector(".social-links-row__delete-wrap");
        const urlInput = getUrlInput(row);
        if (!wrap) {
            return;
        }
        const hasUrl = Boolean(urlInput && urlInput.value.trim());
        const show = hasSavedId(row) || hasUrl;
        wrap.classList.toggle("is-hidden", !show);
    }

    function reindexForms(container, totalFormsInput, initialFormsInput) {
        const rows = Array.from(container.querySelectorAll(".social-links-row"));
        let initialCount = 0;

        rows.forEach(function (row, index) {
            row.querySelectorAll("input, label, button").forEach(function (el) {
                if (el.name) {
                    el.name = el.name.replace(
                        /social_links-\d+-/,
                        "social_links-" + index + "-"
                    );
                }
                if (el.id && el.id.indexOf("id_social_links-") === 0) {
                    el.id = el.id.replace(
                        /id_social_links-\d+-/,
                        "id_social_links-" + index + "-"
                    );
                }
                if (el.htmlFor && el.htmlFor.indexOf("id_social_links-") === 0) {
                    el.htmlFor = el.htmlFor.replace(
                        /id_social_links-\d+-/,
                        "id_social_links-" + index + "-"
                    );
                }
            });

            const idInput = row.querySelector('input[name$="-id"]');
            if (idInput && idInput.value) {
                initialCount += 1;
            }
        });

        totalFormsInput.value = String(rows.length);
        if (initialFormsInput) {
            initialFormsInput.value = String(initialCount);
        }
    }

    function ensureAtLeastOneRow(container, template, totalFormsInput, initialFormsInput, addButton, maxForms) {
        if (visibleRowCount(container) > 0) {
            return;
        }

        const html = template.innerHTML.replace(/__prefix__/g, "0");
        const wrapper = document.createElement("div");
        wrapper.innerHTML = html.trim();
        const row = wrapper.firstElementChild;
        if (!row) {
            return;
        }
        container.appendChild(row);
        totalFormsInput.value = "1";
        if (initialFormsInput) {
            initialFormsInput.value = "0";
        }
        bindRow(row, container, template, addButton, maxForms, totalFormsInput, initialFormsInput);
        updateAddButton(addButton, container, maxForms);
    }

    function removeRowFromDom(row, container, template, addButton, maxForms, totalFormsInput, initialFormsInput) {
        row.remove();
        reindexForms(container, totalFormsInput, initialFormsInput);
        ensureAtLeastOneRow(
            container,
            template,
            totalFormsInput,
            initialFormsInput,
            addButton,
            maxForms
        );
        updateAddButton(addButton, container, maxForms);
    }

    function clearUnsavedRow(row) {
        const urlInput = getUrlInput(row);
        if (urlInput) {
            urlInput.value = "";
        }
        syncRemoveVisibility(row);
    }

    function bindRow(row, container, template, addButton, maxForms, totalFormsInput, initialFormsInput) {
        const urlInput = getUrlInput(row);
        const button = row.querySelector("[data-social-link-remove]");

        if (urlInput) {
            urlInput.addEventListener("input", function () {
                syncRemoveVisibility(row);
            });
            urlInput.addEventListener("change", function () {
                syncRemoveVisibility(row);
            });
        }

        syncRemoveVisibility(row);

        if (!button) {
            return;
        }

        button.addEventListener("click", function () {
            if (button.disabled) {
                return;
            }

            const deleteUrl = row.getAttribute("data-delete-url");

            if (deleteUrl && hasSavedId(row)) {
                button.disabled = true;
                fetch(deleteUrl, {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": getCsrfToken(),
                        Accept: "application/json",
                    },
                    credentials: "same-origin",
                })
                    .then(function (response) {
                        if (!response.ok) {
                            throw new Error("Delete failed");
                        }
                        return response.json();
                    })
                    .then(function () {
                        removeRowFromDom(
                            row,
                            container,
                            template,
                            addButton,
                            maxForms,
                            totalFormsInput,
                            initialFormsInput
                        );
                    })
                    .catch(function () {
                        button.disabled = false;
                        window.alert(
                            "We couldn't remove that link. Please try again."
                        );
                    });
                return;
            }

            // Unsaved row: clear if it's the only one, otherwise drop the row.
            if (visibleRowCount(container) <= 1) {
                clearUnsavedRow(row);
            } else {
                removeRowFromDom(
                    row,
                    container,
                    template,
                    addButton,
                    maxForms,
                    totalFormsInput,
                    initialFormsInput
                );
            }
        });
    }

    function init() {
        const container = document.getElementById("social-links-forms");
        const template = document.getElementById("social-link-empty-form");
        const addButton = document.getElementById("social-links-add");
        const totalFormsInput = getTotalFormsInput();
        const initialFormsInput = getInitialFormsInput();

        if (!container || !template || !totalFormsInput) {
            return;
        }

        const maxForms = parseInt(container.dataset.maxForms || "5", 10);

        container.querySelectorAll(".social-links-row").forEach(function (row) {
            bindRow(
                row,
                container,
                template,
                addButton,
                maxForms,
                totalFormsInput,
                initialFormsInput
            );
        });

        updateAddButton(addButton, container, maxForms);

        if (!addButton) {
            return;
        }

        addButton.addEventListener("click", function () {
            if (visibleRowCount(container) >= maxForms) {
                return;
            }

            const index = parseInt(totalFormsInput.value, 10);
            const html = template.innerHTML.replace(/__prefix__/g, String(index));
            const wrapper = document.createElement("div");
            wrapper.innerHTML = html.trim();
            const row = wrapper.firstElementChild;
            if (!row) {
                return;
            }

            container.appendChild(row);
            totalFormsInput.value = String(index + 1);
            bindRow(
                row,
                container,
                template,
                addButton,
                maxForms,
                totalFormsInput,
                initialFormsInput
            );
            updateAddButton(addButton, container, maxForms);

            const urlInput = getUrlInput(row);
            if (urlInput) {
                urlInput.focus();
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
