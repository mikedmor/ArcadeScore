import { fetchVPinData } from "../utils.js";

document.addEventListener("DOMContentLoaded", () => {
    const serverList = document.getElementById("vpin-server-list");
    const webhookList = document.getElementById("webhook-list");
    const addServerBtn = document.getElementById("add-vpin-server-btn");

    if (!serverList || !webhookList || !addServerBtn) {
        // Integrations section isn't present on this page render.
        return;
    }

    function escapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = value == null ? "" : String(value);
        return div.innerHTML;
    }

    // ------------------------------------------------------------------
    // Linked servers
    // ------------------------------------------------------------------

    function renderServerList(servers) {
        if (!servers.length) {
            serverList.innerHTML = `<li class="integration-item-sub">No VPin Studio servers linked yet.</li>`;
            return;
        }

        serverList.innerHTML = servers.map(server => `
            <li class="integration-item" data-server-id="${server.id}" data-server-url="${escapeHtml(server.server_url)}">
                <div class="integration-item-header">
                    <span class="integration-item-title">${escapeHtml(server.label || server.server_url)}</span>
                    <button class="unlink-server btn-small btn-danger" data-server-id="${server.id}">Unlink</button>
                </div>
                ${server.label ? `<div class="integration-item-sub">${escapeHtml(server.server_url)}</div>` : ""}
                <div class="integration-item-actions">
                    <button class="import-games-btn btn-small" data-server-url="${escapeHtml(server.server_url)}">Import Games</button>
                    <button class="import-players-btn btn-small" data-server-url="${escapeHtml(server.server_url)}">Import / Link Players</button>
                    <button class="resync-media-btn btn-small" data-server-url="${escapeHtml(server.server_url)}">Resync Media</button>
                    <button class="resync-scores-btn btn-small" data-server-url="${escapeHtml(server.server_url)}">Resync Scores</button>
                </div>
                <div class="import-panel hidden" data-panel-for="${server.id}"></div>
            </li>
        `).join("");
    }

    function reloadServers() {
        fetch(`/api/v1/scoreboards/${roomID}/vpin-servers`)
            .then(response => response.json())
            .then(renderServerList)
            .catch(error => console.error("Failed to load linked VPin servers:", error));
    }

    addServerBtn.addEventListener("click", () => {
        let url = prompt("VPin Studio server URL (e.g. http://192.168.1.50:8089):");
        if (!url) return;
        url = url.trim();
        if (!/^https?:\/\//i.test(url)) {
            url = "http://" + url;
        }
        const label = prompt("Optional label for this server (leave blank to use the URL):") || "";

        fetch(`/api/v1/scoreboards/${roomID}/vpin-servers`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ server_url: url, label: label.trim() }),
        })
            .then(response => response.json().then(data => ({ ok: response.ok, data })))
            .then(({ ok, data }) => {
                if (!ok) {
                    alert("Failed to link server: " + (data.error || "Unknown error"));
                    return;
                }
                reloadServers();
            })
            .catch(error => alert("Failed to link server: " + error.message));
    });

    // ------------------------------------------------------------------
    // Registered webhooks
    // ------------------------------------------------------------------

    function reloadWebhooks() {
        fetch(`/api/v1/scoreboards/${roomID}/vpin-webhooks`)
            .then(response => response.json())
            .then(renderWebhookList)
            .catch(error => console.error("Failed to load webhooks:", error));
    }

    function badge(label) {
        return `<span class="badge">${escapeHtml(label)}</span>`;
    }

    function renderWebhookList(webhooks) {
        if (!webhooks.length) {
            webhookList.innerHTML = `<li class="integration-item-sub">No webhooks registered yet — set these up from the scoreboard creation wizard.</li>`;
            return;
        }

        webhookList.innerHTML = webhooks.map(webhook => {
            const badges = [
                webhook.score_update && badge("Highscores: update"),
                webhook.game_create && badge("Games: create"),
                webhook.game_update && badge("Games: update"),
                webhook.game_delete && badge("Games: delete"),
                webhook.player_create && badge("Players: create"),
                webhook.player_update && badge("Players: update"),
                webhook.player_delete && badge("Players: delete"),
                webhook.pause_update && badge("Now Playing: pause"),
                webhook.unpause_update && badge("Now Playing: unpause"),
            ].filter(Boolean).join("");

            let health;
            if (webhook.last_error) {
                health = `<div class="integration-item-sub health-error">Last error: ${escapeHtml(webhook.last_error)}</div>`;
            } else if (webhook.last_event_at) {
                health = `<div class="integration-item-sub health-ok">Last event: ${escapeHtml(webhook.last_event_at)}</div>`;
            } else {
                health = `<div class="integration-item-sub">No events received yet.</div>`;
            }

            return `
                <li class="integration-item" data-webhook-id="${webhook.id}">
                    <div class="integration-item-header">
                        <span class="integration-item-title">${escapeHtml(webhook.webhook_name)}</span>
                        <button class="delete-webhook btn-small btn-danger" data-webhook-id="${webhook.id}">Delete</button>
                    </div>
                    <div class="integration-item-sub">${escapeHtml(webhook.server_url)}</div>
                    <div class="badge-row">${badges}</div>
                    ${health}
                </li>
            `;
        }).join("");
    }

    webhookList.addEventListener("click", (event) => {
        const button = event.target.closest(".delete-webhook");
        if (!button) return;

        if (!confirm("Remove this webhook? VPin Studio will stop calling back into this scoreboard for it.")) {
            return;
        }

        const webhookId = button.dataset.webhookId;
        button.disabled = true;
        button.textContent = "Removing...";

        fetch(`/api/v1/scoreboards/${roomID}/vpin-webhooks/${webhookId}`, { method: "DELETE" })
            .then(response => response.json().then(data => ({ ok: response.ok, data })))
            .then(({ ok, data }) => {
                if (!ok) {
                    alert("Failed to remove webhook: " + (data.error || "Unknown error"));
                    button.disabled = false;
                    button.textContent = "Delete";
                    return;
                }
                reloadWebhooks();
            })
            .catch(error => {
                alert("Failed to remove webhook: " + error.message);
                button.disabled = false;
                button.textContent = "Delete";
            });
    });

    // ------------------------------------------------------------------
    // Server list actions: unlink / resync / import panels
    // ------------------------------------------------------------------

    serverList.addEventListener("click", (event) => {
        const unlinkBtn = event.target.closest(".unlink-server");
        if (unlinkBtn) {
            handleUnlink(unlinkBtn);
            return;
        }

        const resyncMediaBtn = event.target.closest(".resync-media-btn");
        if (resyncMediaBtn) {
            handleResync(resyncMediaBtn, { retrieve_media: true });
            return;
        }

        const resyncScoresBtn = event.target.closest(".resync-scores-btn");
        if (resyncScoresBtn) {
            handleResync(resyncScoresBtn, { sync_historical_scores: true });
            return;
        }

        const importGamesBtn = event.target.closest(".import-games-btn");
        if (importGamesBtn) {
            toggleGamesImportPanel(importGamesBtn);
            return;
        }

        const importPlayersBtn = event.target.closest(".import-players-btn");
        if (importPlayersBtn) {
            togglePlayersImportPanel(importPlayersBtn);
        }
    });

    function handleUnlink(button) {
        if (!confirm("Unlink this server? Already-imported games and players are kept.")) {
            return;
        }

        const serverId = button.dataset.serverId;
        button.disabled = true;

        fetch(`/api/v1/scoreboards/${roomID}/vpin-servers/${serverId}`, { method: "DELETE" })
            .then(response => response.json().then(data => ({ ok: response.ok, data })))
            .then(({ ok, data }) => {
                if (!ok) {
                    alert("Failed to unlink server: " + (data.error || "Unknown error"));
                    button.disabled = false;
                    return;
                }
                reloadServers();
            })
            .catch(error => {
                alert("Failed to unlink server: " + error.message);
                button.disabled = false;
            });
    }

    function handleResync(button, flags) {
        const serverUrl = button.dataset.serverUrl;
        const originalText = button.textContent;
        button.disabled = true;
        button.textContent = "Working...";

        fetch(`/api/v1/scoreboards/${roomID}/vpin-games/resync`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ server_url: serverUrl, ...flags }),
        })
            .then(response => response.json().then(data => ({ ok: response.ok, data })))
            .then(({ ok, data }) => {
                alert(data.message || (ok ? "Done" : "Failed"));
            })
            .catch(error => alert("Resync failed: " + error.message))
            .finally(() => {
                button.disabled = false;
                button.textContent = originalText;
            });
    }

    function getPanel(button) {
        return button.closest(".integration-item").querySelector(".import-panel");
    }

    // ------------------------------------------------------------------
    // Import games panel
    // ------------------------------------------------------------------

    function toggleGamesImportPanel(button) {
        const panel = getPanel(button);
        const serverUrl = button.dataset.serverUrl;

        if (!panel.classList.contains("hidden") && panel.dataset.mode === "games") {
            panel.classList.add("hidden");
            panel.innerHTML = "";
            return;
        }

        panel.dataset.mode = "games";
        panel.classList.remove("hidden");
        panel.innerHTML = `<div class="loading-spinner" style="display:block;">Loading games...</div>`;

        fetchVPinData(
            "api/v1/games",
            serverUrl,
            (vpinGames) => {
                const filtered = (vpinGames || []).filter(
                    game => game.highscoreType && game.highscoreType.trim() !== "" && !game.disabled
                );

                if (!filtered.length) {
                    panel.innerHTML = `<div class="loading-error" style="display:block;">No high-score capable games found on that server.</div>`;
                    return;
                }

                panel.innerHTML = `
                    <label><input type="checkbox" class="games-select-all"> Select All</label>
                    <ul class="import-checklist">
                        ${filtered.map(game => `
                            <li>
                                <input type="checkbox" class="game-import-checkbox"
                                    data-id="${game.id}"
                                    data-name="${escapeHtml(game.gameDisplayName || "Unknown")}"
                                    data-ext-table-id="${escapeHtml(game.extTableId || "")}"
                                    data-ext-table-version-id="${escapeHtml(game.extTableVersionId || "")}">
                                <span>${escapeHtml(game.gameDisplayName || "Unknown")}</span>
                            </li>
                        `).join("")}
                    </ul>
                    <div class="import-options">
                        <label>Style Preset:</label>
                        <select class="game-import-preset"></select>
                        <label><input type="checkbox" class="game-import-retrieve-media" checked> Retrieve Game Media</label>
                        <label><input type="checkbox" class="game-import-sync-scores" checked> Sync Historical Scores</label>
                        <label>Image Compression:</label>
                        <select class="game-import-compression">
                            <option value="original">Original (No Compression)</option>
                            <option value="low">Low (1920x1080)</option>
                            <option value="medium">Medium (1280x720)</option>
                            <option value="high">High (640x360)</option>
                        </select>
                    </div>
                    <button class="btn game-import-submit">Import Selected</button>
                `;

                const selectAll = panel.querySelector(".games-select-all");
                const checkboxes = panel.querySelectorAll(".game-import-checkbox");
                selectAll.addEventListener("change", () => {
                    checkboxes.forEach(cb => { cb.checked = selectAll.checked; });
                });

                fetch("/api/v1/style/presets")
                    .then(response => response.json())
                    .then(presets => {
                        const select = panel.querySelector(".game-import-preset");
                        select.innerHTML = presets.map(p => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join("");
                    })
                    .catch(error => console.error("Failed to load presets:", error));

                panel.querySelector(".game-import-submit").addEventListener("click", () => {
                    submitGamesImport(panel, serverUrl);
                });
            },
            (error) => {
                panel.innerHTML = `<div class="loading-error" style="display:block;">Failed to load games: ${escapeHtml(error)}</div>`;
            }
        );
    }

    function submitGamesImport(panel, serverUrl) {
        const selected = Array.from(panel.querySelectorAll(".game-import-checkbox:checked")).map(cb => ({
            id: cb.dataset.id,
            name: cb.dataset.name,
            extTableId: cb.dataset.extTableId,
            extTableVersionId: cb.dataset.extTableVersionId,
        }));

        if (!selected.length) {
            alert("Select at least one game to import.");
            return;
        }

        const submitBtn = panel.querySelector(".game-import-submit");
        submitBtn.disabled = true;
        submitBtn.textContent = "Importing...";

        fetch(`/api/v1/scoreboards/${roomID}/vpin-games/import`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                server_url: serverUrl,
                games: selected,
                preset_id: panel.querySelector(".game-import-preset").value,
                retrieve_media: panel.querySelector(".game-import-retrieve-media").checked,
                sync_historical_scores: panel.querySelector(".game-import-sync-scores").checked,
                image_compression_level: panel.querySelector(".game-import-compression").value,
            }),
        })
            .then(response => response.json().then(data => ({ ok: response.ok, data })))
            .then(({ data }) => {
                alert(data.message || "Import finished");
                panel.classList.add("hidden");
                panel.innerHTML = "";
            })
            .catch(error => alert("Import failed: " + error.message))
            .finally(() => {
                submitBtn.disabled = false;
                submitBtn.textContent = "Import Selected";
            });
    }

    // ------------------------------------------------------------------
    // Import / link players panel
    // ------------------------------------------------------------------

    function togglePlayersImportPanel(button) {
        const panel = getPanel(button);
        const serverUrl = button.dataset.serverUrl;

        if (!panel.classList.contains("hidden") && panel.dataset.mode === "players") {
            panel.classList.add("hidden");
            panel.innerHTML = "";
            return;
        }

        panel.dataset.mode = "players";
        panel.classList.remove("hidden");
        panel.innerHTML = `<div class="loading-spinner" style="display:block;">Loading players...</div>`;

        fetchVPinData(
            "api/v1/players",
            serverUrl,
            (vpinPlayers) => {
                fetch("/api/v1/players")
                    .then(response => response.json())
                    .then(existingPlayers => renderPlayerImportPanel(panel, serverUrl, vpinPlayers, existingPlayers))
                    .catch(error => {
                        panel.innerHTML = `<div class="loading-error" style="display:block;">Failed to load existing players: ${escapeHtml(error.message)}</div>`;
                    });
            },
            (error) => {
                panel.innerHTML = `<div class="loading-error" style="display:block;">Failed to load players: ${escapeHtml(error)}</div>`;
            }
        );
    }

    function renderPlayerImportPanel(panel, serverUrl, vpinPlayers, existingPlayers) {
        const grouped = {};
        (vpinPlayers || []).forEach(player => {
            if (!grouped[player.name]) {
                grouped[player.name] = { name: player.name, initials: new Set(), vpinIds: new Set() };
            }
            grouped[player.name].initials.add(player.initials);
            grouped[player.name].vpinIds.add(player.id);
        });

        const rows = Object.values(grouped).map(group => {
            const initials = Array.from(group.initials);
            const vpinIds = Array.from(group.vpinIds);
            const existing = existingPlayers.find(p => p.full_name.toLowerCase() === group.name.toLowerCase());

            if (existing) {
                const linkedVpinIds = new Set(existing.vpin.map(vp => vp.vpin_player_id));
                const newVpinIds = vpinIds.filter(id => !linkedVpinIds.has(id));
                const linkedInitials = new Set(existing.aliases);
                const newInitials = initials.filter(init => !linkedInitials.has(init));

                if (!newVpinIds.length && !newInitials.length) {
                    return `<li><span>${escapeHtml(existing.full_name)} — already linked</span></li>`;
                }

                return `
                    <li>
                        <span>${escapeHtml(existing.full_name)} (${escapeHtml(Array.from(linkedInitials).join(","))})${newInitials.length ? ` — new initials: ${escapeHtml(newInitials.join(","))}` : ""}</span>
                        <button class="btn-small link-player-btn"
                            data-vpin-ids="${newVpinIds.join(",")}"
                            data-arcade-id="${existing.id}"
                            data-full-name="${escapeHtml(group.name)}"
                            data-aliases="${escapeHtml(initials.join(","))}">Link</button>
                    </li>
                `;
            }

            return `
                <li>
                    <span>${escapeHtml(group.name)} (${escapeHtml(initials.join(","))}) — new player</span>
                    <button class="btn-small add-player-btn"
                        data-vpin-ids="${vpinIds.join(",")}"
                        data-full-name="${escapeHtml(group.name)}"
                        data-aliases="${escapeHtml(initials.join(","))}">Add</button>
                </li>
            `;
        });

        panel.innerHTML = `<ul class="import-checklist">${rows.join("") || "<li>No players found on that server.</li>"}</ul>`;

        panel.querySelectorAll(".add-player-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                btn.disabled = true;
                btn.textContent = "Adding...";
                fetch("/api/v1/players/vpin/import", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        full_name: btn.dataset.fullName,
                        default_alias: btn.dataset.aliases.split(",")[0],
                        aliases: btn.dataset.aliases.split(","),
                        vpin_player_ids: btn.dataset.vpinIds.split(","),
                        vpin_url: serverUrl,
                    }),
                })
                    .then(response => response.json().then(data => ({ ok: response.ok, data })))
                    .then(({ ok, data }) => {
                        if (!ok) {
                            alert("Failed to add player: " + (data.error || "Unknown error"));
                            btn.disabled = false;
                            btn.textContent = "Add";
                            return;
                        }
                        btn.closest("li").innerHTML = `<span>${escapeHtml(btn.dataset.fullName)} — added</span>`;
                    })
                    .catch(error => {
                        alert("Failed to add player: " + error.message);
                        btn.disabled = false;
                        btn.textContent = "Add";
                    });
            });
        });

        panel.querySelectorAll(".link-player-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                btn.disabled = true;
                btn.textContent = "Linking...";
                fetch("/api/v1/players/vpin", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        server_url: serverUrl,
                        players: [{
                            vpin_player_ids: btn.dataset.vpinIds.split(","),
                            arcadescore_player_id: btn.dataset.arcadeId,
                            full_name: btn.dataset.fullName,
                            aliases: btn.dataset.aliases.split(","),
                        }],
                    }),
                })
                    .then(response => response.json().then(data => ({ ok: response.ok, data })))
                    .then(({ ok, data }) => {
                        if (!ok) {
                            alert("Failed to link player: " + (data.error || "Unknown error"));
                            btn.disabled = false;
                            btn.textContent = "Link";
                            return;
                        }
                        btn.closest("li").innerHTML = `<span>${escapeHtml(btn.dataset.fullName)} — linked</span>`;
                    })
                    .catch(error => {
                        alert("Failed to link player: " + error.message);
                        btn.disabled = false;
                        btn.textContent = "Link";
                    });
            });
        });
    }
});
