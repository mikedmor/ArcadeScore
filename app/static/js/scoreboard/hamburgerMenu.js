import { scrollToTop } from '../utils.js';

document.addEventListener("DOMContentLoaded", () => {
    const hamburgerButton = document.querySelector('.hamburger-button');
    const hamburgerMenu = document.querySelector('.hamburger-menu');
    const closeButton = document.querySelector('.close-button');
    const menuButtons = document.querySelectorAll('.menu-button');
    const menuSections = document.querySelectorAll('.menu-section');
    const backArrow = document.querySelector('.back-arrow');
    const homeButton = document.querySelector('.home-button');
    const menuOptions = document.getElementById('menu-options');
    const sectionContent = document.getElementById('menu-section-content');

    //Sections
    const gamesSection = document.getElementById('games-section');
    const playersSection = document.getElementById('players-section');

    // Toggle menu visibility
    hamburgerButton.addEventListener('click', () => {
        hamburgerMenu.classList.toggle('open');
    });

    closeButton.addEventListener('click', () => {
        hamburgerMenu.classList.remove('open');
        resetMenu();
    });

    // Show specific sections
    menuButtons.forEach(button => {
        button.addEventListener('click', () => {
            const section = button.dataset.section;
            menuSections.forEach(sec => sec.classList.remove('active'));

            document.getElementById(`${section}-section`).classList.add('active');
            menuOptions.style.display = 'none';
            sectionContent.style.display = 'block';

            backArrow.style.display = 'block';
            homeButton.style.display = 'none';

            scrollToTop();
        });
    });

    // Back arrow functionality
    backArrow.addEventListener('click', () => {
        const activeSection = document.querySelector('.menu-section.active');

        if (activeSection) {
            activeSection.classList.remove('active');
        }

        console.log("activeSection.id: ",activeSection.id);
        switch(activeSection.id){
            case 'games-section':
            case 'players-section':
            case 'style-section':
            case 'admin-section':
                sectionContent.style.display = 'none';
                menuOptions.style.display = 'block';
                backArrow.style.display = 'none';
                homeButton.style.display = 'block';
                break;
            case 'game-form-section':
                gamesSection.classList.add('active');
                break;
            case 'player-view-section':
            case 'player-form-section':
                playersSection.classList.add('active');
                break;
        }

        scrollToTop();
    });

    // Home button functionality (Navigates to landing page)
    homeButton.addEventListener('click', () => {
        window.location.href = "/"; // Update with the actual URL of your landing page
    });

    // Helper function to reset menu state
    function resetMenu() {
        menuSections.forEach(sec => sec.classList.remove('active'));
        sectionContent.style.display = 'none';
        menuOptions.style.display = 'block';

        backArrow.style.display = 'none';
        homeButton.style.display = 'block';
    }

    // Initialize correct button visibility
    resetMenu();
});
