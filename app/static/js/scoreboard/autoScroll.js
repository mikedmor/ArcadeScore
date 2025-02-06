document.addEventListener("DOMContentLoaded", () => {
    const gameContainer = document.getElementById('gameContainer');
    let isUserInteracting = false;
    const scrollSpeed = 1; // Adjust scroll speed for horizontal scrolling
    const scoreScrollSpeed = 0.5; // 🔥 Adjust speed for vertical scrolling
    const autoScrollIntervalTime = 30; // Interval in milliseconds
    const pauseDuration = 60000; // 1 minute (in milliseconds)
    let autoScrollInterval;
    let debounceTimeout;
    let autoScrollDirection = 1; // 1 for right, -1 for left

    // **🔥 Gradually scroll `.score-container` back to top**
    function resetScoreScroll() {
        document.querySelectorAll('.score-container').forEach((scoreContainer) => {
            if (scoreContainer.scrollTop > 0) {
                scoreContainer.scrollTop -= scoreScrollSpeed; // 🔥 Gradual scroll-up
            }
        });
    }

    // **🔥 Auto-scroll logic (Triggers `resetScoreScroll`)**
    function autoScroll() {
        if (!isUserInteracting) {
            gameContainer.scrollLeft += autoScrollDirection * scrollSpeed;
            resetScoreScroll(); // 🔥 Simultaneously scrolls scores up

            // Calculate maximum scroll position
            const maxScrollLeft = gameContainer.scrollWidth - gameContainer.clientWidth;

            // Adjust boundary conditions
            if (gameContainer.scrollLeft >= maxScrollLeft - 0.5) {
                gameContainer.scrollLeft = maxScrollLeft;
                autoScrollDirection = -1;
            } else if (gameContainer.scrollLeft <= 0.5) {
                gameContainer.scrollLeft = 0;
                autoScrollDirection = 1;
            }
        }
    }

    // **🔥 Start auto-scroll interval**
    autoScrollInterval = setInterval(autoScroll, autoScrollIntervalTime);

    // **🔥 Pause auto-scroll on user interaction**
    function pauseAutoScroll() {
        clearTimeout(debounceTimeout);
        isUserInteracting = true;
        debounceTimeout = setTimeout(() => (isUserInteracting = false), pauseDuration);
    }

    // **🔥 Listen for interactions to pause auto-scroll**
    ['mousedown', 'mouseup', 'touchstart', 'touchend', 'wheel'].forEach((event) => {
        gameContainer.addEventListener(event, pauseAutoScroll, { passive: true });
    });
});
