import { showToast } from '../utils.js';

document.addEventListener("DOMContentLoaded", () => {
    const updatesIcon = document.getElementById("updates-icon");
    const updatesModal = document.getElementById("updates-modal");
    if (!updatesIcon || !updatesModal) return;

    const currentBuildEl = document.getElementById("update-current-build");
    const statusMessageEl = document.getElementById("update-status-message");
    const availableBanner = document.getElementById("update-available-banner");
    const latestBuildEl = document.getElementById("update-latest-build");
    const latestDateEl = document.getElementById("update-latest-date");
    const latestLinkEl = document.getElementById("update-latest-link");
    const checkBtn = document.getElementById("check-updates-btn");
    const applyBtn = document.getElementById("apply-update-btn");
    const deploymentNoteEl = document.getElementById("update-deployment-note");
    const prereleaseToggle = document.getElementById("update-include-prereleases");
    const closeModalBtn = updatesModal.querySelector(".close-modal");

    let loaded = false;
    let restartPollTimer = null;

    function openModal() {
        updatesModal.style.display = "flex";
        updatesModal.classList.remove("hidden");
        if (!loaded) {
            loaded = true;
            loadStatus();
        }
    }

    function closeModal() {
        updatesModal.style.display = "none";
        updatesModal.classList.add("hidden");
    }

    updatesIcon.addEventListener("click", openModal);
    closeModalBtn.addEventListener("click", closeModal);
    window.addEventListener("click", (event) => {
        if (event.target === updatesModal) closeModal();
    });

    function formatDate(isoString) {
        if (!isoString) return "an unknown date";
        try {
            return new Date(isoString).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
        } catch (e) {
            return isoString;
        }
    }

    function resetApplyButton() {
        applyBtn.disabled = false;
        applyBtn.innerHTML = `<i class="fas fa-download"></i> Update Now`;
    }

    function renderStatus(status) {
        currentBuildEl.textContent = status.current_build;
        prereleaseToggle.checked = !!status.include_prereleases;

        if (status.error) {
            statusMessageEl.textContent = `Couldn't check for updates: ${status.error}`;
        } else if (status.last_checked_at) {
            statusMessageEl.textContent = `Last checked ${formatDate(status.last_checked_at)}`;
        } else {
            statusMessageEl.textContent = "";
        }

        if (status.update_available) {
            availableBanner.classList.remove("hidden");
            latestBuildEl.textContent = status.latest_build;
            latestDateEl.textContent = formatDate(status.latest_published_at);
            if (status.latest_url) {
                latestLinkEl.href = status.latest_url;
            }
        } else {
            availableBanner.classList.add("hidden");
        }

        if (status.deployment_type === "git" && status.update_available) {
            applyBtn.classList.remove("hidden");
            deploymentNoteEl.textContent = "";
        } else {
            applyBtn.classList.add("hidden");
            if (status.deployment_type === "docker") {
                deploymentNoteEl.textContent = "Running in Docker - update by pulling or rebuilding your image and recreating the container.";
            } else if (status.deployment_type === "standalone") {
                deploymentNoteEl.textContent = "This install isn't a git checkout, so it can't update itself automatically - download the latest release from GitHub instead.";
            } else {
                deploymentNoteEl.textContent = "";
            }
        }
    }

    function loadStatus() {
        fetch("/api/v1/updates/status")
            .then(response => response.json())
            .then(renderStatus)
            .catch(error => {
                statusMessageEl.textContent = `Couldn't check for updates: ${error.message}`;
            });
    }

    checkBtn.addEventListener("click", () => {
        checkBtn.disabled = true;
        checkBtn.innerHTML = `<i class="fas fa-arrows-rotate"></i> Checking...`;

        fetch("/api/v1/updates/check", { method: "POST" })
            .then(response => response.json())
            .then(status => {
                renderStatus(status);
                if (status.error) {
                    showToast("Couldn't check for updates: " + status.error, { type: "error" });
                } else {
                    showToast(status.update_available ? `Build ${status.latest_build} is available!` : "You're up to date.", { type: "success" });
                }
            })
            .catch(error => showToast("Failed to check for updates: " + error.message, { type: "error" }))
            .finally(() => {
                checkBtn.disabled = false;
                checkBtn.innerHTML = `<i class="fas fa-arrows-rotate"></i> Check for Updates`;
            });
    });

    prereleaseToggle.addEventListener("change", () => {
        fetch("/api/v1/updates/prerelease-opt-in", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enabled: prereleaseToggle.checked }),
        })
            .then(response => response.json())
            .then(renderStatus)
            .catch(error => showToast("Failed to update preference: " + error.message, { type: "error" }));
    });

    applyBtn.addEventListener("click", () => {
        applyBtn.disabled = true;
        applyBtn.textContent = "Updating...";

        fetch("/api/v1/updates/apply", { method: "POST" })
            .then(response => response.json().then(data => ({ ok: response.ok, data })))
            .then(({ ok, data }) => {
                if (!ok) {
                    showToast("Update failed: " + (data.error || "Unknown error"), { type: "error" });
                    resetApplyButton();
                    return;
                }
                showToast(data.message || "Update applied, restarting...", { type: "success" });
                applyBtn.textContent = "Restarting...";
                pollForRestart();
            })
            .catch(error => {
                showToast("Update failed: " + error.message, { type: "error" });
                resetApplyButton();
            });
    });

    function pollForRestart() {
        const start = Date.now();
        const timeoutMs = 45000;
        const intervalMs = 1500;

        clearInterval(restartPollTimer);
        restartPollTimer = setInterval(() => {
            const timedOut = Date.now() - start > timeoutMs;

            fetch("/", { cache: "no-store" })
                .then(response => {
                    if (response.ok) {
                        clearInterval(restartPollTimer);
                        showToast("Update complete! Reloading...", { type: "success" });
                        setTimeout(() => location.reload(), 500);
                    } else if (timedOut) {
                        clearInterval(restartPollTimer);
                        showToast("Automatic restart didn't finish - please restart ArcadeScore manually.", { type: "error" });
                        resetApplyButton();
                    }
                })
                .catch(() => {
                    // Expected while the old process is shutting down / the new one is starting.
                    if (timedOut) {
                        clearInterval(restartPollTimer);
                        showToast("Automatic restart didn't finish - please restart ArcadeScore manually.", { type: "error" });
                        resetApplyButton();
                    }
                });
        }, intervalMs);
    }
});
