document.addEventListener("DOMContentLoaded", async () => {
    const socket = io({
        transports: ["websocket"],
        upgrade: false
    });

    const modal = document.getElementById("create-modal");
    const modalContent = document.querySelector(".modal-content");
    const modalLoading = document.getElementById("modal-loading");
    const progressBar = document.getElementById("progress-bar");

    // Detect current page
    const currentPage = document.body.dataset.page;
    console.log("currentPage: ", currentPage);

    socket.on("connect", () => {
        console.log("WebSocket Connected!");
    });

    // Progress updates for scoreboard creation (applies to all pages)
    socket.on("progress_update", (data) => {
        console.log("received progress_update!", data);
        modal.style.display = "flex";
        modal.classList.remove("hidden");
        modalContent.classList.add("hidden");
        modalLoading.classList.remove("hidden");
        
        progressBar.style.width = `${data.progress}%`;
    
        if (data.game) {
            modalLoading.innerHTML = `<p>Processing: ${data.game}</p><div class="progress-container"><div id="progress-bar" class="progress-bar" style="width:${data.progress}%"></div></div>`;
        }

        // TODO: adjust this based on if we are on the homepage or not
        if (data.progress === 100) {
            alert("Scoreboard created successfully!");
            loadScoreboards();
            modalLoading.classList.add("hidden");
            modal.classList.add("hidden");
            modalContent.classList.remove("hidden");
            resetModal();
        }
    });

    // Sockets only for scoreboard
    let updateGameCard, updateGameMenu, removeGameFromDOM, toggleGameVisibility, updateGameSort, updateGameScores;
    if (currentPage === "scoreboard") {
        console.log("Loading scoreboard Sockets");
        const gamesModule = await import("/static/js/scoreboard/games.js");
        updateGameCard = gamesModule.updateGameCard;
        updateGameMenu = gamesModule.updateGameMenu;
        removeGameFromDOM = gamesModule.removeGameFromDOM;
        toggleGameVisibility = gamesModule.toggleGameVisibility;
        updateGameSort = gamesModule.updateGameSort;
        updateGameScores = gamesModule.updateGameScores;

        socket.on("game_update", (data) => {
            if (data.roomID === roomID) {
                console.log("Game updated via WebSocket:", data);
                updateGameCard(data);
                updateGameMenu(data);
            }
        });

        socket.on("game_deleted", (data) => {
            console.log("Game deleted via WebSocket:", data);
            removeGameFromDOM(data.gameID);
        });

        socket.on("game_visibility_toggled", (data) => {
            console.log("Game visibility toggled:", data);
            toggleGameVisibility(data);
        });

        socket.on("game_order_update", (data) => {
            console.log("Game order updated via WebSocket:", data);
            updateGameSort(data);
        });

        socket.on("game_score_update", (data) => {
            if (data.roomID === roomID) {
                console.log("Game scores updated via WebSocket:", data);
                updateGameScores(data);
            }
        });
        
        console.log("Done Loading scoreboard Sockets");
    }
});
