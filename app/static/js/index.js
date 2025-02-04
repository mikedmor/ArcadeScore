// Fetch and display scoreboards
export function loadScoreboards() {
    const scoreboardList = document.getElementById("scoreboard-list");
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

document.addEventListener("DOMContentLoaded", () => {
    const createScoreboardBtn = document.getElementById("create-scoreboard-btn");
    const saveScoreboardBtn = document.getElementById("save-scoreboard-btn");
    const closeModalBtn = document.getElementById("close-modal-btn");
    const modal = document.getElementById("create-modal");

    // Open modal
    createScoreboardBtn.addEventListener("click", () => {
        modal.classList.remove("hidden");
    });

    // Close modal
    closeModalBtn.addEventListener("click", () => {
        modal.classList.add("hidden");
    });

    // Save new scoreboard (currently just creating a new room)
    saveScoreboardBtn.addEventListener("click", () => {
        const scoreboardName = document.getElementById("scoreboard-name").value.trim();
        if (!scoreboardName) {
            alert("Please enter a name for the scoreboard.");
            return;
        }

        fetch("/api/v1/scoreboards", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ scoreboard_name: scoreboardName })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert(`Error: ${data.error}`);
            } else {
                createScoreboardBtn.style.display = "none";
                loadScoreboards();
            }
        })
        .catch(error => {
            console.error("Failed to create scoreboard:", error);
            alert("Failed to create scoreboard.");
        });
    });

    // Load scoreboards on page load
    loadScoreboards();
});
