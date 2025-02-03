import { updateImagePreview, validateImageURL, scrollToTop } from './utils.js';
import { fetchGamesAndScores } from './autoUpdate.js';

document.addEventListener("DOMContentLoaded", () => {
    const gameList = document.getElementById('game-list');
    const addGameButton = document.getElementById('add-game-button');
    const gameFormSection = document.getElementById('game-form-section');
    const gameSection = document.getElementById('games-section');
    const gameForm = document.getElementById('game-form');
    const gameImageField = document.getElementById('game_image');
    const gameBackgroundField = document.getElementById('game_background');
    const gameImagePreview = document.getElementById('game_image_preview');
    const gameBackgroundPreview = document.getElementById('game_background_preview');
    const gameImageFileInput = document.getElementById("game-image-upload");
    const gameBackgroundFileInput = document.getElementById("game-background-upload");
    const gameColorField = document.getElementById("game_color");
    const cssStyleSelect = document.getElementById("css_style");
    const customCSSSection = document.getElementById("custom_css");
    const copyCSSSection = document.getElementById("copy_css");


    // Save game logic
    async function saveGame() {
        const formData = new FormData(gameForm);
        const game = Object.fromEntries(formData.entries());

        game["room_id"] = roomID;

        // Copy styles from another game
        if (game["css_style"] === "_copy" && game["css_copy"]) {
            const selectedGame = await fetch(`/api/v1/games/${game["css_copy"]}`).then(res => res.json());
            game.css_score_cards = selectedGame.css_score_cards;
            game.css_scores = selectedGame.css_scores;
            game.css_initials = selectedGame.css_initials;
            game.css_box = selectedGame.css_box;
            game.css_title = selectedGame.css_title;
        }

        // Download images if provided
        if (game["game_image"]) {
            game["game_image"] = await fetchAndStoreImage(game["game_image"], "gameImage");
            updateImagePreview(gameImageField, gameImagePreview);
        }
        
        if (game["game_background"]) {
            game["game_background"] = await fetchAndStoreImage(game["game_background"], "gameBackground");
            updateImagePreview(gameBackgroundField, gameBackgroundPreview);
        }

        // Determine if editing or adding
        const endpoint = game["game_id"] 
            ? `/api/v1/games/${game["game_id"]}` 
            : `/api/v1/games`;
        const method = game["game_id"] ? "PUT" : "POST";

        try {
            const response = await fetch(endpoint, {
                method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(game),
            });

            if (!response.ok) throw new Error("Failed to save game.");
            //alert("Game saved successfully!");

            // Update UI
            await fetchGamesAndScores();

            // Return to games section
            gameFormSection.classList.remove('active');
            gameSection.classList.add('active');
        } catch (error) {
            console.error("Error saving game:", error);
            alert("Failed to save game. Check the console for details.");
        }
    }

    // Fetch and store image on the server
    async function fetchAndStoreImage(imageUrl, type) {
        try {
            // Check if the image is already a local file
            if (imageUrl.startsWith(`/static/images/${type}/`)) {
                console.log(`Image is already local: ${imageUrl}`);
                return imageUrl; // Return the local path as is
            }
    
            // Otherwise, fetch and store the image
            const response = await fetch(`/api/v1/store-image`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url: imageUrl, type }),
            });
    
            if (!response.ok) throw new Error("Failed to store image.");
            const data = await response.json();
    
            // Construct the local path and return it
            return `/static/images/${type}/${data.localPath}`;
        } catch (error) {
            console.error("Error storing image:", error);
            return imageUrl; // Fallback to the original URL in case of an error
        }
    }

    // Delete game
    async function deleteGame(gameId) {
        const confirmDelete = confirm("Are you sure you want to delete this game? This action cannot be undone.");
        if (!confirmDelete) return;
    
        try {
            const response = await fetch(`/api/v1/games/${gameId}`, {
                method: "DELETE",
                headers: { "Content-Type": "application/json" },
            });
    
            if (!response.ok) throw new Error("Failed to delete game.");
    
            // Remove the game from the UI
            const gameItem = document.querySelector(`li[data-id="${gameId}"]`);
            if (gameItem) gameItem.remove();
    
            // Refresh the game display to reflect changes
            await fetchGamesAndScores();
        } catch (error) {
            console.error("Error deleting game:", error);
            alert("Failed to delete game. Check the console for details.");
        }
    }
    
    // Edit Game
    function editGame(listItem) {
        toggleCSSSections();

        if (!listItem) {
            console.error("Could not find parent list item.");
            return;
        }

        const gameData = {
            id: listItem.dataset.id,
            name: listItem.querySelector('span').textContent,
            css_score_cards: listItem.dataset.cssScoreCards || '',
            css_initials: listItem.dataset.cssInitials || '',
            css_scores: listItem.dataset.cssScores || '',
            css_box: listItem.dataset.cssBox || '',
            css_title: listItem.dataset.cssTitle || '',
            score_type: listItem.dataset.scoreType || '',
            sort_ascending: listItem.dataset.sortAscending || '',
            game_image: listItem.dataset.gameImage || '',
            game_background: listItem.dataset.gameBackground || '',
            tags: listItem.dataset.tags || '',
            hidden: listItem.dataset.hidden || '',
            game_color: listItem.dataset.gameColor || '#ffffff'
        };

        showGameForm(gameData);
        scrollToTop();
    }

    // Show form for editing or adding games
    async function showGameForm(game = null) {
        fetch(`/api/${user}`)
            .then(response => response.json())
            .then(games => {
                const copyCSSSelect = document.getElementById("css_copy");
                copyCSSSelect.innerHTML = '<option value="" selected>-- Select Game --</option>';
                
                games.forEach(fetchedGame => {
                    if (String(fetchedGame.gameID) !== game?.id) { // Exclude current game
                        const option = document.createElement("option");
                        option.value = fetchedGame.gameID;
                        option.textContent = fetchedGame.gameName;
                        copyCSSSelect.appendChild(option);
                    }
                });
            })
            .catch(error => console.error("Error loading games:", error));

        gameSection.classList.remove('active');
        gameFormSection.classList.add('active');
        document.getElementById('form-title').textContent = game ? 'Edit Game' : 'Add New Game';

        const fields = {
            "vps_url": game?.tags || "",
            "game_name": game?.name || "",
            "css_style": "_custom",
            "css_score_cards": game?.css_score_cards || "",
            "css_initials": game?.css_initials || "",
            "css_scores": game?.css_scores || "",
            "css_box": game?.css_box || "",
            "css_title": game?.css_title || "",
            "score_type": game?.score_type || "",
            "sort_ascending": game?.sort_ascending || "",
            "game_image": game?.game_image || "",
            "game_background": game?.game_background || "",
            "hidden": game?.hidden || "FALSE",
            "game_color": game?.game_color || "#ffffff",
        };

        let defaultPreset = null;

        // Fetch default preset if creating a new game
        if (!game) {
            try {
                const response = await fetch(`/publicCommands.php?c=getRoomInfo&user=${user}`);
                if (!response.ok) throw new Error("Failed to fetch room info.");
                const data = await response.json();
        
                if (data.settings && data.settings.defaultPreset) {
                    defaultPreset = String(data.settings.defaultPreset); 
                }
            } catch (error) {
                console.error("Error fetching default preset:", error);
            }
        }

        // Populate form fields
        Object.entries(fields).forEach(([id, value]) => {
            const input = document.getElementById(id);
            if (input) {
                input.value = value;
            }
        });
        
        // 🔥 Directly set the "selected" attribute
        const cssStyleSelect = document.getElementById("css_style");
        if (cssStyleSelect) {
            cssStyleSelect.querySelectorAll("option").forEach(option => {
                if (option.value === defaultPreset) {
                    option.setAttribute("selected", "selected");
                } else {
                    option.removeAttribute("selected");
                }
            });
        }
        
        toggleCSSSections();

        // Reset image previews
        if (!game) {
            gameForm.reset();
            gameImagePreview.style.display = "none";
            gameBackgroundPreview.style.display = "none";
            gameImageFileInput.value = "";
            gameBackgroundFileInput.value = "";
        } else {
            updateImagePreview(gameImageField, gameImagePreview);
            updateImagePreview(gameBackgroundField, gameBackgroundPreview);
        }

        document.getElementById('game_id').value = game?.id || "";
    }

    // Set initial background color
    function updateColorFieldBackground(input) {
        input.style.backgroundColor = input.value;
    }

    // Function to toggle visibility
    function toggleCSSSections() {
        if (cssStyleSelect.value === "_custom") {
            customCSSSection.style.display = "block";
            copyCSSSection.style.display = "none";
        } else if (cssStyleSelect.value === "_copy") {
            customCSSSection.style.display = "none";
            copyCSSSection.style.display = "block";
        } else {
            customCSSSection.style.display = "none";
            copyCSSSection.style.display = "none";
        }
    }

    /* Event Listeners */
    const attachFileUploadHandler = (fileInput, urlInput, previewElement, type) => {
        fileInput.addEventListener("change", async (event) => {
            const file = event.target.files[0];
            if (file) {
                try {
                    // Upload the file to the server
                    const formData = new FormData();
                    formData.append("file", file);
                    formData.append("type", type);
    
                    const response = await fetch(`/api/v1/upload-image`, {
                        method: "POST",
                        body: formData,
                    });
    
                    if (!response.ok) throw new Error("Failed to upload image");
    
                    const data = await response.json();
    
                    // Update the URL input with the local path
                    urlInput.value = data.localPath;
    
                    // Update the preview
                    updateImagePreview(urlInput, previewElement);
                } catch (error) {
                    console.error("Error uploading image:", error);
                    alert("Failed to upload image. Please check the console for details.");
                }
            }
        });
    };

    gameList.addEventListener("click", async (event) => {
        const button = event.target.closest("button");
        if (!button) return;

        const listItem = button.closest("li");
        if (!listItem) return;

        const gameId = listItem.dataset.id;

        if (button.classList.contains("hide-button")) {
            // Toggle Hidden Status
            const isCurrentlyHidden = listItem.dataset.hidden === "TRUE";
            const newHiddenStatus = isCurrentlyHidden ? "FALSE" : "TRUE";

            try {
                const response = await fetch(`/api/v1/games/${gameId}/hide`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ hidden: newHiddenStatus }),
                });

                if (!response.ok) throw new Error("Failed to update game visibility.");

                listItem.dataset.hidden = newHiddenStatus;

                // Update icon
                const icon = button.querySelector("i");
                icon.classList.toggle("fa-eye", newHiddenStatus === "FALSE");
                icon.classList.toggle("fa-eye-slash", newHiddenStatus === "TRUE");

                // Refresh game list
                fetchGamesAndScores();
            } catch (error) {
                console.error("Error updating game visibility:", error);
            }
        } 
        else if (button.classList.contains("edit-button")) {
            // Handle Edit
            editGame(listItem);
        } 
        else if (button.classList.contains("delete-button")) {
            // Handle Delete
            deleteGame(gameId);
        }
    });

    // Validate on form submission
    gameForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const gameImageValue = gameImageField.value.trim();
        const gameBackgroundValue = gameBackgroundField.value.trim();

        if (gameImageValue && !validateImageURL(gameImageValue)) {
            e.preventDefault();
            alert("Please enter a valid URL or local path for the Game Image.");
            return;
        }

        if (gameBackgroundValue && !validateImageURL(gameBackgroundValue)) {
            e.preventDefault();
            alert("Please enter a valid URL or local path for the Game Background.");
            return;
        }

        // Proceed with the form submission
        saveGame();
    });

    // Show form for adding a new game
    addGameButton.addEventListener('click', () => {
        showGameForm();
        scrollToTop();
    });

    // Update visibility when selection changes
    cssStyleSelect.addEventListener("change", toggleCSSSections);

    /* Startup Code */

    // Update background on input or change events
    gameColorField.addEventListener("input", () => updateColorFieldBackground(gameColorField));
    gameColorField.addEventListener("change", () => updateColorFieldBackground(gameColorField));

    // Initialize the background color
    updateColorFieldBackground(gameColorField);
    
    // Attach upload handlers to game image and background fields
    attachFileUploadHandler(gameImageFileInput, gameImageField, gameImagePreview, "gameImage");
    attachFileUploadHandler(gameBackgroundFileInput, gameBackgroundField, gameBackgroundPreview, "gameBackground");

});
