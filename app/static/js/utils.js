// utils.js
export function fetchVPinData(endpoint, vpinUrl, onSuccess, onError) {
    // Ensure vpinUrl ends with a "/"
    if (!vpinUrl.endsWith("/")) {
        vpinUrl += "/";
    }

    // Check the protocol of the current page
    const isHttps = window.location.protocol === "https:";

    // Use the proxy only if the current page is running on HTTPS
    const targetUrl = isHttps
        ? `/api/v1/proxy?url=${encodeURIComponent(vpinUrl + endpoint)}`
        : vpinUrl + endpoint;

    // Fetch the data from the appropriate URL
    fetch(targetUrl)
        .then(response => {
            if (!response.ok) throw new Error("Failed to connect to VPin API.");
            return response.json();
        })
        .then(onSuccess)
        .catch(error => onError(error.message));
}

export function updateImagePreview(inputField, previewElement) {
    const url = inputField.value.trim();

    // Hide the preview initially
    previewElement.style.display = "none";
    previewElement.src = "";

    if (url) {
        // Check if URL starts with a valid protocol or is a local static path
        if (url.startsWith("http://") || url.startsWith("https://") || url.startsWith("/static/images/")) {
            const img = new Image();
            img.onload = () => {
                previewElement.src = url;
                previewElement.style.display = "block";
            };
            img.onerror = () => {
                previewElement.style.display = "none";
            };
            img.src = url;
        }
    }
}

export function validateImageURL(url) {
    // Allow external URLs (http/https) and local paths (/static/images/...)
    const validUrlPattern = /^(https?:\/\/.*|\/static\/images\/.*)$/;
    return validUrlPattern.test(url);
}

export function scrollToTop() {
    document.getElementById("hamburgerMenu").scrollTo({ top: 0, behavior: "instant" });
}

/**
 * Shows a dismissible, auto-expiring notification. Replaces alert() across the app -
 * falls back to a real alert() if #toast-container isn't on the page, so a missing
 * container never silently swallows a message.
 */
export function showToast(message, { type = "info", duration = 4000 } = {}) {
    const container = document.getElementById("toast-container");
    if (!container) {
        window.alert(message);
        return;
    }

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span class="toast-message"></span><button class="toast-close" aria-label="Dismiss">&times;</button>`;
    toast.querySelector(".toast-message").textContent = message;

    const remove = () => {
        toast.classList.add("toast-out");
        toast.addEventListener("animationend", () => toast.remove(), { once: true });
    };

    toast.querySelector(".toast-close").addEventListener("click", remove);
    container.appendChild(toast);

    if (duration > 0) {
        setTimeout(remove, duration);
    }
}

/**
 * Shows a confirmation modal and resolves true/false based on the user's choice.
 * Replaces confirm() across the app - falls back to a real confirm() if
 * #confirm-modal isn't on the page, so a missing modal never silently skips
 * the confirmation.
 */
export function showConfirm(message, { danger = false } = {}) {
    const modal = document.getElementById("confirm-modal");
    if (!modal) {
        return Promise.resolve(window.confirm(message));
    }

    return new Promise((resolve) => {
        const messageEl = document.getElementById("confirm-modal-message");
        const confirmBtn = document.getElementById("confirm-modal-confirm-btn");
        const cancelBtn = document.getElementById("confirm-modal-cancel-btn");

        messageEl.textContent = message;
        confirmBtn.classList.toggle("btn-danger", danger);

        modal.classList.remove("hidden");

        function cleanup(result) {
            modal.classList.add("hidden");
            confirmBtn.removeEventListener("click", onConfirm);
            cancelBtn.removeEventListener("click", onCancel);
            document.removeEventListener("keydown", onKeydown);
            resolve(result);
        }

        function onConfirm() { cleanup(true); }
        function onCancel() { cleanup(false); }
        function onKeydown(event) {
            if (event.key === "Escape") cleanup(false);
            if (event.key === "Enter") cleanup(true);
        }

        confirmBtn.addEventListener("click", onConfirm);
        cancelBtn.addEventListener("click", onCancel);
        document.addEventListener("keydown", onKeydown);
    });
}

/**
 * Wires up click-to-collapse behavior for .menu-section-part[data-collapsible]
 * blocks. The first collapsible part within each .menu-section starts open, the
 * rest start collapsed. Safe to call repeatedly - already-wired parts are skipped.
 */
export function initAccordions(root = document) {
    const seenSections = new Set();

    root.querySelectorAll(".menu-section-part[data-collapsible]").forEach((part) => {
        const header = part.querySelector(".accordion-header");
        const body = part.querySelector(".accordion-body");
        if (!header || !body || part.dataset.accordionInit) return;
        part.dataset.accordionInit = "true";

        const section = part.closest(".menu-section");
        const openByDefault = !seenSections.has(section);
        seenSections.add(section);

        function setOpen(open) {
            header.setAttribute("aria-expanded", String(open));
            body.classList.toggle("accordion-body-open", open);
        }

        setOpen(openByDefault);
        header.addEventListener("click", () => {
            setOpen(header.getAttribute("aria-expanded") !== "true");
        });
    });
}

/**
 * Wires up click-to-open behavior for .dropdown-trigger buttons (kebab menus) -
 * each trigger toggles its adjacent .dropdown-menu, closing any other open one.
 * Safe to call repeatedly (e.g. after re-rendering a list) - already-wired
 * triggers are skipped, and the outside-click/Escape handlers are bound once.
 */
export function initDropdowns(root = document) {
    root.querySelectorAll(".dropdown-trigger").forEach((trigger) => {
        if (trigger.dataset.dropdownInit) return;
        trigger.dataset.dropdownInit = "true";

        trigger.addEventListener("click", (event) => {
            event.stopPropagation();
            const menu = trigger.nextElementSibling;
            if (!menu || !menu.classList.contains("dropdown-menu")) return;

            const isOpen = !menu.classList.contains("hidden");
            document.querySelectorAll(".dropdown-menu").forEach(m => m.classList.add("hidden"));
            if (!isOpen) menu.classList.remove("hidden");
        });
    });

    if (!document.body.dataset.dropdownOutsideClickBound) {
        document.body.dataset.dropdownOutsideClickBound = "true";
        document.addEventListener("click", () => {
            document.querySelectorAll(".dropdown-menu").forEach(m => m.classList.add("hidden"));
        });
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                document.querySelectorAll(".dropdown-menu").forEach(m => m.classList.add("hidden"));
            }
        });
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const currentPage = document.body.dataset.page;

    initAccordions();
    initDropdowns();

    document.querySelectorAll(".tooltip-trigger").forEach(trigger => {
        const tooltipId = trigger.dataset.tooltipId;
        const tooltip = document.getElementById(tooltipId);

        if (!tooltip) return;

        trigger.addEventListener("mouseenter", () => {
            const rect = trigger.getBoundingClientRect();

            // Position the tooltip near the trigger
            tooltip.style.top = `${rect.top - tooltip.offsetHeight - 8}px`;
            tooltip.style.left = `${rect.left + rect.width / 2 - tooltip.offsetWidth / 2}px`;
            tooltip.style.visibility = "visible";
            tooltip.style.opacity = "1";

            // Prevent off-screen tooltips
            if (parseInt(tooltip.style.left) < 10) {
                tooltip.style.left = "10px";
            }
            if (parseInt(tooltip.style.left) + tooltip.offsetWidth > window.innerWidth - 10) {
                tooltip.style.left = `${window.innerWidth - tooltip.offsetWidth - 10}px`;
            }

            // If tooltip goes off the top, place it below
            if (parseInt(tooltip.style.top) < 10) {
                tooltip.style.top = `${rect.bottom + 8}px`;
            }
        });

        trigger.addEventListener("mouseleave", () => {
            tooltip.style.visibility = "hidden";
            tooltip.style.opacity = "0";
        });
    });
    
    if (currentPage === "scoreboard") {
        textFit(document.getElementsByClassName('game-title'), {multiLine: true})
        textFit(document.getElementsByClassName('score-player-name'));
    }
});