/* Tiny display helper: apply stored object-position from data attributes. */
(function () {
    "use strict";

    function applyObjectPosition() {
        document.querySelectorAll("[data-cover-focus-x]").forEach(function (element) {
            const x = element.getAttribute("data-cover-focus-x");
            const y = element.getAttribute("data-cover-focus-y");
            if (x === null || y === null) {
                return;
            }
            element.style.objectPosition = x + "% " + y + "%";
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", applyObjectPosition);
    } else {
        applyObjectPosition();
    }
})();
