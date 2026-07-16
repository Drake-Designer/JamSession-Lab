/*
 * Admin change form: show the "Other instrument" row only when the
 * "Other" checkbox is ticked in the instruments checkbox group.
 */
(function () {
    "use strict";

    function getOtherInstrumentRow() {
        const otherField = document.getElementById("id_other_instrument");
        if (!otherField) {
            return null;
        }

        return (
            otherField.closest(".field-other_instrument") ||
            otherField.closest(".form-row") ||
            otherField.parentElement
        );
    }

    function getInstrumentCheckboxes() {
        return document.querySelectorAll(
            'input[name="instruments"][type="checkbox"]'
        );
    }

    function toggleOtherInstrument() {
        const otherRow = getOtherInstrumentRow();
        if (!otherRow) {
            return;
        }

        let otherTicked = false;
        getInstrumentCheckboxes().forEach(function (checkbox) {
            if (checkbox.value === "other" && checkbox.checked) {
                otherTicked = true;
            }
        });

        otherRow.style.display = otherTicked ? "" : "none";
    }

    function initInstrumentToggle() {
        const checkboxes = getInstrumentCheckboxes();
        if (checkboxes.length === 0) {
            return;
        }

        checkboxes.forEach(function (checkbox) {
            checkbox.addEventListener("change", toggleOtherInstrument);
        });
        toggleOtherInstrument();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initInstrumentToggle);
    } else {
        initInstrumentToggle();
    }
})();
