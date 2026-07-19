(function () {
    const form = document.getElementById("event-rsvp-form");
    if (!form) {
        return;
    }

    const openJamCheckbox = form.querySelector("#id_join_open_jam");
    const originalsBlock = document.getElementById("originals-in-jam-block");
    const songsBlock = document.getElementById("songs-block");
    const addSongBtn = document.getElementById("add-song-btn");
    const songsForms = document.getElementById("songs-forms");
    const totalFormsInput = form.querySelector("#id_songs-TOTAL_FORMS");

    function originalsChoice() {
        const checked = form.querySelector(
            'input[name="originals_choice"]:checked'
        );
        return checked ? checked.value : null;
    }

    function syncVisibility() {
        const jamSelected = openJamCheckbox && openJamCheckbox.checked;
        if (originalsBlock) {
            originalsBlock.hidden = !jamSelected;
        }
        const showSongs = jamSelected && originalsChoice() === "yes";
        if (songsBlock) {
            songsBlock.hidden = !showSongs;
        }
    }

    if (openJamCheckbox) {
        openJamCheckbox.addEventListener("change", syncVisibility);
    }

    form.querySelectorAll('input[name="originals_choice"]').forEach(
        function (input) {
            input.addEventListener("change", syncVisibility);
        }
    );

    if (addSongBtn && songsForms && totalFormsInput) {
        addSongBtn.addEventListener("click", function () {
            const index = parseInt(totalFormsInput.value, 10);
            const template = songsForms.querySelector(".song-form");
            if (!template) {
                return;
            }
            const clone = template.cloneNode(true);
            clone.querySelectorAll("input, textarea, select, label").forEach(
                function (el) {
                    if (el.name) {
                        el.name = el.name.replace(/songs-\d+-/, "songs-" + index + "-");
                    }
                    if (el.id) {
                        el.id = el.id.replace(/id_songs-\d+-/, "id_songs-" + index + "-");
                    }
                    if (el.htmlFor) {
                        el.htmlFor = el.htmlFor.replace(
                            /id_songs-\d+-/,
                            "id_songs-" + index + "-"
                        );
                    }
                    if (el.type === "checkbox") {
                        el.checked = false;
                    } else if (el.tagName !== "LABEL") {
                        el.value = "";
                    }
                }
            );
            songsForms.appendChild(clone);
            totalFormsInput.value = String(index + 1);
        });
    }

    syncVisibility();
})();
