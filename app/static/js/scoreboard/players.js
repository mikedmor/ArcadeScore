document.addEventListener("DOMContentLoaded", () => {
    const playerSection = document.getElementById("players-section");
    const playerViewSection = document.getElementById("player-view-section");
    const playerFormSection = document.getElementById("player-form-section");
    const playerList = document.getElementById("player-list");

    const playerViewIcon = document.getElementById("player-view-icon");
    const playerViewName = document.getElementById("player-view-name");
    const playerViewAliases = document.getElementById("player-view-aliases");
    const playerScoreList = document.getElementById("player-score-list");
    const playerViewWinsLosses = document.getElementById("player-view-wins-losses");

    const addPlayerButton = document.getElementById("add-player-button");
    const editPlayerButton = document.getElementById("edit-player-button");
    const hidePlayerButton = document.getElementById("hide-player-button");

    const playerForm = document.getElementById("player-form");
    const playerFormTitle = document.getElementById("player-form-title");
    const playerIdInput = document.getElementById("player_id");
    const fullNameInput = document.getElementById("full_name");
    const playerIconInput = document.getElementById("player_icon");
    const longNamesEnabledInput = document.getElementById("long_names_enabled");
    const mergePlayerSelect = document.getElementById("merge_player");
    const deletePlayerButton = document.getElementById("delete_player_button");

    const aliasesContainer = document.getElementById("aliases-container");
    const addAliasButton = document.getElementById("add-alias-button");

    let existingAliases = [""];
    let defaultAlias = "";

    // Open Player Form when clicking "Add Player"
    addPlayerButton.addEventListener("click", () => {
        playerSection.classList.remove("active");
        playerFormTitle.textContent = "Add New Player";

        playerForm.reset();

        existingAliases = [""];
        aliasesContainer.innerHTML = ""; // Clear existing aliases
        addAliasInput("", true); // Add a blank alias input

        // Hide "Merge With" field and delete button when adding a new player
        document.getElementById("merge-player-wrapper").style.display = "none";
        deletePlayerButton.style.display = "none";

        playerFormSection.classList.add("active"); 
    });

    // Open Player View when clicking a player
    playerList.addEventListener("click", (event) => {
        const playerItem = event.target.closest(".player-list-card");
        if (!playerItem) return;

        const playerId = playerItem.dataset.id;

        fetch(`/api/v1/players/${playerId}`)
            .then(response => response.json())
            .then(player => {
                playerViewSection.dataset.id = player.id;
                playerViewName.textContent = player.full_name;
                playerViewIcon.src = player.icon || "/static/images/avatars/default-avatar.png";
                playerViewAliases.textContent = player.aliases.join(", ") || "None";

                // Display Scores
                playerScoreList.innerHTML = player.scores.length
                    ? player.scores.map(score => `
                        <li>
                            <strong>${score.game_name}:</strong> ${score.score}
                            <span class="date">(${score.timestamp})</span>
                        </li>`).join("")
                    : "<li>No scores available.</li>";

                // Wins / Losses
                playerViewWinsLosses.textContent = `${player.total_wins} Wins / ${player.total_losses} Losses`;

                // Show Player View, Hide Player Form
                playerViewSection.classList.add("active");
                playerFormSection.classList.remove("active");
                playerSection.classList.remove("active");
            })
            .catch(error => console.error("Error loading player data:", error));
    });

    // Open Player Form when clicking "Edit Player"
    if (editPlayerButton) {
        editPlayerButton.addEventListener("click", () => {
            const playerId = playerViewSection.dataset.id; // Get stored player ID
            if (!playerId) {
                console.error("No player ID found for editing.");
                return;
            }

            fetch(`/api/v1/players/${playerId}`)
                .then(response => response.json())
                .then(player => {
                    playerFormTitle.textContent = "Edit Player";
                    playerIdInput.value = player.id;
                    fullNameInput.value = player.full_name;
                    playerIconInput.value = player.icon || "";
                    longNamesEnabledInput.checked = player.long_names_enabled === "TRUE";

                    aliasesContainer.innerHTML = ""; // Clear existing aliases

                    // Populate aliases with radio buttons
                    player.aliases.forEach((alias, index) => {
                        addAliasInput(alias, alias === player.default_alias || index === 0);
                    });

                    // Show "Merge With" and delete options when editing
                    document.getElementById("merge-player-wrapper").style.display = "block";
                    deletePlayerButton.style.display = "block";

                    // Show Player Form and Hide Player View
                    playerFormSection.classList.add("active");
                    playerViewSection.classList.remove("active");
                })
                .catch(error => console.error("Error loading player data for edit:", error));
        });
    }

    // Hide Player
    if (hidePlayerButton) {
        hidePlayerButton.addEventListener("click", () => {
            const playerId = playerViewSection.dataset.id; // Get stored player ID
            if (!playerId) {
                console.error("No player ID found for hiding.");
                return;
            }

            fetch(`/api/v1/players/${playerId}/hide`, { method: "POST" })
                .then(() => {
                    playerViewSection.classList.remove("active");
                })
                .catch(error => console.error("Error hiding player:", error));
        });
    }

    // Delete Player
    if (deletePlayerButton) {
        deletePlayerButton.addEventListener("click", () => {
            const playerId = playerIdInput.value.trim();
            if (!playerId) {
                console.error("No player ID found for deletion.");
                return;
            }

            // Confirm before deleting
            if (!confirm(`Are you sure you want to delete this player? This action cannot be undone.`)) {
                return;
            }

            // Send DELETE request to API
            fetch(`/api/v1/players/${playerId}`, {
                method: "DELETE"
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log("Player deleted:", data);
                    playerFormSection.classList.remove("active");
                    playerSection.classList.add("active");
                } else {
                    console.error("Failed to delete player:", data.error);
                }
            })
            .catch(error => console.error("Error deleting player:", error));
        });
    }

    // Function to add an alias input dynamically
    function addAliasInput(alias = "", isDefault = false) {
        const aliasWrapper = document.createElement("div");
        aliasWrapper.classList.add("alias-wrapper");

        const radioWrapper = document.createElement("div");
        radioWrapper.classList.add("radio-wrapper");

        const aliasInput = document.createElement("input");
        aliasInput.type = "text";
        aliasInput.classList.add("alias-input");
        aliasInput.value = alias;
        aliasInput.placeholder = "Enter alias";

        const radioInput = document.createElement("input");
        radioInput.type = "radio";
        radioInput.name = "default_alias";
        radioInput.value = alias;
        radioInput.classList.add("default-alias-radio");
        if (isDefault || alias === defaultAlias) {
            radioInput.checked = true;
            defaultAlias = alias;
        }

        radioInput.addEventListener("change", () => {
            defaultAlias = radioInput.value;
        });

        const removeButton = document.createElement("button");
        removeButton.type = "button";
        removeButton.classList.add("remove-alias");
        removeButton.textContent = "✖";
        removeButton.addEventListener("click", () => {
            aliasWrapper.remove();
            refreshDefaultAlias(); // Ensure default alias is valid after removal
        });

        radioWrapper.appendChild(radioInput);
        aliasWrapper.appendChild(radioWrapper);
        aliasWrapper.appendChild(aliasInput);
        aliasWrapper.appendChild(removeButton);
        aliasesContainer.appendChild(aliasWrapper);
    }

    function refreshDefaultAlias() {
        const aliasInputs = document.querySelectorAll(".alias-input");
        const radioButtons = document.querySelectorAll(".default-alias-radio");

        if (aliasInputs.length > 0) {
            radioButtons[0].checked = true;
            defaultAlias = aliasInputs[0].value;
        } else {
            defaultAlias = "";
        }
    }

    // Event listener for adding a new alias
    addAliasButton.addEventListener("click", () => {
        addAliasInput("", existingAliases.length === 0);
    });

    // Modify form submission to include all aliases
    playerForm.addEventListener("submit", (event) => {
        event.preventDefault();
    
        const playerId = playerIdInput.value.trim();
        const formData = new FormData();
    
        formData.append("full_name", fullNameInput.value.trim());
    
        // Collect aliases
        const aliasInputs = document.querySelectorAll(".alias-input");
        const aliases = Array.from(aliasInputs)
            .map(input => input.value.trim())
            .filter(value => value !== "");
        formData.append("aliases", JSON.stringify(aliases));
    
        // Get selected default alias (ensure a valid one exists)
        const selectedDefaultAlias = document.querySelector(".default-alias-radio:checked");
        let defaultAlias = selectedDefaultAlias ? selectedDefaultAlias.value : "";
        
        if (!defaultAlias && aliases.length > 0) {
            defaultAlias = aliases[0]; // Fallback to first alias if no radio is selected
        }
        
        formData.append("default_alias", defaultAlias);
        formData.append("long_names_enabled", longNamesEnabledInput.checked ? "TRUE" : "FALSE");
    
        // Handle avatar upload
        const fileInput = document.getElementById("player-icon-upload");
        if (fileInput.files.length > 0) {
            formData.append("player_icon_file", fileInput.files[0]);
        } else if (playerIconInput.value.trim() !== "") {
            formData.append("player_icon_url", playerIconInput.value.trim());
        }
    
        console.log("Submitting:", {
            full_name: formData.get("full_name"),
            default_alias: formData.get("default_alias"),
            aliases: JSON.parse(formData.get("aliases")),
            long_names_enabled: formData.get("long_names_enabled"),
            icon: formData.get("player_icon_file") || formData.get("player_icon_url"),
        });
    
        const apiUrl = playerId ? `/api/v1/players/${playerId}` : "/api/v1/players";
        const method = playerId ? "PUT" : "POST"; // Use PUT when editing, POST when adding
    
        fetch(apiUrl, {
            method: method,
            body: formData // Send as FormData for file support
        })
        .then(response => response.json())
        .then(data => {
            console.log("Player saved:", data);
            playerFormSection.classList.remove("active");
            playerSection.classList.add("active");
        })
        .catch(error => console.error("Error saving player:", error));
    });
});
