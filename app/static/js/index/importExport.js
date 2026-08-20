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
        document.getElementById("import-data-btn").disabled = true;
        document.getElementById("export-data-btn").disabled = true;
        document.getElementById("import-file-input").click();
    });

    document.getElementById("import-file-input").addEventListener("change", function () {
        const file = this.files[0];
        if (!file) return;
    
        // Get DOM elements
        const importStatus = document.getElementById("import-status");
        const globalLoadingModal = document.getElementById("global-loading-modal");
        const modalLoadingStatus = document.getElementById("modal-loading-status");
        const modalCloseButton = document.getElementById("modal-close-button");
        const progressBar = document.getElementById("progress-bar");
    
        // Show global loading modal
        globalLoadingModal.classList.remove("hidden");
        modalLoadingStatus.textContent = `Importing: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
        modalCloseButton.classList.add("hidden"); // Hide close button while processing
    
        // Set progress bar to an "indeterminate" loading effect
        progressBar.classList.add("indeterminate");
    
        // Prepare file for upload
        const formData = new FormData();
        formData.append("file", file);
    
        fetch("/api/v1/import", {
            method: "POST",
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            // Remove indeterminate effect and hide loading modal
            progressBar.classList.remove("indeterminate");
            globalLoadingModal.classList.add("hidden");
    
            // Update the import status inside the import/export modal
            importStatus.classList.remove("hidden");
            importStatus.textContent = data.message || "Import completed.";
            importStatus.style.color = data.error ? "red" : "green";
    
            // Show close button for user acknowledgment
            modalCloseButton.classList.remove("hidden");
            modalCloseButton.addEventListener("click", () => {
                globalLoadingModal.classList.add("hidden");
            });
            loadScoreboards();
            
            document.getElementById("import-data-btn").disabled = false;
            document.getElementById("export-data-btn").disabled = false;
        })
        .catch(error => {
            // Remove indeterminate effect and hide loading modal
            progressBar.classList.remove("indeterminate");
            globalLoadingModal.classList.add("hidden");
    
            // Update import status with an error message
            importStatus.classList.remove("hidden");
            importStatus.textContent = "Import failed. Check console for details.";
            importStatus.style.color = "red";
    
            console.error("Import error:", error);
    
            // Show close button for user acknowledgment
            modalCloseButton.classList.remove("hidden");
            loadScoreboards();
            
            document.getElementById("import-data-btn").disabled = false;
            document.getElementById("export-data-btn").disabled = false;
        });
    });

    // Export Functionality
    document.getElementById("export-data-btn").addEventListener("click", () => {
        document.getElementById("import-data-btn").disabled = true;
        document.getElementById("export-data-btn").disabled = true;

        const sessionId = localStorage.getItem("session_id") || crypto.randomUUID();
        localStorage.setItem("session_id", sessionId);

        fetch("/api/v1/export?session_id=" + sessionId)
            .then(response => response.json())
            .then(data => {
                if (data.task_id) {
                    console.log("Export started. Waiting for completion...");
                }
            })
            .catch(error => console.error("Export failed:", error));
        // .then(response => {
        //     if (!response.ok) throw new Error("Failed to export data");
        //     return response.blob();
        // })
        // .then(blob => {
        //     const downloadUrl = window.URL.createObjectURL(blob);
        //     const a = document.createElement("a");
        //     a.href = downloadUrl;
        //     a.download = "ArcadeScoreExport.7z";
        //     document.body.appendChild(a);
        //     a.click();
        //     a.remove();
            
        //     document.getElementById("import-data-btn").disabled = false;
        //     document.getElementById("export-data-btn").disabled = false;
        // })
        // .catch(error => {
        //     console.error("Export failed:", error);
            
        //     document.getElementById("import-data-btn").disabled = false;
        //     document.getElementById("export-data-btn").disabled = false;
        // });
    });
});
