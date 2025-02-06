import { fetchGamesAndScores, updateStylesMenu } from '../autoUpdate.js';

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
                body: JSON.stringify({ presetID })
            });

            if (!response.ok) throw new Error("Failed to apply preset to all games");

            alert("Preset applied to all games!");
            fetchGamesAndScores(); // Refresh game styles in UI
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
                body: JSON.stringify({ presetID })
            });

            if (!response.ok) throw new Error("Failed to apply preset to global");

            alert("Preset applied to global styles!");
            updateStylesMenu();  // Refresh global styles in UI
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
                body: JSON.stringify({ presetID })
            });

            if (!response.ok) throw new Error("Failed to apply preset to both global and all games");

            alert("Preset applied to both global and all games!");
            updateStylesMenu();   // Update global styles
            fetchGamesAndScores(); // Refresh game styles
        } catch (error) {
            console.error("Error applying preset to both:", error);
        }
    });

    // Apply preset to a specific game
    document.getElementById("apply-game-preset").addEventListener("click", async () => {
        const gameID = gameSelector.value;
        const presetID = gamePresetSelector.value;
        if (!gameID || !presetID) return alert("Select a game and a preset.");

        await fetch(`/api/v1/style/apply-to-game`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ gameID, presetID })
        });

        alert("Preset applied to selected game!");
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
            alert("Copied to all games!");
            fetchGamesAndScores(); // Refresh UI
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
                body: JSON.stringify({ cssBody, cssCard })
            });

            alert("Global style saved!");

            // Re-apply styles after saving
            document.querySelectorAll(".game-container").forEach(container => {
                container.style = cssBody || "";
            });

            // Game card styles will be handled dynamically in `updateGameList`
            fetchGamesAndScores(); // Refresh UI to reapply changes

        } catch (error) {
            console.error("Error saving global style:", error);
        }
    });

    // Save the current game as a new preset
    savePresetBtn.addEventListener("click", async () => {
        const gameID = gameSelector.value;
        if (!gameID) return alert("Select a game to save as a preset.");

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
                overwrite = confirm(`A preset named "${presetName}" already exists. Do you want to overwrite it?`);
                if (!overwrite) return;
            }

            // Save or overwrite the preset
            await fetch(`/api/v1/style/save-preset`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ gameID, presetName, overwrite })
            });

            alert(`Preset ${overwrite ? "updated" : "saved"} successfully!`);
            updateStylesMenu();  // Update preset dropdowns immediately
        } catch (error) {
            console.error("Error saving preset:", error);
            alert("Failed to save preset.");
        }
    });

    // Load games on page load
    loadGames();
    loadGlobalStyles();
    loadPresets();
});
