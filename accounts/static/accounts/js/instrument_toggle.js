(function () {
    "use strict";

    function getInstrumentOtherRow() {
        const otherField = document.getElementById("id_instrument_other");
        if (!otherField) {
            return null;
        }

        return (
            otherField.closest(".field-instrument_other") ||
            otherField.closest(".form-row") ||
            otherField.parentElement
        );
    }

    function toggleInstrumentOther() {
        const instrumentSelect = document.getElementById("id_instrument");
        const otherRow = getInstrumentOtherRow();

        if (!instrumentSelect || !otherRow) {
            return;
        }

        if (instrumentSelect.value === "other") {
            otherRow.style.display = "";
        } else {
            otherRow.style.display = "none";
        }
    }

    function initInstrumentToggle() {
        const instrumentSelect = document.getElementById("id_instrument");
        if (!instrumentSelect) {
            return;
        }

        instrumentSelect.addEventListener("change", toggleInstrumentOther);
        toggleInstrumentOther();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initInstrumentToggle);
    } else {
        initInstrumentToggle();
    }
})();
