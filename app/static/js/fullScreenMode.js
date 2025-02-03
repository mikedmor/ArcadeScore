let lastClickTime = 0;
const doubleClickThreshold = 300; // Time in milliseconds

document.addEventListener("click", () => {
    const currentTime = new Date().getTime();
    
    if (currentTime - lastClickTime < doubleClickThreshold) {
        toggleFullScreen();
    }

    lastClickTime = currentTime; // Store the current click time
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
