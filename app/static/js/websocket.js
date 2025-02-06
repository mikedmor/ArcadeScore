document.addEventListener("DOMContentLoaded", () => {
    const socket = io({
        transports: ["websocket"],
        upgrade: false
    });

    const modal = document.getElementById("create-modal");
    const modalContent = document.querySelector(".modal-content");

    const modalLoading = document.getElementById("modal-loading");
    const progressBar = document.getElementById("progress-bar");

    socket.on("connect", () => {
        console.log("WebSocket Connected!");
    });

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
});