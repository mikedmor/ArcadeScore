/**
 * Update global styles and preset menus
 */
export function updateStylesMenu(stylesData) {
    const { roomID: styleRoomID, css_body, css_card, presets } = stylesData;

    // Apply styles only if the roomID matches
    if (styleRoomID && styleRoomID === roomID) {
        console.log(`Applying global styles for room ${roomID}`);

        // Update global style inputs
        document.getElementById("css-body").value = css_body || "";
        document.getElementById("css-card").value = css_card || "";

        // Apply global styles dynamically
        document.querySelectorAll(".game-container").forEach(container => {
            container.style = css_body || "";
        });

        document.querySelectorAll(".game-card").forEach(card => {
            let appliedCardStyle = css_card || "";

            // Replace placeholders with actual game values
            appliedCardStyle = appliedCardStyle
                .replace(/{GameBackground}/g, card.dataset.background || "")
                .replace(/{GameColor}/g, card.dataset.color || "#FFFFFF")
                .replace(/{GameImage}/g, card.dataset.image || "");

            card.setAttribute("style", appliedCardStyle);

            // Ensure ordering is correct
            if (card.style.order !== `${card.dataset.gameSort}`) {
                card.style.order = `${card.dataset.gameSort}`;
            }
        });
    } else {
        console.log(`Skipping global style updates (current room: ${roomID}, received: ${styleRoomID})`);
    }

    // Always update preset dropdowns, regardless of roomID
    const presetSelectors = document.querySelectorAll("#preset-selector, #game-preset-selector, #css_style");

    presetSelectors.forEach(selector => {
        const currentValue = selector.value; // Save currently selected value
        selector.innerHTML = `<option value="">-- Select Preset --</option>`;

        presets.forEach(preset => {
            const option = document.createElement("option");
            option.value = String(preset.id);
            option.textContent = preset.name;
            selector.appendChild(option);
        });

        // Ensure custom option appears in the game form
        if (selector.id === "css_style") {
            const customOption = document.createElement("option");
            customOption.value = "_custom";
            customOption.textContent = "-- Custom --";
            selector.prepend(customOption);
        }

        // Restore previously selected value if it still exists
        if ([...selector.options].some(option => option.value === currentValue)) {
            selector.value = currentValue;
        } else {
            console.warn(`⚠️ Previous value ${currentValue} not found in updated presets`);
        }
    });
}
