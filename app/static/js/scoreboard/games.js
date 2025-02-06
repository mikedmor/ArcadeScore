/**
 * Update a single game card in the scoreboard
 */
export function updateGameCard(game) {
    let gameCard = document.querySelector(`.game-card[data-id="${game.gameID}"]`);

    if (!gameCard) {
        console.warn(`Game card with ID ${game.gameID} not found, creating new card.`);
        createGameCard(game);
        return;
    }
    
    const appliedCardStyle = game.css_card
    .replace(/{GameBackground}/g, game.GameBackground || "")
    .replace(/{GameColor}/g, game.GameColor || "#FFFFFF")
    .replace(/{GameImage}/g, game.GameImage || "");

    // Update styles dynamically
    if(gameCard.style !== appliedCardStyle){
        gameCard.style = appliedCardStyle;
    }

    gameCard.dataset.background = game.GameBackground;
    gameCard.dataset.color = game.GameColor;
    gameCard.dataset.image = game.GameImage;
    gameCard.dataset.gameSort = game.GameSort;

    if (gameCard.style.order !== `${game.GameSort}`) {
        gameCard.style.order = `${game.GameSort}`;
    }

    const gameTitle = gameCard.querySelector(".game-title");
    if (gameTitle && gameTitle.textContent !== game.gameName) {
        gameTitle.textContent = game.gameName;
    }

    const gameImage = gameCard.querySelector("img");
    if (game.GameImage) {
        if (!gameImage) {
            gameImage = document.createElement("img");
            gameImage.src = game.GameImage;
            gameImage.alt = game.gameName;
            gameImage.style = game.CSSBox;
            gameCard.prepend(gameImage);
        } else {
            if (gameImage.src !== game.GameImage) {
                gameImage.src = game.GameImage;
            }
            if (gameImage.style !== game.CSSBox) {
                gameImage.style = game.CSSBox;
            }
        }
    } else if (gameImage) {
        gameImage.remove();
    }

    gameCard.querySelector(".game-title").style = game.CSSTitle
    gameCard.querySelector(".score-card").style = game.CSSScoreCards
    gameCard.querySelector(".score-player-name").style = game.CSSInitials
    gameCard.querySelector(".score-score").style = game.CSSScores

    //gameCard.querySelector(".score-container").innerHTML = generateScoreHTML(game);
}

/**
 * Updates the game menu entry
 */
export function updateGameMenu(game) {
    const gamesMenu = document.getElementById("game-list");
    let menuItem = gamesMenu.querySelector(`li[data-id="${game.gameID}"]`);

    if (!menuItem) {
        console.warn(`Game menu item with ID ${game.gameID} not found, creating new entry.`);
        createGameMenuItem(game);
        return;
    }

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
    menuItem.dataset.gameSort = game.GameSort;

    const span = menuItem.querySelector("span");
    if (span && span.textContent !== game.gameName) {
        span.textContent = game.gameName;
    }

    const hideButton = menuItem.querySelector(".hide-button i");
    if (hideButton) {
        hideButton.classList.toggle("fa-eye", game.Hidden === "FALSE");
        hideButton.classList.toggle("fa-eye-slash", game.Hidden === "TRUE");
    }
}

/**
 * Update game sort
 */
export function updateGameSort(data) {
    const gamesMenu = document.getElementById("game-list");
    data.forEach(game => {
        let gameCard = document.querySelector(`.game-card[data-id="${game.game_id}"]`);
        let menuItem = gamesMenu.querySelector(`li[data-id="${game.game_id}"]`);

        if (gameCard) {
            gameCard.dataset.gameSort = game.game_sort;
            gameCard.style.order = `${game.game_sort}`;
        }
        if (menuItem) {
            menuItem.dataset.gameSort = game.game_sort
            menuItem.style.order = `${game.game_sort}`;
        }
    });
}

/**
 * Removes game from DOM
 */
export function removeGameFromDOM(gameID) {
    document.querySelector(`.game-card[data-id="${gameID}"]`)?.remove();
    document.querySelector(`li[data-id="${gameID}"]`)?.remove();
}

/**
 * Toggle game visibility without refreshing
 */
export function toggleGameVisibility(data) {
    const gameCard = document.querySelector(`.game-card[data-id="${data.gameID}"]`);
    const menuItem = document.querySelector(`li[data-id="${data.gameID}"]`);

    if (gameCard) {
        gameCard.style.display = data.hidden === "TRUE" ? "none" : "flex";
    }
    if (menuItem) {
        menuItem.style.display = data.hidden === "TRUE" ? "none" : "block";
    }
}

/**
 * Update the scores for a specific game in the dashboard
 */
export function updateGameScores(data) {
    const gameCard = document.querySelector(`.game-card[data-id="${data.gameID}"]`);

    if (!gameCard) {
        console.warn(`Game card with ID ${data.gameID} not found. Skipping update.`);
        return;
    }

    // Find the score container inside the game card
    const scoreContainer = gameCard.querySelector(".score-container");
    
    if (!scoreContainer) {
        console.error(`Score container not found for game ID ${data.gameID}`);
        return;
    }

    // Generate new score HTML
    const scoresHTML = generateScoreHTML(data);

    // Replace the existing scores with the updated list
    scoreContainer.innerHTML = scoresHTML;
}

/**
 * format the Date
 */
function formatDate(timestamp, format = "MM/DD/YYYY") {
    return dayjs(timestamp).format(format === "DD/MM/YYYY" ? "DD/MM/YYYY" : "MM/DD/YYYY");
}

/**
 * Adds a new game card to the scoreboard
 */
function createGameCard(game) {
    const gameContainer = document.getElementById("gameContainer");
    const newGameCard = document.createElement("div");
    newGameCard.classList.add("game-card");
    newGameCard.dataset.id = game.gameID;
    newGameCard.dataset.background = game.GameBackground;
    newGameCard.dataset.color = game.GameColor;
    newGameCard.dataset.image = game.GameImage;
    newGameCard.dataset.gameSort = game.GameSort;

    const appliedCardStyle = game.css_card
        .replace(/{GameBackground}/g, game.GameBackground || "")
        .replace(/{GameColor}/g, game.GameColor || "#FFFFFF")
        .replace(/{GameImage}/g, game.GameImage || "");

    newGameCard.setAttribute("style", appliedCardStyle);
    newGameCard.style.order = `${game.GameSort}`;

    newGameCard.innerHTML = `
        <span class="game-title" style="${game.CSSTitle}">${game.gameName}</span>
        ${game.GameImage ? `<img src="${game.GameImage}" alt="${game.gameName}" style="${game.CSSBox}">` : ""}
        <div class="score-container">${generateScoreHTML(game)}</div>
    `;

    gameContainer.appendChild(newGameCard);
}

/**
 * Creates a new game menu entry
 */
function createGameMenuItem(game) {
    const gamesMenu = document.getElementById("game-list");
    const menuItem = document.createElement("li");
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

/**
 * Generates score HTML
 */
function generateScoreHTML(game) {
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

    return game.scores.map(score => {
        const formattedDate = formatDate(score.timestamp, "MM/DD/YYYY"); //data?.dateFormat || 
        return `
            <div class="score-card" style="${game.CSSScoreCards}">
                <div class="score-player-name" style="${game.CSSInitials}">${score.playerName}</div>
                <div class="score-score" style="${game.CSSScores}">${score.score}</div>
                <div class="score-date">${formattedDate}</div>
            </div>`
    }).join("") || `<div class="score-card no-scores-yet" style="${game.CSSScoreCards}">No scores yet.</div>`;
}