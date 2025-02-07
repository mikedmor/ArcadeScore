/**
 * Refresh the players list when changes are received
 */
export function refreshPlayerList(players) {
    const playerList = document.getElementById("player-list");
    playerList.innerHTML = ""; // Clear existing list

    playerList.innerHTML = players.map(player => `
        <li class="player-list-card" data-id="${player.id}">
            <span class="player-name">${player.full_name}</span>
            <span class="player-alias">(${player.default_alias})</span>
        </li>
    `).join("");
}