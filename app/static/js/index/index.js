import { fetchVPinData } from "../utils.js";

// Fetch and display scoreboards
export function loadScoreboards() {
    const scoreboardList = document.getElementById("scoreboard-list");
    fetch("/api/v1/scoreboards")
        .then((response) => response.json())
        .then((scoreboards) => {
            if (scoreboards.length === 0) {
                scoreboardList.innerHTML = "<p>No scoreboards available.</p>";
                return;
            }

            scoreboardList.innerHTML = scoreboards
                .map(
                    (sb) =>
                        `<div class="scoreboard-card" onclick="location.href='/${sb.user}'">
                    <div class="scoreboard-image" style="background: linear-gradient(to right, ${generateColorGradient(
                            sb.game_colors
                        )});">
                        <div class="scoreboard-title">${sb.room_name}</div>
                        <div class="scoreboard-info">
                            <p><strong>${sb.num_games}</strong> Games</p>
                            <p><strong>${sb.num_scores}</strong> Scores</p>
                        </div>
                    </div>
                </div>`
                )
                .join("");
        })
        .catch((error) => {
            scoreboardList.innerHTML = "<p>Error loading scoreboards.</p>";
            console.error("Error fetching scoreboards:", error);
        });
}

// Generate color gradient based on game colors
function generateColorGradient(colors) {
    if (!colors || colors.length === 0) return "#444";
    return colors.join(", ");
}

document.addEventListener("DOMContentLoaded", () => {
    const modal = document.getElementById("create-modal");
    const modalContent = document.querySelector(".modal-content");
    const steps = document.querySelectorAll(".wizard-step");
    const wizardTitle = document.getElementById("wizard-title");

    const nextBtn = document.getElementById("next-step-btn");
    const prevBtn = document.getElementById("prev-step-btn");
    const finishBtn = document.getElementById("finish-setup-btn");
    const closeModalBtn = document.getElementById("close-modal-btn");
    const createScoreboardBtn = document.getElementById("create-scoreboard-btn");

    const vpinUrlContainer = document.getElementById("vpin-url-container");
    const enableVPinCheckbox = document.getElementById("enable-vpin");
    const vpinApiUrlInput = document.getElementById("vpin-api-url");
    const vpinApiError = document.getElementById("vpin-api-error");
    const testVPinBtn = document.getElementById("test-vpin-api-btn");

    const modalLoading = document.getElementById("modal-loading");

    let currentStep = 0;
    let vpinTestSuccessful = false;
    let selectedGames = [];

    function showStep(index) {
        steps.forEach((step, i) => step.classList.toggle("hidden", i !== index));
        prevBtn.classList.toggle("hidden", index === 0);
        nextBtn.classList.toggle("hidden", index >= steps.length - 1);
        finishBtn.classList.toggle("hidden", index !== steps.length - 1);

        // Set title based on step
        const titles = [
            "Create a New Scoreboard",
            "Enable Integrations",
            "Select Players",
            "Select Games",
            "Select Theme Preset",
            "Setup Complete",
        ];
        wizardTitle.textContent = titles[index];

        currentStep = index;
    }

    function loadVPinPlayers(vpinUrl) {
        fetchVPinData(
            "api/v1/players",
            vpinUrl,
            (vpinPlayers) => {
                fetch("/api/v1/players")
                    .then((response) => response.json())
                    .then((existingPlayers) => {
                        const playerList = document.getElementById("vpin-players-list");

                        playerList.innerHTML = vpinPlayers
                            .map((player) => {
                                const existing = existingPlayers.find(
                                    (p) => p.default_alias === player.initials
                                );
                                const linkedVPin = existing
                                    ? existing.vpin.find((vp) => vp.vpin_player_id === player.id)
                                    : null;

                                if (linkedVPin) {
                                    // Already linked
                                    return `<li>
                                    <div class="player-row">
                                        <div class="player-action"></div>
                                        <div class="player-info" 
                                             data-full-name="${existing.full_name
                                        }" 
                                             data-aliases="${existing.aliases.join(
                                            ","
                                        )}" 
                                             data-initials="${existing.default_alias
                                        }">
                                            <span>${existing.full_name
                                        } (${existing.aliases.join(
                                            ","
                                        )})</span>
                                            <div class="change-summary"><strong>No changes required</strong></div>
                                        </div>
                                    </div>
                                </li>`;
                                } else if (existing) {
                                    // Existing player with updates or not linked
                                    const updates = [
                                        `<span>+ New VPin Player ID: <strong>${player.id}</strong></span>`,
                                    ];
                                    if (!existing.aliases.includes(player.initials)) {
                                        updates.push(
                                            `<span>+ Initials: <strong>${player.initials}</strong></span>`
                                        );
                                    }
                                    if (existing.full_name !== player.name) {
                                        updates.push(
                                            `<span>+ Name update: <strong>${player.name}</strong></span>`
                                        );
                                    }

                                    return `<li>
                                    <div class="player-row">
                                        <div class="player-action">
                                            <button class="link-player btn" 
                                                    data-vpin="${player.id}" 
                                                    data-arcade="${existing.id
                                        }" 
                                                    data-full-name="${player.name
                                        }" 
                                                    data-aliases="${player.initials
                                        }">
                                                Link
                                            </button>
                                        </div>
                                        <div class="player-info"
                                             data-full-name="${existing.full_name
                                        }" 
                                             data-aliases="${existing.aliases.join(
                                            ","
                                        )}" 
                                             data-initials="${existing.default_alias
                                        }">
                                            <span>${existing.full_name
                                        } (${existing.aliases.join(
                                            ","
                                        )})</span>
                                            <div class="change-summary">${updates.join(
                                            "<br>"
                                        )}</div>
                                        </div>
                                    </div>
                                </li>`;
                                } else {
                                    // New player to be added
                                    return `<li>
                                    <div class="player-row">
                                        <div class="player-action">
                                            <button class="add-player btn" 
                                                    data-vpin="${player.id}" 
                                                    data-full-name="${player.name}" 
                                                    data-aliases="${player.initials}">
                                                Add
                                            </button>
                                        </div>
                                        <div class="player-info"
                                             data-full-name="${player.name}" 
                                             data-aliases="${player.initials}" 
                                             data-initials="${player.initials}">
                                            <span>${player.name} (${player.initials})</span>
                                            <div class="change-summary">
                                                <span>+ New Player Name: <strong>${player.name}</strong></span><br>
                                                <span>+ New VPin Player ID: <strong>${player.id}</strong></span><br>
                                                <span>+ Initials: <strong>${player.initials}</strong></span>
                                            </div>
                                        </div>
                                    </div>
                                </li>`;
                                }
                            })
                            .join("");

                        // Add event listeners for "Add" buttons
                        const addButtons = document.querySelectorAll(".add-player");
                        addButtons.forEach((button) => {
                            button.addEventListener("click", function () {
                                const vpinPlayerId = this.dataset.vpin;
                                const fullName = this.dataset.fullName;
                                const initials = this.dataset.aliases;
                                const aliases = [initials];

                                this.disabled = true;
                                this.textContent = "Adding...";
                                // Call the new API for VPin Studio imports
                                fetch("/api/v1/players/vpin/import", {
                                    method: "POST",
                                    headers: { "Content-Type": "application/json" },
                                    body: JSON.stringify({
                                        full_name: fullName,
                                        default_alias: initials,
                                        aliases: aliases,
                                        vpin_player_id: vpinPlayerId,
                                        vpin_url: vpinUrl,
                                    }),
                                })
                                    .then((response) => response.json())
                                    .then((data) => {
                                        if (data.success) {
                                            this.style.display = "none";
                                            this.parentElement.parentElement.querySelector(
                                                ".change-summary"
                                            ).innerHTML = "<strong>No changes required</strong>";
                                        } else {
                                            this.textContent = "Add";
                                            this.disabled = false;
                                            alert("Failed to add player: " + data.error);
                                        }
                                    })
                                    .catch((error) => {
                                        this.textContent = "Add";
                                        this.disabled = false;
                                        alert("Failed to add player: " + error.message);
                                    });
                            });
                        });

                        // Add event listeners for "Link" buttons
                        const linkButtons = document.querySelectorAll(".link-player");
                        linkButtons.forEach((button) => {
                            button.addEventListener("click", function () {
                                const vpinPlayerId = this.dataset.vpin;
                                const arcadePlayerId = this.dataset.arcade;
                                const fullName = this.dataset.fullName;
                                const aliases = this.dataset.aliases
                                    .split(",")
                                    .map((alias) => alias.trim());

                                this.disabled = true;
                                this.textContent = "Linking...";

                                // Call API to link players and update their details
                                fetch("/api/v1/players/vpin", {
                                    method: "POST",
                                    headers: { "Content-Type": "application/json" },
                                    body: JSON.stringify({
                                        server_url: vpinUrl,
                                        players: [
                                            {
                                                vpin_player_id: vpinPlayerId,
                                                arcadescore_player_id: arcadePlayerId,
                                                full_name: fullName,
                                                aliases: aliases,
                                            },
                                        ],
                                    }),
                                })
                                    .then((response) => response.json())
                                    .then((data) => {
                                        if (data.message) {
                                            this.style.display = "none";
                                            this.parentElement.parentElement.querySelector(
                                                ".player-info"
                                            ).innerHTML = `
                                                <span>${fullName} (${aliases.join(
                                                ","
                                            )})</span>
                                                <div class="change-summary"><strong>No changes required</strong></div>
                                            `;
                                        } else {
                                            this.textContent = "Link";
                                            this.disabled = false;
                                            alert("Failed to link player: " + data.error);
                                        }
                                    })
                                    .catch((error) => {
                                        this.textContent = "Link";
                                        this.disabled = false;
                                        alert("Failed to link player: " + error.message);
                                    });
                            });
                        });
                    })
                    .catch((error) =>
                        console.error("Error loading ArcadeScore players:", error)
                    );
            },
            (error) => alert(error)
        );
    }

    function loadVPinGames(vpinUrl) {
        fetchVPinData(
            "api/v1/games",
            vpinUrl,
            (vpinGamesData) => {
                const gameList = document.getElementById("vpin-games-list");
                const selectAllCheckbox = document.getElementById("select-all-games");

                if (!vpinGamesData || vpinGamesData.length === 0) {
                    gameList.innerHTML = "<p>No games found.</p>";
                    return;
                }

                // Filter out games that are disabled or have no highscoreType
                const filteredGames = vpinGamesData.filter(
                    (game) =>
                        game.highscoreType &&
                        game.highscoreType.trim() !== "" &&
                        !game.disabled
                );

                if (!filteredGames || filteredGames.length === 0) {
                    gameList.innerHTML = "<p>No high-score capable games available.</p>";
                    selectAllCheckbox.style.display = "none";
                    return;
                }

                selectAllCheckbox.style.display = "inline";
                selectAllCheckbox.checked = false;
                gameList.innerHTML = filteredGames
                    .map((game) => {
                        const gameId = game.id;
                        const gameName = game.gameDisplayName || "Unknown";
                        const gameFile = game.gameFileName || "Unknown";
                        const gameRom = game.rom || "Unknown";
                        const version = game.version || "Unknown";
                        const highscoreType = game.highscoreType || "Unknown";
                        const extTableId = game.extTableId || "";
                        const extTableVersionId = game.extTableVersionId || "";

                        return `<li>
                        <div class="game-row">
                            <div class="game-action">
                                <input type="checkbox" class="import-game" 
                                       data-game-id="${gameId}" 
                                       data-game-name="${gameName}" 
                                       data-game-file="${gameFile}" 
                                       data-game-rom="${gameRom}" 
                                       data-game-version="${version}"
                                       data-game-ext-table-id="${extTableId}"
                                       data-game-ext-table-version-id="${extTableVersionId}">
                            </div>
                            <div class="game-info">
                                <span><strong>${gameName}</strong></span>
                                <div class="change-summary">
                                    <span>(${gameFile})</span><br>
                                    <span>Game ROM: <strong>${gameRom}</strong></span><br>
                                    <span>Version: <strong>${version}</strong></span><br>
                                    <span>Highscore Type: <strong>${highscoreType}</strong></span>
                                </div>
                            </div>
                        </div>
                    </li>`;
                    })
                    .join("");

                // Attach event listeners to checkboxes for tracking selections
                const checkboxes = document.querySelectorAll(".import-game");
                checkboxes.forEach((checkbox) => {
                    checkbox.addEventListener("change", function () {
                        const gameData = {
                            id: this.dataset.gameId,
                            name: this.dataset.gameName,
                            file: this.dataset.gameFile,
                            rom: this.dataset.gameRom,
                            version: this.dataset.gameVersion,
                            extTableId: this.dataset.gameExtTableId,
                            extTableVersionId: this.dataset.gameExtTableVersionId,
                        };

                        if (this.checked) {
                            selectedGames.push(gameData);
                        } else {
                            selectedGames = selectedGames.filter(
                                (game) => game.id !== gameData.id
                            );
                        }

                        // Update "Select All" checkbox state
                        selectAllCheckbox.checked =
                            checkboxes.length === selectedGames.length;
                    });
                });

                // "Select All" event listener
                selectAllCheckbox.addEventListener("change", function () {
                    if (selectAllCheckbox.checked) {
                        checkboxes.forEach((checkbox) => {
                            checkbox.checked = true;
                            checkbox.dispatchEvent(new Event("change")); // Trigger change event
                        });
                        selectAllCheckbox.checked = true;
                    } else {
                        checkboxes.forEach((checkbox) => {
                            checkbox.checked = false;
                            checkbox.dispatchEvent(new Event("change")); // Trigger change event
                        });
                        selectAllCheckbox.checked = false;
                    }
                });
            },
            (error) => alert(error)
        );
    }

    function vps_toggle() {
        if (!enableVPinCheckbox.checked || vpinTestSuccessful) {
            nextBtn.disabled = false;
        } else {
            nextBtn.disabled = true;
        }
    }

    function resetModal() {
        modalContent.classList.remove("hidden");
        document.getElementById("modal-loading").classList.add("hidden");
    }

    nextBtn.addEventListener("click", () => {
        if (currentStep === 0) {
            // Require a Scoreboard Name
            const scoreboardName = document
                .getElementById("scoreboard-name")
                .value.trim();
            if (!scoreboardName) {
                alert("Please enter a name for the scoreboard.");
                return;
            }
        }

        if (currentStep === 1) {
            loadVPinPlayers(vpinApiUrlInput.value.trim());
        }

        if (currentStep === 2) {
            loadVPinGames(vpinApiUrlInput.value.trim());
        }

        if (currentStep === 3) {
            if (selectedGames.length === 0) {
                alert("Please select at least one game.");
                return;
            }

            // Fetch and populate presets in Step 5 dropdown
            fetch("/api/v1/style/presets")
                .then((response) => response.json())
                .then((presets) => {
                    const presetDropdown = document.getElementById("selected-preset");
                    presetDropdown.innerHTML =
                        "<option selected>-- Select Preset --</option>"; // Reset options

                    presets.forEach((preset) => {
                        const option = document.createElement("option");
                        option.value = preset.id;
                        option.textContent = preset.name;
                        presetDropdown.appendChild(option);
                    });
                })
                .catch((error) => {
                    console.error("Failed to load presets:", error);
                    alert("Error fetching presets.");
                });
        }

        // Ensure a preset is selected before proceeding from Step 5
        if (currentStep === 4) {
            const presetDropdown = document.getElementById("selected-preset");
            const selectedPreset = presetDropdown.value;

            if (!selectedPreset || selectedPreset === "-- Select Preset --") {
                alert("Please select a preset.");
                return;
            }
        }

        showStep(currentStep + 1);
    });

    prevBtn.addEventListener("click", () => {
        if (!document.getElementById("enable-vpin").checked && currentStep >= 4) {
            showStep(currentStep - 3);
        } else {
            showStep(currentStep - 1);
        }
    });

    finishBtn.addEventListener("click", () => {
        const scoreboardName = document.getElementById("scoreboard-name").value.trim();
        const enableVPin = document.getElementById("enable-vpin").checked;
        const vpinApiUrl = document.getElementById("vpin-api-url").value.trim();
        const selectedPreset = document.getElementById("selected-preset").value;

        const requestData = {
            scoreboard_name: scoreboardName,
            vpin_api_enabled: enableVPin,
            vpin_api_url: enableVPin ? vpinApiUrl : null,
            vpin_games: selectedGames,
            preset_id: selectedPreset,
        };

        // Hide modal contents & show loading screen
        modalContent.classList.add("hidden");
        modalLoading.classList.remove("hidden");

        fetch("/api/v1/scoreboards", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(requestData),
        })
            .catch(() => {
                alert("Failed to start scoreboard creation.");
                resetModal();
            });
    });

    createScoreboardBtn.addEventListener("click", () => {
        showStep(0);
        modal.style.display = "flex";
        modal.classList.remove("hidden");
    });

    closeModalBtn.addEventListener("click", () => {
        modal.style.display = "none";
        modal.classList.add("hidden");
    });

    // Toggle VPin API input & lock Next button when checked
    enableVPinCheckbox.addEventListener("change", () => {
        vpinUrlContainer.classList.toggle("hidden", !enableVPinCheckbox.checked);
        vpinTestSuccessful = false; // Reset test state
        if (!enableVPinCheckbox.checked) {
            vpinApiError.textContent = "";
            vpinApiError.style.color = "blue";
        }
        vps_toggle();
    });

    // Disable "Next" when user modifies URL
    vpinApiUrlInput.addEventListener("input", () => {
        vpinTestSuccessful = false;
        vpinApiError.textContent = "";
        vps_toggle();
    });

    testVPinBtn.addEventListener("click", () => {
        let apiUrl = vpinApiUrlInput.value.trim();

        if (!apiUrl) {
            vpinApiError.textContent = "Please enter a valid VPin API URL.";
            vpinApiError.style.color = "red";
            return;
        }

        if (!apiUrl.endsWith("/")) {
            apiUrl += "/";
        }

        vpinApiError.textContent = "Checking VPin API connection...";
        vpinApiError.style.color = "blue";
        nextBtn.disabled = true; // Lock Next until test completes

        fetchVPinData(
            "api/v1/system/startupTime",
            apiUrl,
            (data) => {
                console.log("VPin API connected. Startup time:", data);
                vpinApiError.textContent = "VPin API connection successful!";
                vpinApiError.style.color = "green";
                vpinTestSuccessful = true;
                vps_toggle();
            },
            (error) => {
                vpinApiError.textContent = error;
                vpinApiError.style.color = "red";
                vpinTestSuccessful = false;
                vps_toggle();
            }
        );
    });

    // Close Modal when clicking outside of it
    window.addEventListener("click", (event) => {
        if (event.target === modal && !document.getElementById("modal-loading").classList.contains("hidden")) {
            // Prevent closing if the loading screen is active
            return;
        }
    
        if (event.target === modal) {
            modal.style.display = "none";
            modal.classList.add("hidden");
        }
    });

    // Load scoreboards on page load
    loadScoreboards();
});
