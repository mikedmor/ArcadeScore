document.addEventListener("DOMContentLoaded", async () => {
    const socket = io({
        transports: ["websocket"],
        upgrade: false
    });

    const modalLoading = document.getElementById("global-loading-modal");
    const modalLoadingStatus = document.getElementById("modal-loading-status");
    const progressBar = document.getElementById("progress-bar");
    const modalCloseButton = document.getElementById("modal-close-button");

    // Detect current page
    const currentPage = document.body.dataset.page;
    console.log("currentPage: ", currentPage);

    let loadScoreboards;
    if(currentPage === "index"){
        const scoreboardModule =   await import("/static/js/index/index.js");
        loadScoreboards = scoreboardModule.loadScoreboards;
    }
    modalCloseButton.addEventListener('click', () => {
        modalLoading.classList.add("hidden");
        if(currentPage === "index"){
            loadScoreboards();
        }
    });

    socket.on("connect", () => {
        console.log("WebSocket Connected!");
    });

    // Progress updates for scoreboard creation (applies to all pages)
    socket.on("progress_update", (data) => {
        console.log("Received export progress update:", data);
    
        // Show the loading modal
        modalLoading.classList.remove("hidden");
    
        if (data.progress === -1) {
            modalLoadingStatus.innerHTML = `<span style="color: red;">Error:</span> ${data.message}`;
            progressBar.style.width = "0%"; // Reset progress bar on error
            modalCloseButton.classList.remove("hidden"); // Show close button
        } else {
            // Normal Progress Update
            if (data.message) {
                modalLoadingStatus.innerHTML = data.message;
            }
            progressBar.style.width = `${data.progress}%`;
    
            // 🎉 Show Close Button on Completion
            if (data.progress === 100) {
                modalCloseButton.classList.remove("hidden");
            }
        }
    });
    
    if (currentPage === "index"){
        socket.on("file_ready", (data) => {
            console.log("Export completed. Starting download...", data);
        
            if (data.session_id === localStorage.getItem("session_id")) {
                const downloadUrl = data.file_path;
                const downloadLink = document.createElement("a");
                downloadLink.href = downloadUrl;
                downloadLink.download = "ArcadeScoreExport.7z";
                document.body.appendChild(downloadLink);
                downloadLink.click();
                document.body.removeChild(downloadLink);
            }
            
            document.getElementById("import-data-btn").disabled = false;
            document.getElementById("export-data-btn").disabled = false;
        });
    }

    // Sockets only for scoreboard
    let updateGameCard, updateGameMenu, removeGameFromDOM, toggleGameVisibility, updateGameSort, updateGameScores, updateStylesMenu, refreshPlayerList;
    if (currentPage === "scoreboard") {
        console.log("Loading scoreboard Sockets");
        const gamesModule =   await import("/static/js/socketModules/games.js");
        const stylesModule =  await import("/static/js/socketModules/styles.js");
        const playersModule = await import("/static/js/socketModules/players.js");

        updateGameCard = gamesModule.updateGameCard;
        updateGameMenu = gamesModule.updateGameMenu;
        removeGameFromDOM = gamesModule.removeGameFromDOM;
        toggleGameVisibility = gamesModule.toggleGameVisibility;
        updateGameSort = gamesModule.updateGameSort;
        updateGameScores = gamesModule.updateGameScores;
        updateStylesMenu = stylesModule.updateStylesMenu;
        refreshPlayerList = playersModule.refreshPlayerList;

        socket.on("game_update", (data) => {
            if (!data) return; // Ignore if no data is received
        
            // Ensure we're only processing updates for the current room
            if (Array.isArray(data)) {
                // Handle multiple game updates (array)
                data.forEach((game) => {
                    if (game.roomID === roomID) {
                        console.log("Game updated via WebSocket:", game);
                        updateGameCard(game);
                        updateGameMenu(game);
                    }
                });
            } else {
                // Handle single game update (object)
                if (data.roomID === roomID) {
                    console.log("Game updated via WebSocket:", data);
                    updateGameCard(data);
                    updateGameMenu(data);
                }
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

        socket.on("styles_updated", (data) => {
            console.log("Updated styles via WebSocket:", data);
            updateStylesMenu(data);
        });

        socket.on("players_updated", (data) => {
            if (data.players) {
                console.log("Updated player list via WebSocket:", data.players);
                refreshPlayerList(data.players);
            }
        });
        
        console.log("Done Loading scoreboard Sockets");
    }
});
