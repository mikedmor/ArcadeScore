// autoUpdate.js
let draggedItem = null;

export async function fetchGamesAndScores() {
    try {
        const response = await fetch(`/api/${user}`);
        if (!response.ok) throw new Error("Failed to fetch games and scores");
        const gamesAndScores = await response.json();

        //console.log("gamesAndScores: ", gamesAndScores);

        updateGameList(gamesAndScores);
        updateGamesMenu(gamesAndScores);
        refreshPlayerList();
        updateStylesMenu();
    } catch (error) {
        console.error("Error fetching games and scores:", error);
    }
}

export function updateStylesMenu() {
    fetch("/api/v1/style/presets")
        .then(response => response.json())
        .then(presets => {
            const presetSelectors = document.querySelectorAll("#preset-selector, #game-preset-selector, #css_style");

            presetSelectors.forEach(selector => {
                const currentValue = selector.value; // 🔥 Save currently selected value
                
                selector.innerHTML = `<option value="">-- Select Preset --</option>`;
                
                presets.forEach(preset => {
                    const option = document.createElement("option");
                    option.value = String(preset.id);
                    option.textContent = preset.name;
                    selector.appendChild(option);
                });

                // Ensure preset options appear in the game form
                if (selector.id === "css_style") {
                    const customOption = document.createElement("option");
                    customOption.value = "_custom";
                    customOption.textContent = "-- Custom --";
                    selector.prepend(customOption);
                }

                // 🔥 Restore previously selected value if it still exists
                if ([...selector.options].some(option => option.value === currentValue)) {
                    selector.value = currentValue;
                } else {
                    console.warn(`⚠️ Previous value ${currentValue} not found in updated presets`);
                }
            });
        })
        .catch(error => console.error("Error updating styles menu:", error));

    // Fetch global styles and update the input fields
    fetch("/api/v1/style/global")
        .then(response => response.json())
        .then(styles => {
            document.getElementById("css-body").value = styles.css_body || "";
            document.getElementById("css-card").value = styles.css_card || "";

            // Apply the global styles dynamically
            document.querySelectorAll(".game-container").forEach(container => {
                container.style = styles.css_body || "";
            });
            document.querySelectorAll(".game-card").forEach(card => {
                let appliedCardStyle = styles.css_card || "";
                
                // Replace placeholders with actual game values
                appliedCardStyle = appliedCardStyle
                    .replace(/{GameBackground}/g, card.dataset.background || "")
                    .replace(/{GameColor}/g, card.dataset.color || "#FFFFFF")
                    .replace(/{GameImage}/g, card.dataset.image || "");

                card.setAttribute("style", appliedCardStyle);

                // Ensure ordering is correct
                if (card.style.order !== `${card.dataset.gameSort}`) {
                    card.style.order = `${card.dataset.gameSort}`;
                }
            });
        })
        .catch(error => console.error("Error updating global styles:", error));
}

function refreshPlayerList() {
    const playerList = document.getElementById("player-list");
    fetch("/api/v1/players")
        .then(response => response.json())
        .then(players => {
            playerList.innerHTML = players.map(player => `
                <li class="player-list-card" data-id="${player.id}">
                    <span class="player-name">${player.full_name}</span>
                    <span class="player-alias">(${player.default_alias})</span>
                </li>
            `).join("");
        })
        .catch(error => console.error("Error loading players:", error));
}

function formatDate(timestamp, format = "MM/DD/YYYY") {
    return dayjs(timestamp).format(format === "DD/MM/YYYY" ? "DD/MM/YYYY" : "MM/DD/YYYY");
}

// Update the game list in the DOM
function updateGameList(games) {
    const gameContainer = document.getElementById("gameContainer");

    fetch("/api/v1/style/global")
        .then(response => response.json())
        .then(styles => {
            const globalCardStyle = styles.css_card || "";

            // Create a Set of current game IDs in the DOM
            const existingGameIDs = new Set([...gameContainer.querySelectorAll(".game-card")].map(card => card.dataset.id));

            // Filter out hidden games
            const visibleGames = games.filter(game => game.Hidden !== "TRUE");

            // Sort games by game_sort before adding to the DOM
            visibleGames.sort((a, b) => a.GameSort - b.GameSort);

            visibleGames.forEach((game, index) => {
                let existingGameCard = document.querySelector(`.game-card[data-id="${game.gameID}"]`);

                // Remove from existing list since it's still visible
                existingGameIDs.delete(String(game.gameID));

                // Apply dynamic replacements for global card styles
                //console.log("Game:", game);
                const appliedCardStyle = globalCardStyle
                    .replace(/{GameBackground}/g, game.GameBackground || "")
                    .replace(/{GameColor}/g, game.GameColor || "#FFFFFF")
                    .replace(/{GameImage}/g, game.GameImage || "");

                if (existingGameCard) {
                    // Update text content
                    const gameTitle = existingGameCard.querySelector(".game-title");
                    if (gameTitle.textContent !== game.gameName) {
                        gameTitle.textContent = game.gameName;
                    }

                    // Update title styles
                    if (gameTitle.getAttribute("style") !== game.CSSTitle) {
                        gameTitle.setAttribute("style", game.CSSTitle);
                    }

                    // Apply dynamically generated global card styles
                    existingGameCard.setAttribute("style", appliedCardStyle);
                    existingGameCard.dataset.background = game.GameBackground;
                    existingGameCard.dataset.color = game.GameColor;
                    existingGameCard.dataset.image = game.GameImage;
                    existingGameCard.dataset.gameSort = index;

                    // Ensure ordering is correct
                    if (existingGameCard.style.order !== `${index}`) {
                        existingGameCard.style.order = `${index}`;
                    }

                    // Update game image styles
                    let gameImage = existingGameCard.querySelector("img");
                    if (game.GameImage) {
                        if (!gameImage) {
                            gameImage = document.createElement("img");
                            gameImage.src = game.GameImage;
                            gameImage.alt = game.gameName;
                            gameImage.setAttribute("style", game.CSSBox);
                            existingGameCard.prepend(gameImage);
                        } else {
                            if (gameImage.src !== game.GameImage) {
                                gameImage.src = game.GameImage;
                            }
                            if (gameImage.getAttribute("style") !== game.CSSBox) {
                                gameImage.setAttribute("style", game.CSSBox);
                            }
                        }
                    } else if (gameImage) {
                        gameImage.remove();
                    }

                    // Update Scores dynamically
                    const scoreContainer = existingGameCard.querySelector(".score-container");
                    const scoresHTML = game.scores.map((score) => {
                        const formattedDate = formatDate(score.timestamp, game.dateFormat || "MM/DD/YYYY");
                    
                        let extraFields = "";
                        if (game.ScoreType === "") {
                            extraFields = `
                                <div class="score-event">${score.event || 'N/A'}</div>
                                <div class="score-wins">${score.wins} Wins | ${score.losses} Losses</div>
                            `;
                        } else if (game.ScoreType === "hideWins") {
                            extraFields = `<div class="score-event">${score.event || 'N/A'}</div>`;
                        } else if (game.ScoreType === "hideEvent") {
                            extraFields = `<div class="score-wins">${score.wins} Wins | ${score.losses} Losses</div>`;
                        }
                    
                        return `
                            <div class="score-card" style="${game.CSSScoreCards}">
                                <div class="score-player-name" style="${game.CSSInitials}">${score.player_name}</div>
                                <div class="score-score" style="${game.CSSScores}">${score.score}</div>
                                <div class="score-date">${formattedDate}</div>
                                ${extraFields}
                            </div>
                        `;
                    }).join("") || `<div class="score-card" style="${game.CSSScoreCards}">No scores yet for this game.</div>`;

                    if (scoreContainer.innerHTML !== scoresHTML) {
                        scoreContainer.innerHTML = scoresHTML;
                    }

                } else {
                    // Create new game card if not existing
                    const newGameCard = document.createElement("div");
                    newGameCard.classList.add("game-card");
                    newGameCard.dataset.id = game.gameID;
                    
                    // Apply dynamically generated global card styles
                    newGameCard.setAttribute("style", appliedCardStyle);
                    newGameCard.style.order = `${index}`; // Set order
                    
                    newGameCard.dataset.background = game.GameBackground;
                    newGameCard.dataset.color = game.GameColor;
                    newGameCard.dataset.image = game.GameImage;

                    newGameCard.innerHTML = `
                        <span class="game-title" style="${game.CSSTitle}">${game.gameName}</span>
                        ${game.GameImage ? `<img src="${game.GameImage}" alt="${game.gameName}" style="${game.CSSBox}">` : ""}
                        <div class="score-container">
                            ${game.scores
                                .map((score) => {
                                    const formattedDate = formatDate(score.timestamp, game.dateFormat || "MM/DD/YYYY");

                                    let extraFields = "";
                                    if (game.ScoreType === "") {
                                        extraFields = `
                                            <div class="score-event">${score.event || 'N/A'}</div>
                                            <div class="score-wins">${score.wins} Wins | ${score.losses} Losses</div>
                                        `;
                                    } else if (game.ScoreType === "hideWins") {
                                        extraFields = `<div class="score-event">${score.event || 'N/A'}</div>`;
                                    } else if (game.ScoreType === "hideEvent") {
                                        extraFields = `<div class="score-wins">${score.wins} Wins | ${score.losses} Losses</div>`;
                                    }

                                    return `
                                        <div class="score-card" style="${game.CSSScoreCards}">
                                            <div class="score-player-name" style="${game.CSSInitials}">${score.player_name}</div>
                                            <div class="score-score" style="${game.CSSScores}">${score.score}</div>
                                            <div class="score-date">${formattedDate}</div>
                                            ${extraFields}
                                        </div>
                                    `;
                                })
                                .join("") || `<div class="score-card" style="${game.CSSScoreCards}">No scores yet for this game.</div>`}
                        </div>
                    `;

                    gameContainer.appendChild(newGameCard);
                }
            });

            // Remove game cards that are now hidden
            existingGameIDs.forEach(id => {
                const hiddenGameCard = document.querySelector(`.game-card[data-id="${id}"]`);
                if (hiddenGameCard) {
                    hiddenGameCard.remove();
                }
            });

            
            //Make the text fit for these elements:
            textFit(document.getElementsByClassName('game-title'), {multiLine: true})
            textFit(document.getElementsByClassName('score-player-name'));
            textFit(document.getElementsByClassName('no-scores-yet'));
        })
        .catch(error => console.error("Error loading global styles:", error));
}

// Update games in the hamburger menu
function updateGamesMenu(games) {
    const gamesMenu = document.getElementById("game-list");
    // Track existing menu items for updating or removal
    const existingMenuItems = Array.from(gamesMenu.querySelectorAll("li"));
    //const menuItemIDs = existingMenuItems.map(item => item.dataset.id);

    //console.log(games);

    games.forEach((game) => {
        let menuItem = gamesMenu.querySelector(`li[data-id="${game.gameID}"]`);

        if (menuItem) {
            // Update existing menu item attributes and content if necessary
            menuItem.dataset.cssScoreCards = game.CSSScoreCards || "";
            menuItem.dataset.cssInitials = game.CSSInitials || "";
            menuItem.dataset.cssScores = game.CSSScores || "";
            menuItem.dataset.cssBox = game.CSSBox || "";
            menuItem.dataset.cssTitle = game.CSSTitle || "";
            menuItem.dataset.scoreType = game.ScoreType || "";
            menuItem.dataset.sortAscending = game.SortAscending || "";
            menuItem.dataset.gameImage = game.GameImage || "";
            menuItem.dataset.gameBackground = game.GameBackground || "";
            menuItem.dataset.tags = game.tags || "";
            menuItem.dataset.hidden = game.Hidden || "FALSE";
            menuItem.dataset.gameColor = game.GameColor || "#FFFFFF";
            menuItem.dataset.gameSort = game.GameSort || game.gameID;

            const span = menuItem.querySelector("span");
            if (span && span.textContent !== game.gameName) {
                span.textContent = game.gameName;
            }

            // Update visibility icon
            const hideButton = menuItem.querySelector(".hide-button i");
            if (hideButton) {
                hideButton.classList.toggle("fa-eye", game.Hidden === "FALSE");
                hideButton.classList.toggle("fa-eye-slash", game.Hidden === "TRUE");
            }
        } else {
            // Add new menu item if not existing
            menuItem = document.createElement("li");
            menuItem.dataset.id = game.gameID;
            menuItem.dataset.gameSort = game.GameSort || game.gameID;
            menuItem.dataset.cssScoreCards = game.CSSScoreCards || "";
            menuItem.dataset.cssInitials = game.CSSInitials || "";
            menuItem.dataset.cssScores = game.CSSScores || "";
            menuItem.dataset.cssBox = game.CSSBox || "";
            menuItem.dataset.cssTitle = game.CSSTitle || "";
            menuItem.dataset.scoreType = game.ScoreType || "";
            menuItem.dataset.sortAscending = game.SortAscending || "";
            menuItem.dataset.gameImage = game.GameImage || "";
            menuItem.dataset.gameBackground = game.GameBackground || "";
            menuItem.dataset.tags = game.tags || "";
            menuItem.dataset.hidden = game.Hidden || "FALSE";
            menuItem.dataset.gameColor = game.GameColor || "#FFFFFF";
            menuItem.classList.add("game-list-card", "draggable");
            menuItem.setAttribute("draggable", "true");

            menuItem.innerHTML = `
                <span class="game-list-card-title">${game.gameName}</span>
                <div class="game-list-card-actions">
                    <button class="hide-button" title="Toggle Visibility">
                        <i class="fas ${game.Hidden === "TRUE" ? "fa-eye-slash" : "fa-eye"}"></i>
                    </button>
                    <button class="edit-button">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="delete-button">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;
            gamesMenu.appendChild(menuItem);
        }
    });

    // Remove stale menu items that are no longer in the games array
    existingMenuItems.forEach((item) => {
        if (!games.some(game => String(game.gameID) === item.dataset.id)) {
            item.remove();
        }
    });

    attachDragAndDrop(); 
}

function attachDragAndDrop() {
    const gameList = document.getElementById('game-list');
    const draggableItems = document.querySelectorAll(".game-list-card.draggable");

    // 🔥 Remove previous event listeners before attaching new ones
    draggableItems.forEach(item => {
        item.removeEventListener("dragstart", handleDragStart);
        item.removeEventListener("dragover", handleDragOver);
        item.removeEventListener("drop", handleDrop);
        item.removeEventListener("dragend", handleDragEnd);
    });

    // 🔥 Attach fresh event listeners
    draggableItems.forEach(item => {
        item.addEventListener("dragstart", handleDragStart);
        item.addEventListener("dragover", (e) => handleDragOver(e, gameList));
        item.addEventListener("drop", handleDrop);
        item.addEventListener("dragend", handleDragEnd);
    });
}

// Event Handlers (Moved outside for cleaner code)
function handleDragStart(e) {
    draggedItem = e.target;
    e.dataTransfer.effectAllowed = "move";
    setTimeout(() => (draggedItem.style.opacity = "0.5"), 0);
}

function handleDragOver(e, container) {
    e.preventDefault();
    const afterElement = getDragAfterElement(container, e.clientY);
    if (afterElement == null) {
        container.appendChild(draggedItem);
    } else if (afterElement instanceof Node && draggedItem !== afterElement) {
        container.insertBefore(draggedItem, afterElement);
    }
}

function handleDrop() {
    if (draggedItem) {
        draggedItem.style.opacity = "1";
        updateGameOrder();
    }
}

function handleDragEnd() {
    if (draggedItem) {
        draggedItem.style.opacity = "1";
        updateGameOrder();
        draggedItem = null;
    }
}

function getDragAfterElement(container, y) {
    const elements = [...container.querySelectorAll(".draggable:not(.dragging)")];

    return elements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) {
            return { offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY, element: null }).element || null;
}

async function updateGameOrder() {
    const updatedOrder = [...document.querySelectorAll(".game-list-card.draggable")].map((game, index) => ({
        game_id: game.dataset.id,
        game_sort: index + 1
    }));

    try {
        await fetch(`/api/v1/update-game-order`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(updatedOrder)
        });

        fetchGamesAndScores();  // Refresh main game display
    } catch (error) {
        console.error("Error updating game order:", error);
    }
}

// Auto-update data every 30 seconds
setInterval(fetchGamesAndScores, 30000);

// Initial fetch
fetchGamesAndScores();

attachDragAndDrop();
