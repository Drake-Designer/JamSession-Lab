/*
 * Admin change form: show the "Other instrument" / "Other genre" rows only
 * when the matching "Other" checkbox is ticked.
 */
(function () {
    "use strict";

    function getFieldRow(fieldId) {
        const field = document.getElementById(fieldId);
        if (!field) {
            return null;
        }

        return (
            field.closest(".field-" + fieldId.replace(/^id_/, "")) ||
            field.closest(".form-row") ||
            field.parentElement
        );
    }

    function getCheckboxes(name) {
        return document.querySelectorAll(
            'input[name="' + name + '"][type="checkbox"]'
        );
    }

    function initOtherToggle(checkboxName, fieldId, otherValue) {
        const otherRow = getFieldRow(fieldId);
        const checkboxes = getCheckboxes(checkboxName);
        if (!otherRow || checkboxes.length === 0) {
            return;
        }

        function toggle() {
            let otherTicked = false;
            checkboxes.forEach(function (checkbox) {
                if (checkbox.value === otherValue && checkbox.checked) {
                    otherTicked = true;
                }
            });
            otherRow.style.display = otherTicked ? "" : "none";
        }

        checkboxes.forEach(function (checkbox) {
            checkbox.addEventListener("change", toggle);
        });
        toggle();
    }

    function init() {
        initOtherToggle("instruments", "id_other_instrument", "other");
        initOtherToggle("preferred_genres", "id_other_genre", "other");
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
