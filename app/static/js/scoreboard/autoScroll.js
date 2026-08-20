document.addEventListener("DOMContentLoaded", () => {
    const gameContainer = document.getElementById("gameContainer");
    let isUserInteracting = false;
    let autoScrollDirection = 1; // 1 for right, -1 for left
    let horizontalScrollInterval, verticalScrollInterval;
    let horizontalScrollTimeout, verticalScrollTimeout;
    let debounceTimeout;

    /**
     * **🔥 Gradually scroll `.score-container` back to top**
     */
    let cachedScoreContainers = [];

    function resetScoreScroll() {
        for (const scoreContainer of cachedScoreContainers) {
            if (scoreContainer.scrollTop > 0) {
                scoreContainer.scrollTop -= Math.max(settings.verticalScrollSpeed * 0.3, 0.3);
            }
        }
    }

    /**
     * **🔥 Horizontal scrolling logic**
     */
    function autoScrollHorizontal() {
        if (!isUserInteracting && settings.horizontalScrollEnabled) {
            const scrollAmount = Math.max(settings.horizontalScrollSpeed, 1);
            gameContainer.scrollLeft += autoScrollDirection * scrollAmount;

            const maxScrollLeft = gameContainer.scrollWidth - gameContainer.clientWidth;
            if (gameContainer.scrollLeft >= maxScrollLeft - 0.5) {
                gameContainer.scrollLeft = maxScrollLeft;
                autoScrollDirection = -1;
            } else if (gameContainer.scrollLeft <= 0.5) {
                gameContainer.scrollLeft = 0;
                autoScrollDirection = 1;
            }
        }
    }

    /**
     * **🔥 Start horizontal scrolling (with its own independent delay)**
     */
    function startAutoScrollHorizontal() {
        stopAutoScrollHorizontal();
        if (settings.horizontalScrollEnabled) {
            horizontalScrollTimeout = setTimeout(() => {
                horizontalScrollInterval = setInterval(autoScrollHorizontal, 30);
            }, settings.horizontalScrollDelay);
        }
    }

    /**
     * **🔥 Stop horizontal scrolling**
     */
    function stopAutoScrollHorizontal() {
        clearTimeout(horizontalScrollTimeout);
        clearInterval(horizontalScrollInterval);
    }

    /**
     * **🔥 Start vertical scrolling (with its own independent delay)**
     */
    function startAutoScrollVertical() {
        stopAutoScrollVertical();
        if (settings.verticalScrollEnabled) {
            verticalScrollTimeout = setTimeout(() => {
                // Re-queried here (once per idle-cycle start, not on every 30ms
                // tick) so a game added/removed since the last cycle is picked
                // up - re-running document.querySelectorAll(".score-container")
                // 33 times a second regardless of whether anything changed was
                // real, measurable overhead on a 100+ game room sitting idle,
                // which is this app's normal steady state on a wall display.
                cachedScoreContainers = [...document.querySelectorAll(".score-container")];
                verticalScrollInterval = setInterval(resetScoreScroll, 30);
            }, settings.verticalScrollDelay);
        }
    }

    /**
     * **🔥 Stop vertical scrolling**
     */
    function stopAutoScrollVertical() {
        clearTimeout(verticalScrollTimeout);
        clearInterval(verticalScrollInterval);
    }

    /**
     * **🔥 Pause both scrolls on user interaction**
     */
    function pauseAutoScroll() {
        clearTimeout(debounceTimeout);
        isUserInteracting = true;

        stopAutoScrollHorizontal();
        stopAutoScrollVertical();

        debounceTimeout = setTimeout(() => {
            isUserInteracting = false;
            startAutoScrollHorizontal();
            startAutoScrollVertical();
        }, 1000); // Short debounce time to prevent jittering
    }

    /**
     * **🔥 Apply settings dynamically**
     */
    function applyScrollSettings() {
        stopAutoScrollHorizontal();
        stopAutoScrollVertical();
        if (settings.horizontalScrollEnabled) startAutoScrollHorizontal();
        if (settings.verticalScrollEnabled) startAutoScrollVertical();
    }

    // **🔥 Start both scrolls independently**
    applyScrollSettings();

    // **🔥 Pause scrolling on user interaction (Clicking anywhere)**
    ["mousedown", "mouseup", "touchstart", "touchend", "wheel"].forEach((event) => {
        gameContainer.addEventListener(event, pauseAutoScroll, { passive: true });
    });

    // **🔥 Listen for setting updates (Dynamically apply without refresh)**
    document.getElementById("horizontal_scroll_enabled").addEventListener("change", () => {
        settings.horizontalScrollEnabled = document.getElementById("horizontal_scroll_enabled").checked;
        applyScrollSettings();
    });

    document.getElementById("vertical_scroll_enabled").addEventListener("change", () => {
        settings.verticalScrollEnabled = document.getElementById("vertical_scroll_enabled").checked;
        applyScrollSettings();
    });

    document.getElementById("horizontal_scroll_speed").addEventListener("input", (e) => {
        settings.horizontalScrollSpeed = Math.max(parseFloat(e.target.value) || 1, 0.1);
    });

    document.getElementById("horizontal_scroll_delay").addEventListener("input", (e) => {
        settings.horizontalScrollDelay = parseInt(e.target.value, 10) || 2000;
    });

    document.getElementById("vertical_scroll_speed").addEventListener("input", (e) => {
        settings.verticalScrollSpeed = Math.max(parseFloat(e.target.value) || 1, 0.1);
    });

    document.getElementById("vertical_scroll_delay").addEventListener("input", (e) => {
        settings.verticalScrollDelay = parseInt(e.target.value, 10) || 2000;
    });
});
