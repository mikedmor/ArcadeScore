import { scrollToTop } from '../utils.js';

// Whether this browser session is already an authenticated admin for this
// room. Assume yes until the auth-status check comes back, so a slow/failed
// network request doesn't lock an already-open room's admin out.
let isRoomAdmin = true;

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
    const integrationsSection = document.getElementById('integrations-section');

    // Admin login gate
    const adminLoginModal = document.getElementById('admin-login-modal');
    const adminLoginError = document.getElementById('admin-login-error');
    const adminLoginPassword = document.getElementById('admin-login-password');
    const adminLoginSubmitBtn = document.getElementById('admin-login-submit-btn');
    const adminLoginCancelBtn = document.getElementById('admin-login-cancel-btn');

    fetch(`/api/v1/settings/${roomID}/auth-status`)
        .then(response => response.json())
        .then(status => { isRoomAdmin = !!status.is_admin; })
        .catch(error => console.error("Failed to check admin auth status:", error));

    function showLoginModal() {
        adminLoginError.textContent = '';
        adminLoginPassword.value = '';
        adminLoginModal.classList.remove('hidden');
        adminLoginPassword.focus();
    }

    function hideLoginModal() {
        adminLoginModal.classList.add('hidden');
    }

    function attemptLogin() {
        fetch(`/api/v1/settings/${roomID}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: adminLoginPassword.value }),
        })
            .then(response => response.json().then(data => ({ ok: response.ok, data })))
            .then(({ ok, data }) => {
                if (!ok) {
                    adminLoginError.textContent = data.error || 'Login failed';
                    return;
                }
                isRoomAdmin = true;
                hideLoginModal();
                hamburgerMenu.classList.add('open');
            })
            .catch(error => {
                adminLoginError.textContent = error.message;
            });
    }

    adminLoginSubmitBtn.addEventListener('click', attemptLogin);
    adminLoginCancelBtn.addEventListener('click', hideLoginModal);
    adminLoginPassword.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            attemptLogin();
        }
    });

    // Toggle menu visibility
    hamburgerButton.addEventListener('click', () => {
        if (!isRoomAdmin) {
            showLoginModal();
            return;
        }
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
            case 'integrations-section':
            case 'admin-section':
                sectionContent.style.display = 'none';
                menuOptions.style.display = 'block';
                backArrow.style.display = 'none';
                homeButton.style.display = 'block';
                break;
            case 'vpin-studio-section':
                integrationsSection.classList.add('active');
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
