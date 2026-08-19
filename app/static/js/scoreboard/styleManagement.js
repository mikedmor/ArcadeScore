import { showToast, showConfirm } from '../utils.js';

document.addEventListener("DOMContentLoaded", () => {
    const gameSelector = document.getElementById("game-selector");
    const presetSelector = document.getElementById("preset-selector");
    const gamePresetSelector = document.getElementById("game-preset-selector");
    const savePresetBtn = document.getElementById("save-as-preset");

    const copyStyleBtn = document.getElementById("copy-style-all");
    const saveGlobalStyleBtn = document.getElementById("save-global-style");

    const cssBodyField = document.getElementById("css-body");
    const cssCardField = document.getElementById("css-card");

    // Fetch games for the dropdown
    async function loadGames() {
        try {
            const response = await fetch(`/api/${user}`);
            if (!response.ok) throw new Error("Failed to fetch games");
            const games = await response.json();

            gameSelector.innerHTML = `<option value="">Select a Game</option>`;
            games.forEach(game => {
                const option = document.createElement("option");
                option.value = game.gameID;
                option.textContent = game.gameName;
                gameSelector.appendChild(option);
            });
        } catch (error) {
            console.error("Error loading games:", error);
        }
    }

    // Fetch presets and populate dropdowns
    async function loadPresets() {
        try {
            const response = await fetch(`/api/v1/style/presets`);
            if (!response.ok) throw new Error("Failed to load presets");

            const presets = await response.json();
            presetSelector.innerHTML = `<option value="" selected>-- Select Preset --</option>`;
            gamePresetSelector.innerHTML = `<option value="" selected>-- Select Preset --</option>`;

            presets.forEach(preset => {
                const option = document.createElement("option");
                option.value = preset.id;
                option.textContent = preset.name;
                presetSelector.appendChild(option);
                gamePresetSelector.appendChild(option.cloneNode(true));
            });

        } catch (error) {
            console.error("Error loading presets:", error);
        }
    }

    // Fetch and apply global styles on page load
    async function loadGlobalStyles() {
        try {
            const response = await fetch("/api/v1/style/global");
            if (!response.ok) throw new Error("Failed to fetch global styles");
            const styles = await response.json();

            // Populate the input fields
            cssBodyField.value = styles.css_body || "";
            cssCardField.value = styles.css_card || "";

            // Apply styles to the game-container only
            document.querySelectorAll(".game-container").forEach(container => {
                container.style = styles.css_body || "";
            });

            // We will now handle game-card styles dynamically in `updateGameList`
        } catch (error) {
            console.error("Error loading global styles:", error);
        }
    }

    // Apply preset to all games
    document.getElementById("apply-preset-all").addEventListener("click", async () => {
        const presetID = document.getElementById("preset-selector").value;
        if (!presetID) return;

        try {
            const response = await fetch("/api/v1/style/apply-to-all", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ presetID, roomID })
            });

            if (!response.ok) throw new Error("Failed to apply preset to all games");

            showToast("Preset applied to all games!", { type: "success" });
        } catch (error) {
            console.error("Error applying preset to all games:", error);
        }
    });

    // Apply preset to global styles
    document.getElementById("apply-preset-global").addEventListener("click", async () => {
        const presetID = document.getElementById("preset-selector").value;
        if (!presetID) return;

        try {
            const response = await fetch("/api/v1/style/apply-global", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ presetID, roomID })
            });

            if (!response.ok) throw new Error("Failed to apply preset to global");

            showToast("Preset applied to global styles!", { type: "success" });
        } catch (error) {
            console.error("Error applying preset to global:", error);
        }
    });

    // Apply preset to both games and global
    document.getElementById("apply-preset-both").addEventListener("click", async () => {
        const presetID = document.getElementById("preset-selector").value;
        if (!presetID) return;

        try {
            const response = await fetch("/api/v1/style/apply-both", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ presetID, roomID })
            });

            if (!response.ok) throw new Error("Failed to apply preset to both global and all games");

            showToast("Preset applied to both global and all games!", { type: "success" });
        } catch (error) {
            console.error("Error applying preset to both:", error);
        }
    });

    // Apply preset to a specific game
    document.getElementById("apply-game-preset").addEventListener("click", async () => {
        const gameID = gameSelector.value;
        const presetID = gamePresetSelector.value;
        if (!gameID || !presetID) return showToast("Select a game and a preset.", { type: "error" });

        await fetch(`/api/v1/style/apply-preset`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ gameID, presetID })
        });

        showToast("Preset applied to selected game!", { type: "success" });
    });

    // Copy Style to All Games
    copyStyleBtn.addEventListener("click", async () => {
        const gameID = gameSelector.value;
        if (!gameID) return;

        try {
            await fetch(`/api/v1/style/copy-to-all`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ gameID })
            });
            showToast("Copied to all games!", { type: "success" });
        } catch (error) {
            console.error("Error copying style:", error);
        }
    });

    // Save Global Style
    saveGlobalStyleBtn.addEventListener("click", async () => {
        const cssBody = cssBodyField.value;
        const cssCard = cssCardField.value;

        try {
            await fetch(`/api/v1/style/save-global`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ cssBody, cssCard, roomID })
            });

            showToast("Global style saved!", { type: "success" });

            // Re-apply styles after saving
            document.querySelectorAll(".game-container").forEach(container => {
                container.style = cssBody || "";
            });

        } catch (error) {
            console.error("Error saving global style:", error);
        }
    });

    // Save the current game as a new preset
    savePresetBtn.addEventListener("click", async () => {
        const gameID = gameSelector.value;
        if (!gameID) return showToast("Select a game to save as a preset.", { type: "error" });

        const presetName = prompt("Enter a name for this preset:");
        if (!presetName) return;

        try {
            // Fetch existing presets
            const response = await fetch(`/api/v1/style/presets`);
            if (!response.ok) throw new Error("Failed to fetch presets.");
            const presets = await response.json();

            // Check if the preset name already exists
            const existingPreset = presets.find(preset => preset.name.toLowerCase() === presetName.toLowerCase());

            let overwrite = false;
            if (existingPreset) {
                overwrite = await showConfirm(`A preset named "${presetName}" already exists. Do you want to overwrite it?`, { danger: true });
                if (!overwrite) return;
            }

            // Save or overwrite the preset
            await fetch(`/api/v1/style/save-preset`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ gameID, presetName, overwrite })
            });

            showToast(`Preset ${overwrite ? "updated" : "saved"} successfully!`, { type: "success" });
        } catch (error) {
            console.error("Error saving preset:", error);
            showToast("Failed to save preset.", { type: "error" });
        }
    });

    // Load games on page load
    loadGames();
    loadGlobalStyles();
    loadPresets();
});
