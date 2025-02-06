// autoUpdate.js
let draggedItem = null;

//TODO: Depreciate and remove this function (replaced with sockets)
export async function fetchGamesAndScores() {
    try {
        const response = await fetch(`/api/${user}`);
        if (!response.ok) throw new Error("Failed to fetch games and scores");
        const gamesAndScores = await response.json();

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
        await fetch(`/api/v1/games/update-game-order`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(updatedOrder)
        });
    } catch (error) {
        console.error("Error updating game order:", error);
    }
}

attachDragAndDrop();
