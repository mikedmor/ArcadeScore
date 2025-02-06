import { loadScoreboards } from './index.js';

document.addEventListener("DOMContentLoaded", () => {
    const importFileInput = document.getElementById("import-file-input");
    const importExportIcon = document.getElementById("import-export-icon");
    const importExportModal = document.getElementById("import-export-modal");
    const importStatus = document.getElementById("import-status");
    const closeModal = document.querySelector(".close-modal");

    // Open modal on icon click
    importExportIcon.addEventListener("click", () => {
        importExportModal.style.display = "flex";
        importExportModal.classList.remove("hidden");
    });

    // Close modal when clicking the close button
    closeModal.addEventListener("click", () => {
        importExportModal.style.display = "none";
        importExportModal.classList.add("hidden");
    });

    // Close modal when clicking outside the content area
    window.addEventListener("click", (event) => {
        if (event.target === importExportModal) {
            importExportModal.style.display = "none";
            importExportModal.classList.add("hidden");
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
            loadScoreboards();
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
