document.addEventListener("DOMContentLoaded", () => {
    const settingsForm = document.getElementById("admin-section");
    const savePasswordBtn = document.getElementById("save-password-btn");
    const deleteScoreboardBtn = document.getElementById("delete-scoreboard-btn");
    const clearScoresBtn = document.getElementById("clear-scores-btn");
    const clearGamesBtn = document.getElementById("clear-games-btn");
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
            const newDateFormat = document.getElementById("dateformat").value;
            const newLongNameEnabled = document.getElementById("long_names_enabled").checked ? "TRUE" : "FALSE";

            const settingsData = {
                room_name: document.getElementById("room_name").value.trim(),
                dateformat: newDateFormat,
                horizontal_scroll_enabled: document.getElementById("horizontal_scroll_enabled").checked ? "TRUE" : "FALSE",
                horizontal_scroll_speed: parseInt(document.getElementById("horizontal_scroll_speed").value, 10) || 1,
                horizontal_scroll_delay: parseInt(document.getElementById("horizontal_scroll_delay").value, 10) || 60000,
                vertical_scroll_enabled: document.getElementById("vertical_scroll_enabled").checked ? "TRUE" : "FALSE",
                vertical_scroll_speed: parseInt(document.getElementById("vertical_scroll_speed").value, 10) || 3,
                vertical_scroll_delay: parseInt(document.getElementById("vertical_scroll_delay").value, 10) || 30000,
                fullscreen_enabled: document.getElementById("fullscreen_enabled").checked ? "TRUE" : "FALSE",
                long_names_enabled: newLongNameEnabled,
                public_scores_enabled: document.getElementById("public_scores").checked ? "TRUE" : "FALSE",
                public_score_entry_enabled: document.getElementById("public_score_entry_enabled").checked ? "TRUE" : "FALSE",
                api_read_access: document.getElementById("api_read_access").checked ? "TRUE" : "FALSE",
                api_write_access: document.getElementById("api_write_access").checked ? "TRUE" : "FALSE",
            };


            // Update the settings object
            settings.horizontalScrollEnabled = settingsData.horizontal_scroll_enabled === "TRUE";
            settings.horizontalScrollSpeed = settingsData.horizontal_scroll_speed;
            settings.horizontalScrollDelay = settingsData.horizontal_scroll_delay;
            settings.verticalScrollEnabled = settingsData.vertical_scroll_enabled === "TRUE";
            settings.verticalScrollSpeed = settingsData.vertical_scroll_speed;
            settings.verticalScrollDelay = settingsData.vertical_scroll_delay;
            settings.fullscreenEnabled = settingsData.fullscreen_enabled === "TRUE";

            // Dynamically update timestamps on the page
            if(settings.date_format != newDateFormat){
                settings.date_format = newDateFormat
                updateTimestamps(newDateFormat);
            }

            if(settings.longNamesEnabled != newLongNameEnabled) {
                settings.longNamesEnabled = newLongNameEnabled;
                updateLongNames(newLongNameEnabled === "TRUE");
            }

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

    function updateTimestamps(format) {
        const scoreDates = document.querySelectorAll(".score-date");
        console.log("Updating " + scoreDates.length + " Timestamps");
    
        scoreDates.forEach((element) => {
            const originalTimestamp = element.getAttribute("data-timestamp");
            if (!originalTimestamp) return;
    
            const formattedDate = formatDate(originalTimestamp, format);
            console.log("New Timestamp: ", formattedDate);
    
            element.textContent = formattedDate;
        });
    }
    
    function formatDate(timestamp, format) {
        // Directly parse raw timestamp string in the format 'YYYY-MM-DD HH:mm:ss'
        const [datePart, timePart] = timestamp.split(" ");
        const [year, month, day] = datePart.split("-").map(Number);
        const [hours, minutes] = timePart ? timePart.split(":").map(Number) : [0, 0];
    
        // Create a Date object using local time to avoid timezone shifts
        const date = new Date(year, month - 1, day, hours, minutes);
    
        const dayFormatted = String(date.getDate()).padStart(2, "0");
        const monthFormatted = String(date.getMonth() + 1).padStart(2, "0");
        const yearFormatted = date.getFullYear();
        const hoursFormatted = String(date.getHours()).padStart(2, "0");
        const minutesFormatted = String(date.getMinutes()).padStart(2, "0");
    
        switch (format) {
            case "MM/DD/YYYY":
                return `${monthFormatted}/${dayFormatted}/${yearFormatted}`;
            case "DD/MM/YYYY":
                return `${dayFormatted}/${monthFormatted}/${yearFormatted}`;
            case "YYYY/MM/DD":
                return `${yearFormatted}/${monthFormatted}/${dayFormatted}`;
            case "YYYY/DD/MM":
                return `${yearFormatted}/${dayFormatted}/${monthFormatted}`;
            case "MM/DD/YYYY HH:mm":
                return `${monthFormatted}/${dayFormatted}/${yearFormatted} ${hoursFormatted}:${minutesFormatted}`;
            case "DD/MM/YYYY HH:mm":
                return `${dayFormatted}/${monthFormatted}/${yearFormatted} ${hoursFormatted}:${minutesFormatted}`;
            case "YYYY/MM/DD HH:mm":
                return `${yearFormatted}/${monthFormatted}/${dayFormatted} ${hoursFormatted}:${minutesFormatted}`;
            case "YYYY/DD/MM HH:mm":
                return `${yearFormatted}/${dayFormatted}/${monthFormatted} ${hoursFormatted}:${minutesFormatted}`;
            default:
                return `${monthFormatted}/${dayFormatted}/${yearFormatted}`; // Default fallback
        }
    }

    function updateLongNames(isEnabled) {
        const scorePlayerNameElements = document.querySelectorAll(".score-player-name");
    
        console.log("isEnabled: ", isEnabled);
    
        scorePlayerNameElements.forEach((element) => {
            const defaultAlias = element.getAttribute("data-default-alias") || "";
            const fullName = element.getAttribute("data-full-name") || "";
    
            // Set content based on the toggle
            const newContent = isEnabled ? fullName : defaultAlias;
    
            console.log("newContent: ", newContent);
    
            // Only update if there's an actual change
            const currentText = element.innerText || element.textContent;
            if (currentText.trim() !== newContent) {
                console.log("Updated Element");
    
                // Clear inner HTML to remove existing spans and styles
                element.innerHTML = "";
    
                // Create a new span element for text fitting
                const span = document.createElement("span");
                span.classList.add("textFitted");
                span.style.display = "inline-block";
                span.textContent = newContent;
    
                // Append the new span
                element.appendChild(span);
            }
        });

        textFit(document.getElementsByClassName('score-player-name'));
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
     * Clear Scores functionality
     */
    clearScoresBtn.addEventListener("click", () => {
        if (!confirm("Are you sure you want to clear all scores from this scoreboard? This action cannot be undone!")) {
            return;
        }

        fetch(`/api/v1/scoreboards/${roomID}/scores`, { method: "DELETE" })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error("Error deleting scores:", data.error);
                alert("Failed to delete scores.");
            } else {
                window.location.reload();
            }
        })
        .catch(error => console.error("Request error:", error));
    });

    /**
     * Clear Games functionality
     */
    clearGamesBtn.addEventListener("click", () => {
        if (!confirm("Are you sure you want to clear all games from this scoreboard? This action cannot be undone!")) {
            return;
        }

        fetch(`/api/v1/scoreboards/${roomID}/games`, { method: "DELETE" })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error("Error deleting games:", data.error);
                alert("Failed to delete games.");
            } else {
                window.location.reload();
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
