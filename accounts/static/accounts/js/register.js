/*
 * Registration form behaviour:
 * 1. Dependent dropdown — Town/City options follow the selected County.
 * 2. "Other" instrument — free-text field only visible when Other is ticked.
 */
(function () {
    "use strict";

    function readJsonScript(id) {
        const element = document.getElementById(id);
        if (!element) {
            return null;
        }
        try {
            return JSON.parse(element.textContent);
        } catch (error) {
            return null;
        }
    }

    /* ---- Dependent County -> Town/City dropdown ---- */

    function populateTowns(countySelect, townSelect, townsByCounty, selectedTown) {
        const county = countySelect.value;
        const towns = townsByCounty[county] || [];

        townSelect.innerHTML = "";

        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = county
            ? "Select your town or city"
            : "Select a county first";
        townSelect.appendChild(placeholder);

        towns.forEach(function (town) {
            const option = document.createElement("option");
            option.value = town;
            option.textContent = town;
            if (town === selectedTown) {
                option.selected = true;
            }
            townSelect.appendChild(option);
        });

        townSelect.disabled = towns.length === 0;
    }

    function initDependentTowns() {
        const countySelect = document.getElementById("id_county");
        const townSelect = document.getElementById("id_town_city");
        const townsByCounty = readJsonScript("towns-by-county");

        if (!countySelect || !townSelect || !townsByCounty) {
            return;
        }

        // Restore the town submitted before a validation error, if any.
        const selectedTown = readJsonScript("selected-town") || "";
        populateTowns(countySelect, townSelect, townsByCounty, selectedTown);

        countySelect.addEventListener("change", function () {
            populateTowns(countySelect, townSelect, townsByCounty, "");
        });
    }

    /* ---- "Other" instrument toggle ---- */

    function initOtherInstrumentToggle() {
        const wrapper = document.getElementById("other-instrument-field");
        const checkboxes = document.querySelectorAll(
            'input[name="instruments"][type="checkbox"]'
        );

        if (!wrapper || checkboxes.length === 0) {
            return;
        }

        function toggle() {
            let otherTicked = false;
            checkboxes.forEach(function (checkbox) {
                if (checkbox.value === "other" && checkbox.checked) {
                    otherTicked = true;
                }
            });
            wrapper.classList.toggle("is-hidden", !otherTicked);
        }

        checkboxes.forEach(function (checkbox) {
            checkbox.addEventListener("change", toggle);
        });
        toggle();
    }

    function init() {
        initDependentTowns();
        initOtherInstrumentToggle();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
