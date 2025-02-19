document.addEventListener("DOMContentLoaded", () => {
    const settingsForm = document.getElementById("admin-section");
    const savePasswordBtn = document.getElementById("save-password-btn");
    const deleteScoreboardBtn = document.getElementById("delete-scoreboard-btn");
    let saveTimeout = null; // Used for debouncing API requests

    if (!roomID) {
        console.error("Room ID not found, unable to save settings.");
        return;
    }

    /**
     * Function to sync slider values with display spans
     */
    function syncSliderValue(sliderID, displayID) {
        const slider = document.getElementById(sliderID);
        const display = document.getElementById(displayID);

        if (slider && display) {
            display.textContent = slider.value; // Initial sync
            slider.addEventListener("input", () => {
                display.textContent = slider.value;
            });
        }
    }

    // Sync slider values for live updates
    syncSliderValue("horizontal_scroll_speed", "horizontal_scroll_speed_value");
    syncSliderValue("horizontal_scroll_delay", "horizontal_scroll_delay_value");
    syncSliderValue("vertical_scroll_speed", "vertical_scroll_speed_value");
    syncSliderValue("vertical_scroll_delay", "vertical_scroll_delay_value");

    /**
     * Collect settings data and send API request
     */
    function saveSettings() {
        clearTimeout(saveTimeout);
        saveTimeout = setTimeout(() => {
            const settingsData = {
                room_name: document.getElementById("room_name").value.trim(),
                dateformat: document.getElementById("dateformat").value,
                horizontal_scroll_enabled: document.getElementById("horizontal_scroll_enabled").checked ? "TRUE" : "FALSE",
                horizontal_scroll_speed: parseInt(document.getElementById("horizontal_scroll_speed").value, 10) || 1,
                horizontal_scroll_delay: parseInt(document.getElementById("horizontal_scroll_delay").value, 10) || 60000,
                vertical_scroll_enabled: document.getElementById("vertical_scroll_enabled").checked ? "TRUE" : "FALSE",
                vertical_scroll_speed: parseInt(document.getElementById("vertical_scroll_speed").value, 10) || 3,
                vertical_scroll_delay: parseInt(document.getElementById("vertical_scroll_delay").value, 10) || 30000,
                fullscreen_enabled: document.getElementById("fullscreen_enabled").checked ? "TRUE" : "FALSE",
                long_names_enabled: document.getElementById("long_names_enabled").checked ? "TRUE" : "FALSE",
                public_scores_enabled: document.getElementById("public_scores").checked ? "TRUE" : "FALSE",
                public_score_entry_enabled: document.getElementById("public_score_entry_enabled").checked ? "TRUE" : "FALSE",
                api_read_access: document.getElementById("api_read_access").checked ? "TRUE" : "FALSE",
                api_write_access: document.getElementById("api_write_access").checked ? "TRUE" : "FALSE",
            };

            settings.horizontalScrollEnabled = settingsData.horizontal_scroll_enabled === "TRUE";
            settings.horizontalScrollSpeed = settingsData.horizontal_scroll_speed;
            settings.horizontalScrollDelay = settingsData.horizontal_scroll_delay;
            settings.verticalScrollEnabled = settingsData.vertical_scroll_enabled === "TRUE";
            settings.verticalScrollSpeed = settingsData.vertical_scroll_speed;
            settings.verticalScrollDelay = settingsData.vertical_scroll_delay;
            settings.fullscreenEnabled = settingsData.fullscreen_enabled === "TRUE";
            settings.longNamesEnabled = settingsData.long_names_enabled === "TRUE";

            fetch(`/api/v1/settings/${roomID}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(settingsData),
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error("Error updating settings:", data.error);
                    alert("Failed to update settings.");
                } else {
                    console.log("Settings updated successfully!");
                }
            })
            .catch(error => console.error("Request error:", error));
        }, 500); // Debounce delay (500ms)
    }

    /**
     * Delete scoreboard functionality
     */
    deleteScoreboardBtn.addEventListener("click", () => {
        if (!confirm("Are you sure you want to delete this scoreboard? This action cannot be undone!")) {
            return;
        }

        fetch(`/api/v1/scoreboards/${roomID}`, { method: "DELETE" })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error("Error deleting scoreboard:", data.error);
                alert("Failed to delete scoreboard.");
            } else {
                window.location.href = "/"; // Redirect to home after deletion
            }
        })
        .catch(error => console.error("Request error:", error));
    });

    /**
     * Apply event listeners to inputs
     */
    settingsForm.querySelectorAll("input, select").forEach(input => {
        if (input.type === "checkbox") {
            input.addEventListener("change", saveSettings);
        } else {
            input.addEventListener("input", saveSettings);
        }
    });
});
