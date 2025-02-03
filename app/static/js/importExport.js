document.addEventListener("DOMContentLoaded", () => {
    const importExportIcon = document.getElementById("import-export-icon");
    const importExportModal = document.getElementById("import-export-modal");
    const closeModal = document.querySelector(".close-modal");
    const createScoreboardBtn = document.getElementById("create-scoreboard-btn");
    const createModal = document.getElementById("create-modal");
    const closeCreateModalBtn = document.getElementById("close-modal-btn");

    // Open Create Scoreboard Modal
    createScoreboardBtn.addEventListener("click", () => {
        createModal.style.display = "flex";
    });

    // Close Modal when clicking the close button
    closeCreateModalBtn.addEventListener("click", () => {
        createModal.style.display = "none";
    });

    // Close Modal when clicking outside of it
    window.addEventListener("click", (event) => {
        if (event.target === createModal) {
            createModal.style.display = "none";
        }
    });

    // Save button (placeholder functionality, replace with actual logic)
    document.getElementById("save-scoreboard-btn").addEventListener("click", () => {
        const scoreboardName = document.getElementById("scoreboard-name").value.trim();
        if (!scoreboardName) {
            alert("Please enter a name for the scoreboard.");
            return;
        }

        // Placeholder: Send to backend (replace with actual API call)
        console.log("New Scoreboard Created:", scoreboardName);

        // Close modal after saving
        createModal.style.display = "none";
    });

    // Open modal on icon click
    importExportIcon.addEventListener("click", () => {
        importExportModal.style.display = "flex";
    });

    // Close modal when clicking the close button
    closeModal.addEventListener("click", () => {
        importExportModal.style.display = "none";
    });

    // Close modal when clicking outside the content area
    window.addEventListener("click", (event) => {
        if (event.target === importExportModal) {
            importExportModal.style.display = "none";
        }
    });

    // Import Functionality
    document.getElementById("import-data-btn").addEventListener("click", () => {
        document.getElementById("import-file-input").click();
    });

    document.getElementById("import-file-input").addEventListener("change", function () {
        const file = importFileInput.files[0];
        if (!file) return;

        importStatus.classList.remove("hidden");
        importStatus.textContent = "Importing data...";

        const formData = new FormData();
        formData.append("file", file);

        fetch("/api/v1/import", {
            method: "POST",
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            importStatus.textContent = data.message || "Import completed.";
            location.reload();
        })
        .catch(error => {
            importStatus.textContent = "Import failed.";
            console.error("Import error:", error);
        });
    });

    // Export Functionality
    document.getElementById("export-data-btn").addEventListener("click", () => {
        fetch("/api/v1/export", {
            method: "GET"
        })
        .then(response => {
            if (!response.ok) throw new Error("Failed to export data");
            return response.blob();
        })
        .then(blob => {
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = downloadUrl;
            a.download = "ArcadeScoreExport.7z";
            document.body.appendChild(a);
            a.click();
            a.remove();
        })
        .catch(error => {
            console.error("Export failed:", error);
        });
    });
});
