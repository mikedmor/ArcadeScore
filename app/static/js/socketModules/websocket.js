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

        // Join this room's Socket.IO room so game/score/style/settings events are
        // scoped to displays actually showing this scoreboard. Reconnects (e.g.
        // after a network blip) re-join automatically since this runs on every
        // "connect", not just the first one.
        if (currentPage === "scoreboard") {
            socket.emit("join", { roomID });
        }
    });

    // Progress updates for scoreboard creation and export (applies to all pages).
    // Filtered by session_id so a background task one tab kicked off doesn't pop
    // the loading modal on every other open tab too.
    socket.on("progress_update", (data) => {
        console.log("Received export progress update:", data);

        if (data.session_id && data.session_id !== localStorage.getItem("session_id")) {
            return;
        }

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
    let updateGameCard, updateGameMenu, removeGameFromDOM, toggleGameVisibility, updateGameSort, updateGameScores, updateGamePauseState, updateStylesMenu, refreshPlayerList;
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
        updateGamePauseState = gamesModule.updateGamePauseState;
        updateStylesMenu = stylesModule.updateStylesMenu;
        refreshPlayerList = playersModule.refreshPlayerList;

        socket.on("game_update", (data) => {
            if (!data) return; // Ignore if no data is received
        
            // Ensure we're only processing updates for the current room
            if (Array.isArray(data)) {
                console.log("Multiple Games updated via WebSocket:", data);
                document.getElementById("global-loading-modal").classList.remove("hidden");
        
                let index = 0;
        
                function processNextGame() {
                    if (index < data.length) {
                        const game = data[index];
                        if (game.roomID === roomID) {
                            modalLoadingStatus.innerHTML = `Updating ${game.gameName}`;
                            progressBar.style.width = `${((index + 1) / data.length) * 100}%`;
                            updateGameCard(game);
                            updateGameMenu(game);
                        }
                        index++;
                        setTimeout(processNextGame, 50); // Small delay to allow UI updates
                    } else {
                        // Hide modal after all updates
                        document.getElementById("global-loading-modal").classList.add("hidden");
                        modalLoadingStatus.innerHTML = "";
                        progressBar.style.width = "0%";
                    }
                }
        
                processNextGame(); // Start processing updates
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
            console.log("Game scores updated via WebSocket:", data);
            if (data.roomID === roomID) {
                updateGameScores(data);
            }
        });

        socket.on("game_pause_state", (data) => {
            console.log("Game pause state changed via WebSocket:", data);
            if (data.roomID === roomID) {
                updateGamePauseState(data);
            }
        });

        socket.on("styles_updated", (data) => {
            console.log("Updated styles via WebSocket:", data);
            updateStylesMenu(data);
        });

        socket.on("players_updated", (data) => {
            console.log("Updated player list via WebSocket:", data.players);
            if (data.players) {
                refreshPlayerList(data.players);
            }
        });

        socket.on("settings_updated", (data) => {
            // The tab that made the change already applied it optimistically -
            // only other displays showing this room need to pick it up, and the
            // simplest correct way to do that for a wall display is a reload
            // rather than hand-patching every scroll timer/date format in place.
            if (data.roomID === roomID && data.client_id !== clientId) {
                console.log("Settings changed on another tab, reloading:", data);
                location.reload();
            }
        });

        console.log("Done Loading scoreboard Sockets");
    }
});
