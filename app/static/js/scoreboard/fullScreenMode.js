let clickCount = 0;
const clickThreshold = 300; // Time in milliseconds
let lastClickTime = 0;

document.addEventListener("click", (event) => {
    const gameContainer = document.getElementById("gameContainer");

    // Ensure the click is inside the gameContainer or one of its children
    if (!gameContainer.contains(event.target)) {
        clickCount = 0; // Reset if click is outside
        return;
    }

    const currentTime = new Date().getTime();

    // Reset count if time between clicks is too long
    if (currentTime - lastClickTime > clickThreshold) {
        clickCount = 0;
    }

    clickCount++;
    lastClickTime = currentTime;

    if (clickCount >= 3) {
        toggleFullScreen();
        clickCount = 0; // Reset click count after triggering
    }
});

// Function to toggle full-screen mode
function toggleFullScreen() {
    const doc = document.documentElement;

    if (!document.fullscreenElement && !document.webkitFullscreenElement && !document.msFullscreenElement) {
        if (doc.requestFullscreen) {
            doc.requestFullscreen();
        } else if (doc.webkitRequestFullscreen) { /* Safari */
            doc.webkitRequestFullscreen();
        } else if (doc.msRequestFullscreen) { /* IE/Edge */
            doc.msRequestFullscreen();
        }
    } else {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) { /* Safari */
            document.webkitExitFullscreen();
        } else if (document.msExitFullscreen) { /* IE/Edge */
            document.msExitFullscreen();
        }
    }
}
