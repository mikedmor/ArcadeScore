document.addEventListener("DOMContentLoaded", () => {
    const settingsForm = document.getElementById("admin-section");
    const savePasswordBtn = document.getElementById("save-password-btn");
    const deleteScoreboardBtn = document.getElementById("delete-scoreboard-btn");

    if (!roomID) {
        console.error("Room ID not found, unable to save settings.");
        return;
    }

    /**
     * Collect settings data and send API request
     */
    function saveSettings() {
        const settingsData = {
            room_name: document.getElementById("room_name").value.trim(),
            dateformat: document.getElementById("dateformat").value,
            horizontal_scroll_enabled: document.getElementById("horizontal_scroll_enabled").checked,
            horizontal_scroll_speed: parseInt(document.getElementById("horizontal_scroll_speed").value, 10) || 3,
            horizontal_scroll_delay: parseInt(document.getElementById("horizontal_scroll_delay").value, 10) || 2000,
            vertical_scroll_enabled: document.getElementById("vertical_scroll_enabled").checked,
            vertical_scroll_speed: parseInt(document.getElementById("vertical_scroll_speed").value, 10) || 3,
            vertical_scroll_delay: parseInt(document.getElementById("vertical_scroll_delay").value, 10) || 2000,
            fullscreen_enabled: document.getElementById("fullscreen_enabled").checked,
            text_autofit_enabled: document.getElementById("text_autofit_enabled").checked,
            long_names_enabled: document.getElementById("long_names_enabled").checked,
            public_scores_enabled: document.getElementById("public_scores").checked,
            public_score_entry_enabled: document.getElementById("public_score_entry_enabled").checked,
            api_read_access: document.getElementById("api_read_access").checked,
            api_write_access: document.getElementById("api_write_access").checked,
        };

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
                alert("Settings saved!");
            }
        })
        .catch(error => console.error("Request error:", error));
    }

    /**
     * Save password functionality
     */
    savePasswordBtn.addEventListener("click", () => {
        const password = document.getElementById("password").value.trim();
        if (!password) {
            alert("Please enter a new password.");
            return;
        }

        fetch(`/api/v1/settings/${roomID}/password`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ password }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error("Error saving password:", data.error);
                alert("Failed to save password.");
            } else {
                alert("Password updated successfully!");
                document.getElementById("password").value = "";
            }
        })
        .catch(error => console.error("Request error:", error));
    });

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
     * Listen for changes in the admin settings form
     */
    settingsForm.querySelectorAll("input, select").forEach(input => {
        input.addEventListener("change", saveSettings);
    });
});
