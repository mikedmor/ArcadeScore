document.addEventListener("DOMContentLoaded", () => {
    const gameContainer = document.getElementById('gameContainer');
    const gameCards = document.querySelectorAll('.game-card');
    let isDragging = false;
    let startX, startY, scrollLeft, scrollTop;

    // Horizontal scrolling
    function handleMouseDown(e) {
        isDragging = true;
        startX = e.pageX || e.touches[0].pageX;
        scrollLeft = gameContainer.scrollLeft;

        const onMouseMove = (event) => {
            if (!isDragging) return;
            const x = event.pageX || event.touches[0].pageX;
            gameContainer.scrollLeft = scrollLeft - (x - startX);
        };

        const stopDragging = () => {
            isDragging = false;
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', stopDragging);
            document.removeEventListener('touchmove', onMouseMove);
            document.removeEventListener('touchend', stopDragging);
        };

        document.addEventListener('mousemove', onMouseMove, { passive: true });
        document.addEventListener('mouseup', stopDragging, { passive: true });
        document.addEventListener('touchmove', onMouseMove, { passive: true });
        document.addEventListener('touchend', stopDragging, { passive: true });
    }

    gameContainer.addEventListener('mousedown', handleMouseDown, { passive: true });
    gameContainer.addEventListener('touchstart', handleMouseDown, { passive: true });

    // Vertical scrolling for score containers
    gameCards.forEach((card) => {
        const scoreContainer = card.querySelector('.score-container');
        if (scoreContainer) {
            function handleVerticalMouseDown(e) {
                isDragging = true;
                startY = e.pageY || e.touches[0].pageY;
                scrollTop = scoreContainer.scrollTop;

                const onMouseMove = (event) => {
                    if (!isDragging) return;
                    const y = event.pageY || event.touches[0].pageY;
                    scoreContainer.scrollTop = scrollTop - (y - startY);
                };

                const stopDragging = () => {
                    isDragging = false;
                    document.removeEventListener('mousemove', onMouseMove);
                    document.removeEventListener('mouseup', stopDragging);
                    document.removeEventListener('touchmove', onMouseMove);
                    document.removeEventListener('touchend', stopDragging);
                };

                document.addEventListener('mousemove', onMouseMove, { passive: true });
                document.addEventListener('mouseup', stopDragging, { passive: true });
                document.addEventListener('touchmove', onMouseMove, { passive: true });
                document.addEventListener('touchend', stopDragging, { passive: true });
            }

            scoreContainer.addEventListener('mousedown', handleVerticalMouseDown, { passive: true });
            scoreContainer.addEventListener('touchstart', handleVerticalMouseDown, { passive: true });
        }
    });
});
