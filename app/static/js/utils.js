// utils.js
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

document.addEventListener("DOMContentLoaded", () => {
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
});