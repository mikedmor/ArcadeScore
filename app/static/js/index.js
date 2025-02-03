document.addEventListener("DOMContentLoaded", () => {
    const createScoreboardBtn = document.getElementById("create-scoreboard-btn");
    const saveScoreboardBtn = document.getElementById("save-scoreboard-btn");
    const closeModalBtn = document.getElementById("close-modal-btn");
    const modal = document.getElementById("create-modal");
    const scoreboardList = document.getElementById("scoreboard-list");

    // Open modal
    createScoreboardBtn.addEventListener("click", () => {
        modal.classList.remove("hidden");
    });

    // Close modal
    closeModalBtn.addEventListener("click", () => {
        modal.classList.add("hidden");
    });

    // Fetch and display scoreboards
    function loadScoreboards() {
        fetch("/api/v1/scoreboards")
            .then(response => response.json())
            .then(scoreboards => {
                if (scoreboards.length === 0) {
                    scoreboardList.innerHTML = "<p>No scoreboards available.</p>";
                    return;
                }

                scoreboardList.innerHTML = scoreboards.map(sb => 
                    `<div class="scoreboard-card" onclick="location.href='/${sb.user}'">
                        <div class="scoreboard-image" style="background: linear-gradient(to right, ${generateColorGradient(sb.game_colors)});">
                            <div class="scoreboard-title">${sb.room_name}</div>
                            <div class="scoreboard-info">
                                <p><strong>${sb.num_games}</strong> Games</p>
                                <p><strong>${sb.num_scores}</strong> Scores</p>
                            </div>
                        </div>
                    </div>`
                ).join("");
            })
            .catch(error => {
                scoreboardList.innerHTML = "<p>Error loading scoreboards.</p>";
                console.error("Error fetching scoreboards:", error);
            });
    }

    // Generate color gradient based on game colors
    function generateColorGradient(colors) {
        if (!colors || colors.length === 0) return "#444";
        return colors.join(", ");
    }

    // Save new scoreboard (currently just creating a new room)
    saveScoreboardBtn.addEventListener("click", () => {
        const scoreboardName = document.getElementById("scoreboard-name").value.trim();
        if (!scoreboardName) return alert("Please enter a name for the scoreboard.");

        fetch("/api/v1/scoreboards", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: scoreboardName })
        })
        .then(() => {
            modal.classList.add("hidden");
            loadScoreboards();
        })
        .catch(error => console.error("Error creating scoreboard:", error));
    });

    // Load scoreboards on page load
    loadScoreboards();
});
