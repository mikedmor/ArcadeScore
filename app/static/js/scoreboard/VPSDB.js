import { updateImagePreview } from '../utils.js';

document.addEventListener("DOMContentLoaded", () => {
    const vpsUrlField = document.getElementById("vps_url");
    const gameNameField = document.getElementById("game_name");
    const loader = document.getElementById("scordBoardLoader");
    const reloadVPSButton = document.createElement('button');

    const gameImageField = document.getElementById('game_image');
    const gameImagePreview = document.getElementById('game_image_preview');

    const gameBackgroundField = document.getElementById('game_background');
    const gameBackgroundPreview = document.getElementById('game_background_preview');

    // Add event listeners for image preview updates
    const attachImagePreviewListeners = (inputField, previewElement) => {
        inputField.addEventListener('input', () => updateImagePreview(inputField, previewElement));
        inputField.addEventListener('change', () => updateImagePreview(inputField, previewElement));
    };

    // Attach listeners to the game image and background fields
    attachImagePreviewListeners(gameImageField, gameImagePreview);
    attachImagePreviewListeners(gameBackgroundField, gameBackgroundPreview);
    
    reloadVPSButton.textContent = "Reload from VPS";
    reloadVPSButton.type = "button"; // Prevent form submission
    reloadVPSButton.classList.add('reload-vps-button');
    vpsUrlField.parentElement.appendChild(reloadVPSButton);

    let localVPSDB = null;

    
    // Function to reload the form from the VPS URL
    async function reloadFormFromVPS() {
        const url = vpsUrlField.value.trim();

        if (!url) {
            alert("Please enter a valid VPS URL.");
            return;
        }

        //ask if the user wants to clear the form

        processVPSURL(url);
    }

    // Fetch cached VPS data from the server
    async function fetchVPSDB() {
        try {
            loader.style.display = "block"; // Show loader
            const response = await fetch("/api/vpsdata");
            if (!response.ok) throw new Error("Failed to fetch VPS data");
            localVPSDB = await response.json();
        } catch (error) {
            console.error("Failed to fetch VPS data:", error);
        } finally {
            loader.style.display = "none"; // Hide loader
        }
    }

    // Extract VPS data based on URL
    async function processVPSURL(url) {
        try {
            if (!localVPSDB) await fetchVPSDB();

            const urlParams = new URLSearchParams(new URL(url).search);
            const gameId = urlParams.get("game");
            const tableId = url.split("#")[1];

            if (localVPSDB) {
                const gameData = localVPSDB.find((game) => game.id === gameId);
                if (gameData) {
                    const tableData = gameData.tableFiles.find((table) => table.id === tableId);
                    if (tableData) {
                        // Populate fields
                        if(gameNameField.value == ""){
                            gameNameField.value = `${gameData.name} (${gameData.manufacturer} ${gameData.year})`;
                        }
                        if (gameData.b2sFiles[0]?.imgUrl && gameImageField.value == "") gameImageField.value = gameData.b2sFiles[0].imgUrl;
                        
                        if (tableData.imgUrl && gameBackgroundField.value == "") gameBackgroundField.value = tableData.imgUrl;

                        // Trigger image preview updates
                        updateImagePreview(gameImageField, gameImagePreview);
                        updateImagePreview(gameBackgroundField, gameBackgroundPreview);

                    } else {
                        if(gameNameField.value == ""){
                            gameNameField.placeholder = "Table not found";
                        }
                    }
                } else {
                    if(gameNameField.value == ""){
                        gameNameField.placeholder = "Game not found";
                    }
                }
            }
        } catch (error) {
            console.error("Error processing VPS URL:", error);
        }
    }

    // Event listener for VPS URL input
    vpsUrlField.addEventListener("change", (e) => {
        const url = e.target.value;
        if (url) processVPSURL(url);
    });

    // Initialize VPS data on load
    fetchVPSDB();

    // Add event listener to the reload button
    reloadVPSButton.addEventListener('click', reloadFormFromVPS);
});
