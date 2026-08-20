# ArcadeScore — Roadmap

**Target:** ship `1.0.0` · **Written:** 2026-08-18 · **Companion docs:** `Progress.md`, `BUG_REVIEW.md`

Phases are ordered by dependency, not by appeal. Phase 0 blocks everything; Phase 1 is what makes
the project's headline feature actually work; Phases 2–3 are what "1.0" honestly requires.

---

## Phase 0 — Recover the tree ⛔ blocks everything

Commit `556c7b2` overwrote 12 commits of March-2025 work with a Feb-2025 zip (`REG-01`). Nothing
downstream is worth doing until this is undone.

- [x] `git revert 556c7b2` (`bb3b548`); confirmed `app/routes/__init__.py` registers 14 blueprints
      again and that `app/models.py`, `app/database.py`, `app/routes/settings.py`,
      `app/socketio_instance.py`, `app/modules/sockets.py`, `app/utils.py` are gone.
- [x] Cherry-picked back the one thing worth keeping from `556c7b2`: `certs/openssl.cnf`.
- [x] Smoke test — ran for real in a local venv (`python -m venv venv`, `pip install -r
      requirements.txt`, `python run.py`) against a fresh `data/highscores.db`: app boots clean
      (`wsgi starting up on http://0.0.0.0:8080`, zero tracebacks), DB lands at `db_version: '2'`
      with `vpin_servers` present and `vpin_webhooks` carrying all the new columns, 4 presets
      seeded, landing page and `/default` both 200, `/webhook/scores` and the new bare
      `/webhook/games`/`/webhook/pause` all correctly 400 (not 404/405) on an empty PUT, the full
      Integrations Menu round-tripped (link → list → delete a server), and `/api/v1/proxy`
      correctly rejected a missing `url`, the `169.254.169.254` metadata address, and a
      non-`/api/v1/` path. See `docs/Progress.md` for the full request/response log.
- [x] **2026-08-19:** Renamed `../ArcadeScore-rc1.zip` to `../ArcadeScore-rc1.zip.old-do-not-restore`
      (still outside the repo, so untracked either way, but no longer sitting under a name an
      unattended script or a future `extract-and-commit` accident could match).
- [x] **2026-08-19:** Added `*.zip` to `.gitignore`, and a pre-commit hook
      (`scripts/git-hooks/pre-commit`, installed to `.git/hooks/pre-commit` for this checkout)
      that blocks any commit to `app/routes/__init__.py` whose staged version registers fewer
      than 17 blueprints — the exact shape REG-01 took. Verified live: staging a truncated
      3-line version of the file correctly failed the hook (exit 1, 0 blueprints detected); the
      real file passes (exit 0, 17). Not committable via git itself (`.git/hooks/` isn't
      versioned) — documented as an opt-in one-time setup step in README's Contributing section.

**Exit criteria:** `git diff 4d8f260 HEAD` shows only the openssl.cnf addition. ✅ confirmed at
`bb3b548`.

---

## Phase 1 — Make the VPin Studio integration real

The headline feature. Score webhooks work; games, players, and the two new pause events do not.
Most of this is small and mechanical — the hard part was finding it.

### 1a. Fix the broken webhook cluster *(~40 lines, high value)* — ✅ done, `a54786a`

- [x] `VPIN-01` — read `data.get("id")` in `webhook_game` / `webhook_player`, not
      `gameID` / `playerID`.
- [x] `VPIN-02` — add `PUT /webhook/games` and `PUT /webhook/players` (no URL segment); the
      documented UPDATE shape puts the id in the body.
- [x] `VPIN-04` — add `"parameters": {"roomID": room_id}` to the `players` block in
      `register_vpin_webhook`.
- [x] `VPIN-05` — call `link_vpin_player(conn, {"server_url": …, "players": [{…}]})`.
- [x] `VPIN-06` — make `add_player_to_db` always return `(bool, str, Optional[int])`; dropped the
      `isinstance` workaround in `players.py`.
- [x] `VPIN-07` — accept `aliases` as list *or* JSON string (fixed in both `add_player_to_db` and
      `update_player_in_db`).
- [x] `VPIN-03` — DELETE handlers no longer demand a `roomID` the spec says isn't sent; resolve the
      ArcadeScore id straight off `vpin_games` / `vpin_players` by the URL-segment id, and switched
      the routes to `request.get_json(silent=True) or {}` so an empty DELETE body doesn't 500 before
      reaching the handler. Documented in-code that this can collide if two VPin servers reuse the
      same numeric id — full fix (matching by server too) needs `parameters` on DELETE, which VPin
      Studio doesn't send; revisit if that changes upstream.
- [x] Re-enabled the Game and Player subscription checkboxes in `index.jinja`; `index.js` already
      read them unconditionally (`?.checked || false`), so no JS change was needed there.

**Verified 2026-08-19 against a live VPin Studio server (192.168.8.149:8089) on the user's network:**
`/api/v1/games`, `/api/v1/games/{id}`, `/api/v1/games/scores/{id}`, `/api/v1/players`,
`/api/v1/players/{id}` all inspected directly. Imported a real game with historical score sync,
resynced it (confirmed idempotent — no duplicate rows), and called `/webhook/scores` and
`/webhook/players` directly with realistic payloads to exercise the actual handler code against
live data. This surfaced and fixed three real bugs no amount of static review had caught — see
"Fixed 2026-08-19" below.

**2026-08-19: End-to-end verification — done, confirmed live against real VPin Studio.**
- [x] End-to-end verification: create/rename/delete a table (or add a score) in VPin Studio's own
      UI reflects on the scoreboard within seconds with no manual refresh, confirming the
      registered webhook actually reaches this app over the network (not just simulated calls).
- [x] Confirmed the DELETE id-collision edge case doesn't bite in the user's actual setup (single
      VPin server = no risk).

**Fixed 2026-08-19 — found via live testing, not static review:**
- [x] `VPIN-13` — `createdAt` on both score and player objects is an ISO 8601 string
      (`"2025-01-13T23:26:42Z"`, sometimes with milliseconds), never the epoch-milliseconds int
      the code assumed. `webhook_log_score`'s `raw_timestamp / 1000` threw on every real score and
      was silently caught, stamping every webhook-logged score with "now" instead of its actual
      time — which also broke the exact-timestamp dedup check, risking duplicate rows on each
      retry (up to 5 attempts) and on any resync of an already-known score.
      `fetch_historical_scores` had a narrower version of the same bug: its `strptime` format
      required fractional seconds, so whole-second timestamps (common on raw NVRam-read scores)
      still fell through to "now". Fixed with one shared `parse_vpin_timestamp()`
      (`app/modules/utils.py`), used by both; unparseable timestamps are now skipped with a
      logged reason instead of silently mislabeled. Verified live: imported real historical scores
      and got back their actual VPin `createdAt` dates (e.g. `2026-04-06 23:11:48`, not today's
      date), and confirmed a resync produces zero duplicate rows.
- [x] `VPIN-14` — `webhook_player` mapped VPin Studio's player object using `fullName`/`alias`/
      `aliases`, but the real object (confirmed against `/api/v1/players/{id}`) uses `name` and a
      single `initials` string — there is no `fullName`, `alias`, or `aliases` field.
      `integrations.js`'s player-linking flow already used `name`/`initials` correctly, so this
      mismatch was isolated to the webhook handler. Every player UPDATE webhook was silently
      overwriting the real name/alias with `"Unknown Player"` / `null`. Verified live: an UPDATE
      webhook for a real, already-linked player now preserves their actual name and alias instead
      of corrupting it.
- [x] `VPIN-15` — `webhook_log_score`'s "no new scores found after retrying" failure path returned
      the reason under `message` instead of `error`, so the route's `.get("error", "Unknown error
      occurred")` fallback masked it — the same class of bug fixed across the webhook routes in
      Phase 1a, one instance missed. Fixed; confirmed the real reason now surfaces through
      `PUT /webhook/scores`.

### 1b. Support the new `pause` / `unpause` events *(new capability)* — ✅ done

The wiki now documents these; ArcadeScore had no concept of them.

- [x] Migration (`db_version` 1→2): added `pause_update`, `unpause_update` to `vpin_webhooks`,
      plus `webhook_token`, `last_event_at`, `last_error` (needed for 1c/1d below) and a new
      `vpin_servers` table, with backfill from existing `vpin_webhooks`/`vpin_games` rows.
- [x] `register_vpin_webhook`: emits `pause` / `unpause` blocks when selected.
- [x] Routes: `PUT /webhook/pause`, `PUT /webhook/unpause` (`app/routes/webhooks/pause.py`),
      resolving the game via `vpin_games` — implemented as one shared `webhook_pause_state(conn,
      data, paused)` in `app/modules/webhooks.py`.
- [x] Socket: `game_pause_state {gameID, roomID, paused}` → scoreboard toggles `.is-playing` on
      the card (green pulsing outline, `app/static/css/scoreboard.css`).
- [x] Wizard checkboxes ("Table Paused" / "Table Resumed" under a new "Now Playing" row).

### 1c. Harden the integration — mostly done

- [x] `VPIN-09` — replaced the removed `time.sleep(30)` with a bounded retry in
      `webhook_log_score`: up to 5 attempts, 2s apart via `eventlet.sleep` (non-blocking under
      eventlet), exits as soon as a genuinely new score is found.
- [x] `VPIN-10` — added `normalize_vpin_url`/`vpin_url` helpers to `app/modules/utils.py`; used
      everywhere a VPin URL is built or stored (`webhooks.py`, `vpinstudio.py`,
      `create_scoreboards.py`, `vpin_integrations.py`).
- [x] `VPIN-12` — `register_vpin_webhook` now generates a per-room `webhook_token`, sent as a
      `parameters.token` value on every CREATE/UPDATE registration; all CREATE/UPDATE handlers
      verify it via `_verify_webhook_token`. Rooms registered before this shipped have no stored
      token and are let through until they re-register (no forced break). DELETE calls remain
      unauthenticated — VPin Studio sends no `parameters` on DELETE at all, so there's nothing to
      check against; noted in code.
- [x] `SEC-01` — `/api/v1/proxy` now validates scheme, requires an `/api/v1/` path, blocks
      loopback/link-local (incl. 169.254.169.254 cloud metadata) targets, and fixes the
      `None`-before-`.rstrip()` crash on a missing `url` param.
- [x] Verified `score` (not `numericScore`) against a live VPin Studio server's
      `/api/v1/games/scores/{id}` response — the existing code was already correct.

### 1d. Finish the Integrations Menu — done, at reduced scope (see note)

Started in `4d8f260` and never completed — the HTML scaffold (`#vpin-studio-section`,
`#webhook-list`, "Resync Media/Scores/Players/Games" buttons) existed with zero JS behind it.

- [x] Per-room list of linked VPin servers — new `vpin_servers` table (fixes `VPIN-11`), populated
      automatically by the wizard and by the Integrations Menu, independent of whether a webhook
      is ever registered. `GET/POST /api/v1/scoreboards/<id>/vpin-servers`,
      `DELETE .../vpin-servers/<id>`.
- [x] View / delete registered webhooks without deleting the scoreboard —
      `GET/DELETE /api/v1/scoreboards/<id>/vpin-webhooks[/<id>]`, deregisters from VPin Studio
      first (best-effort) then removes locally.
- [x] Re-run player import and game import from an existing scoreboard. Players reuse the
      existing `/api/v1/players/vpin` + `/api/v1/players/vpin/import` endpoints directly (they
      were never tied to scoreboard creation). Games got a new
      `POST /api/v1/scoreboards/<id>/vpin-games/import` endpoint, backed by a shared
      `import_vpin_game_into_room()` (`app/modules/vpin_integration.py`) extracted from the
      wizard's per-game loop — used by both, so a game behaves identically regardless of which
      path added it.
- [x] Show webhook health: `last_event_at` / `last_error` columns, updated by
      `record_webhook_health()` after every inbound webhook call, shown in the webhook list.
- [x] *(Not originally scoped, added because the shared importer needed it anyway)* Made game
      import idempotent — re-importing an already-linked game now updates it in place instead of
      creating a duplicate, and preserves its existing `game_color` and per-game CSS. This also
      powers two of the scaffold's original buttons that weren't in the original 1d bullet list:
      **Resync Media** and **Resync Scores** (`POST /api/v1/scoreboards/<id>/vpin-games/resync`),
      which refresh already-imported games without restyling them. Historical-score sync is now
      dedupe-safe (checks for an existing identical row before inserting), which it wasn't before
      — harmless for the one-shot wizard flow, but would have double-logged scores on repeat use.
- [x] **2026-08-19:** Registering a *new* webhook subscription against an existing room — this
      was the scope deliberately cut from the original Phase 1d pass, and it turned out to
      matter in practice: a room created outside the wizard (e.g. via direct game import) had no
      way to ever get a webhook at all. Added `POST /api/v1/scoreboards/<id>/vpin-webhooks`
      (`app/routes/api/v1/vpin_integrations.py`), reusing the existing `register_vpin_webhook()`
      the wizard already calls, gated by `@require_room_admin`. A "Register Webhook" button in the
      Registered Webhooks section (not per-server — a server picker inside the panel instead,
      since registering one isn't really an action "on" a particular linked server) opens the same
      subscription checkboxes as the wizard. Verified live: the route's validation paths (missing
      `server_url`, no events selected, unknown room) all respond correctly; the actual VPin Studio
      registration call itself was left for the user to trigger from the UI rather than done on
      their behalf, since it writes real state to their live server.
      Still not built: editing an existing webhook's subscriptions in place — delete and
      re-register covers it for now.

Frontend: `app/static/js/scoreboard/integrations.js` (new), wired into `scoreboard.jinja`'s
existing VPin Studio menu section.

**Fixed 2026-08-19 (round 2) — found by the user importing their real ~194-game library while
a scoreboard tab was open, not by testing:**
- [x] `VPIN-16` — `game_update`'s socket payload (`save_game_to_db`) never carries a `scores`
      field by design (scores are always pushed separately), but `games.js`'s `createGameCard` →
      `generateScoreHTML` unconditionally called `game.scores.filter(...)`. Harmless when a game
      already has a card (the update path never touches scores), but a brand-new game arriving
      via socket while a tab is open has no card yet, hits the create path, and threw
      `Cannot read properties of undefined (reading 'filter')` — reported live by the user
      mid-import. A second latent bug in the same function: the `ScoreType` "extra fields"
      block referenced `score.event`/`score.wins`/`score.losses` outside the `.map()` where
      `score` is actually defined — would have thrown `ReferenceError` for any game with a
      `score_type` other than `hideBoth`. Both fixed; confirmed live with a socket client
      joined to the room that the real `game_update` payload has no `scores` key.
- [x] `VPIN-17` — historical-score sync in `import_vpin_game_into_room` (used by the wizard,
      import, and resync) wrote real data to `highscores` but never emitted `game_score_update`,
      so an already-open tab showed "No scores yet." forever after a bulk import until manually
      refreshed. Added the same emit `webhook_log_score` already does for the live path.
      Confirmed live: a freshly-imported game now gets `game_update` (empty card) immediately
      followed by `game_score_update` with its real scores.
- [x] `VPIN-18` — neither `import_vpin_games`/`resync_vpin_games` (routes) nor the wizard's
      per-game loop (`create_scoreboards.py`) isolated failures per game — one game throwing
      (flaky media download, transient DB error) aborted the whole request, silently abandoning
      every game after it in the list while everything before it stayed committed. This matches
      what the user saw (158/194 games imported, then nothing, no error surfaced). Root cause of
      that specific run couldn't be reproduced (all 35 missing games imported cleanly on retry —
      likely a transient network blip), but the missing isolation is real regardless. Wrapped
      each per-game call in its own try/except in all three loops.

---

## Phase 2 — Close the gap between the README and reality

Three features are advertised but not implemented. Each is a small, self-contained project.

### 2a. Authentication *(`SEC-05`, `SEC-02`)* — ✅ done, live-verified

The README promises *"(Optional) Password-protected admin menu"*. The `settings.secure` column
existed; the `save-password-btn` element existed but was entirely commented out with no backend
behind it at all — this was built from scratch.

- [x] `POST /api/v1/settings/<room_id>/password` — set/change/clear, hashed via werkzeug
      `generate_password_hash`. Open when no password exists yet (so a fresh room stays usable);
      once one is set, changing or clearing it requires already being logged in.
- [x] Flask session cookie (`session[f"room_{id}_admin"]`), gated by a new
      `@require_room_admin` decorator (`app/modules/auth.py`) with pluggable room-id resolution
      (URL kwarg → JSON body → query string → form body; `room_id_from_game=True` resolves via a
      DB lookup for games/style routes keyed by a game id instead). A separate
      `require_any_room_admin` covers import/export, which touch every room's data at once and
      have no single room to check.
- [x] Applied to: delete/rename scoreboard, clear scores, clear games, all style writes, settings
      PUT, game CRUD (create/update/delete/hide/reorder), player CRUD (players are global data
      with no owning room, so these are gated by whichever room's admin menu the action was taken
      from — the frontend sends `roomID` alongside), VPin Integrations Menu actions, import,
      export. `POST /api/v1/players/vpin[/import]` are reachable both from the wizard (no room
      exists yet) and the Integrations Menu (existing room) — `optional_room=True` lets them
      through ungated only when truly no room is in context.
- [x] `GET .../auth-status`, `POST .../login`, `POST .../logout` round out the flow. Frontend: a
      login-gate modal in front of the hamburger menu (`hamburgerMenu.js`) when a password is set
      and the session isn't authenticated yet, and a real password-set/change/remove form +
      logout button in the admin section (`settings.js`), replacing the dead, commented-out
      scaffold.
- [x] Honoured the four stored-but-unenforced flags: `public_scores_enabled` /
      `public_score_entry_enabled` gate the legacy iScored-compatible `publicCommands.php` reads
      and score submission; `api_read_access` gates the modern `/api/<user>` JSON dump.
      `api_write_access` has nothing to gate yet — there's no write route on that modern API
      today — so it's left stored but inert, same as before. All four default to `TRUE`, so
      nothing changes for existing installs unless explicitly toggled off.
- [x] `SECRET_KEY` (`SEC-03`): env var wins if set, otherwise a random key is generated once and
      persisted to `data/secret_key` so restarts don't invalidate every session. `debug=True`
      (`SEC-04`): now `ARCADESCORE_DEBUG=1` opt-in, default off.

**Verified against the running app**, not just review: full login/logout/wrong-password cycles
with real cookie jars: password set → auto-logged-in → mutating action blocked without the
cookie, allowed with it → wrong password rejected (401) → correct password accepted → logout
actually revokes access → password removal re-opens the room. Also verified the `room_id_from_game`
resolution path (hiding a game while logged out as that game's room correctly 401s) and
`require_any_room_admin` (export blocked/allowed correctly), and all four API-access flags
(each one disabled independently returns 403, default state stays fully open). Zero tracebacks
across the entire test session.

**Known gap, left open deliberately:** `store_image`/`upload-image` (styles.py) have no room or
game id in their payload to gate on — they just save a file to disk, and the room-scoped mutation
that actually *uses* the resulting path (`save_game`) is already gated. Low severity (bounded by
`secure_filename`, no data exposed) but worth revisiting if this becomes a real concern.

### 2b. Socket.IO rooms *(`BUG-22`)* — ✅ done, live-verified

- [x] `@socketio.on("join")` handler joins `room_{roomID}` (client emits it on every `connect`,
      including reconnects). `app/modules/socketio.py`.
- [x] Scoped every room-specific emit with `room=`/`to=`: `game_update`, `game_deleted`,
      `game_visibility_toggled`, `game_order_update`, `game_score_update`, `game_pause_state`,
      `styles_updated` (when a room_id is given — presets-only changes stay global),
      `settings_updated`. `players_updated` stays global on purpose — players are global data
      (`BUG-25`), not room-scoped.
- [x] `settings_updated`: rather than hand-patching every scroll timer/date-format/long-name
      toggle live in place across module boundaries, the tab that made the change applies it
      optimistically (unchanged); every *other* tab showing the same room just reloads. Filtered
      by a per-page-load `clientId` (`crypto.randomUUID()`, alongside the existing `roomID`
      global) so the originating tab doesn't reload itself off its own echo.
- [x] Fixed `emit_player_changes`' `BUG-14` — it selected a `players.room_id` column that doesn't
      exist, so the query threw on every call, silently swallowed by a bare `except`, and
      `players_updated` had never once fired. Removed the bogus column/room concept entirely
      (players are global) rather than trying to give it one.
- [x] **Also fixed while touching this** (`progress_update` cross-tab popup, the concrete example
      the roadmap named for `BUG-22`): extended the `session_id` mechanism export already used —
      creation now generates one too — so a background task's progress modal only shows on the
      tab that started it, not every open tab. Along the way, fixed `BUG-18`
      (`emit_progress(-1, ...)` missing its `app` arg in `export_task.py`'s 7z-not-found path) and
      `BUG-16`'s duplicate instance in `save_game_to_db` (`SELECT ... FROM settings LIMIT 1`
      instead of scoping to the game's own room) — both were adjacent to code I was already
      rewriting for this.

**Verified against the running app** with a real `python-socketio` client (not just static
review): a client that joined `room_1` received a room-scoped `game_visibility_toggled` event; a
client that never joined did not. Both received the global `players_updated` event. A
`settings_updated` PUT correctly echoed back with the sent `client_id`.

### 2c. Player management UI — mostly already there; corrected the original write-up

`docs/Progress.md`'s original review said *"the scoreboard menu doesn't expose"* edit/delete/hide.
That was wrong — checked directly this session (`players.js`, `scoreboard.jinja`) and live-verified
against the running app: clicking a player opens a view with working Edit/Hide buttons, Edit opens
a form with a working Delete button, and all three round-trip correctly through the existing
backend. The real gap was much narrower:

- [x] Edit / delete / hide player from the scoreboard admin menu — **already worked**, confirmed
      live (`PUT`, `POST .../toggle_visibility` both round-tripped correctly against the running
      app before any changes this session).
- [x] Fixed the known bug: "New player alias default changes when adding new aliases". Root cause:
      each alias's radio `value` was set once at creation (usually blank) and never kept in sync
      with what the user typed into the adjacent text input, so the submitted default silently
      fell back to whichever alias happened to be first. Added an `input` listener to keep them in
      sync (`app/static/js/scoreboard/players.js`).
- [x] Global vs. per-room (`BUG-25`): keeping global, matching the schema and every existing code
      path (the same player list renders identically in every room's admin menu; nothing in the
      app has ever treated players as room-owned). Documented here rather than left implicit.
      Auth for player mutations (Phase 2a) works around this by gating on whichever room's admin
      menu the action was taken from, not on any notion of the player "belonging" to a room.

---

## Phase 3 — Make 1.0 upgradeable

This phase's original write-up was stale by the time work on it started: `db_version` was already
bumped to 2 with a real, working migration back in Phase 1b (webhook token/pause columns, the new
`vpin_servers` table), and the README currently contains no "delete your database" warning at all —
checked directly, nothing to remove there. `BUG-26` as originally worded ("every step commented out")
no longer applied.

- [x] `BUG-26` / migration ladder, `db_version` 2 → 3 (`app/modules/database.py`,
      `app/modules/models.py`): two real schema changes had never gotten a migration path, so they
      only landed on a genuinely fresh install — `players.hidden` (`init_db`'s `CREATE TABLE players`
      includes it, but nothing ever added it to an *existing* table) and the 3 non-Default presets
      (Neon Glow, Retro Arcade, Cyberpunk — only inserted when the `presets` table was empty at first
      boot). Confirmed `app/modules/players.py` reads/writes `players.hidden` unconditionally in
      `get_all_players`, `get_player_from_db`, and `toggle_player_score_visibility` — a database
      missing that column throws `no such column: hidden` on ordinary scoreboard page loads, not
      just an edge case. Fixed with the same incremental pattern the v2 migration already
      established: `ALTER TABLE players ADD COLUMN hidden ...` if missing, `INSERT OR IGNORE` the 3
      presets by name (never touches a user's own preset, including one they renamed to match).
- [x] Made the import endpoint's version gate meaningful (`app/routes/api/v1/importExport.py`): it
      already correctly rejected an imported DB *newer* than the running app, but an imported DB
      that's *older* got swapped straight into `data/highscores.db` with no migration applied —
      `migrate_db()` only ever ran once, at app boot, so a restored older backup left the live app
      running against a stale schema until the next full restart. Now calls `migrate_db(DATA_PATH)`
      immediately after the swap.
- [x] **Verified live, not just reviewed:** built a synthetic "old" database (pre-`hidden` column,
      single preset, `db_version` 2) and ran `migrate_db()` directly against it — confirmed the
      column and all 3 missing presets appear, the existing `Default` preset and player rows are
      untouched, `db_version` reads 3, and a second call is a clean no-op. Then built a full synthetic
      old-schema `.7z` import archive around a copy of the live dev database, POSTed it to
      `/api/v1/import`, and confirmed the live database was at `db_version` 3 with the column and all
      4 presets present *immediately* afterward — no server restart in between — while the 194
      games / 106 scores / 5 players already in that database came through completely intact.
- [ ] Write the upgrade path from the last public RC build and test it on a real (not synthetic)
      user database. **Deliberately deferred, not blocking 1.0** — build 1 has no prior build to
      upgrade *from* yet. Revisit once build 2 exists and a real build-1 database is available:
      install build 1 for real, generate genuine data on it, then upgrade in place to build 2 and
      confirm the migration ladder (currently only exercised against synthetic/hand-built old
      databases) handles a real one correctly.
- [x] Confirmed there is no "delete your `highscores.db`" warning in the current README — this
      bullet was already moot.

---

## Phase 4 — Correctness cleanup ✅ done

Batch of independent fixes from `BUG_REVIEW.md`, roughly by value:

- [x] `BUG-13` — restored `def get_docker_host_ip():` (`app/modules/utils.py`); its body had been
      running as an orphaned tail of `cleanup_unused_images` since a lost merge. Also wired it in:
      `get_server_base_url()`'s Docker branch now auto-detects the host's LAN IP via
      `get_docker_host_ip()` when `SERVER_HOST_IP` isn't set, instead of hardcoding `"localhost"`
      (which isn't reachable from another machine on the network for VPin's webhook callback URL).
- [x] `BUG-15` — `save_preset` (`app/routes/api/v1/styles.py`) now resolves the game's own
      `room_id` first and scopes both the INSERT and the overwrite UPDATE's `settings` subqueries
      to it, instead of an unqualified `FROM games g, settings` cross join that broke as soon as a
      second scoreboard existed.
- [x] `BUG-16` — fixed both instances found: `save_game_to_db` and the inbound `webhook_game`
      handler both scoped `settings`/`game_color` to the wrong room on update (Phase 1/2b work).
      `get_global_style` (styles.py) still has its own `LIMIT 1` instance — that route takes no
      room_id param at all today, so fixing it means changing its contract, not just its query;
      still open.
- [x] `BUG-21` — `store_image` now returns `/static/images/<type>/<filename>`, matching
      `upload_image`'s shape, instead of a bare filename that `cleanup_unused_images` couldn't
      recognize as in-use and deleted on the next export.
- [x] `BUG-19` — `addScore` (`app/routes/api/v1/publicCommands.py`) now assigns
      `player_id_row = cursor.fetchone()` in the `long_names_enabled == "TRUE"` branch too,
      instead of raising `NameError` on every legacy score submission from a room with long names
      enabled.
- [x] `BUG-20` — the same handler's `game_score_update` payload had `fullName`/`defaultAlias`
      swapped relative to the `p.full_name, p.default_alias` SELECT order; fixed to match. (The
      HEAD-tree duplicate in `app/routes/settings.py` no longer exists post-REG-01-revert.)
- [x] `BUG-17` — `get_high_scores` (`app/modules/scores.py`) now takes a `room_id`, restores the
      `WHERE h.room_id = ?` filter that had been commented out, and returns keys that actually
      match the selected columns (`gameID` was previously labeled `gameName` while actually
      holding `game_id`, `roomID` was actually `event`, etc.). `/highscores`
      (`app/routes/api/v1/scores.py`) now requires `?roomID=`, returning 400 if it's missing — the
      endpoint has no known frontend caller today (legacy iScored-compatible API, like
      `publicCommands.php`), so this only tightens an already-effectively-dead route.
- [x] `BUG-18` — fixed both instances: `export_task.py`'s 7z-not-found path and the analogous
      pattern in `create_scoreboards.py` were absorbed into a `progress()` closure (Phase 2b) that
      always passes `app` correctly.
- [x] `BUG-23` — `new_sort_order` (`app/modules/games.py`) now checks `max_sort is not None`
      instead of truthiness, so a room's first hand-added game after `MAX(game_sort) == 0` no
      longer collides with sort order `1`.
- [x] `BUG-24` — already fixed; no `utcfromtimestamp`/`utcnow` calls remain anywhere in the
      codebase (superseded by `parse_vpin_timestamp()`, Phase 1a).
- [x] `BUG-27` — deleted every manual `close_db()` call across the codebase (130 call sites, 16
      files) rather than adding the missing ones on early-return paths; `app.teardown_appcontext`
      already closes `g.db` after every request regardless of how the view function returns, so
      the manual calls were redundant everywhere and simply hadn't been added everywhere. Also
      dropped `close_db` from each file's now-unneeded import.
- [x] `BUG-28` — confirmed resolved by the REG-01 revert; `app/routes/settings.py` (the file with
      the `conn.close()` mid-request bug) no longer exists, only `app/routes/api/v1/settings.py`,
      which never had this pattern.
- [x] `SEC-07` — added a shared `escapeHtml()` helper to `app/static/js/utils.js` (previously
      duplicated locally in `integrations.js`, now imported from there too) and applied it to
      every VPin-sourced string (player names, initials, game display/file/ROM names, highscore
      type) interpolated into the wizard's `innerHTML` templates in
      `app/static/js/index/index.js` — both the visible text and the `data-*` attribute values
      that get read back into a later template. A table or player named e.g. `<img src=x
      onerror=...>` no longer executes in the browser.

---

## Phase 5 — Known bugs from the README ✅ done

This phase's original write-up was stale by the time work started on it — written from an even
earlier state of the README than the one actually in the tree. The README's real "Known Bugs"
list at the time work began was 7 items (mobile scroll, slow drag, a drag "shadow" glitch, and 4
already-fixed player bugs left unremoved), not the 4 originally guessed here. All 7 are now fixed
or confirmed already-fixed and removed from the README, which now reads "No known bugs at the
moment."

- [x] Vertical score scrolling on mobile — two compounding bugs, both in
      `app/static/js/scoreboard/dragScroll.js` / `app/static/css/scoreboard.css`:
      `.game-container`'s `touch-action: none` intersects down the DOM tree and silently overrode
      `.score-container`'s own `touch-action: pan-y` for every card, and the vertical drag
      handler's `touchstart` bubbled up into the horizontal drag handler on `gameContainer`
      (no `stopPropagation()`), so a single touch meant to scroll one card's scores also kicked
      off a horizontal drag of the whole row. Fixed `touch-action` to `pan-y` (still blocks native
      horizontal panning, which the custom JS drives manually) and added the missing
      `stopPropagation()`.
- [x] Drag reordering slow when dragging down the list, **and** "Games Menu drag and drop loses
      shadow placement after first change (refresh fixes it)" — same root cause, one fix.
      `app/static/js/scoreboard/gameDragDrop.js`'s `getDragAfterElement` was supposed to exclude
      the item being dragged via `:not(.dragging)`, but nothing ever added a `.dragging` class —
      `handleDragStart` set inline `style.opacity` instead — so the dragged item kept comparing
      against its own constantly-shifting bounding box as it moved, getting worse the further
      down the list you dragged. The CSS meant to show the dimmed "shadow" during a drag
      (`.sortable-list li.dragging { opacity: 0.5; }`) also targeted a class (`sortable-list`)
      that doesn't exist anywhere in the codebase — the actual list has class `sortable`. Fixed
      both: real `.dragging` class toggling (fixing the selector logic) and the CSS class name
      (`.sortable li.dragging`). Also removed a duplicate `updateGameOrder()` call — `drop` and
      `dragend` both fired it on every single reorder, doubling the save requests.
- [x] Reverse sort — the `sort_ascending` column survived in the schema and was threaded through
      every layer (DB, API payloads, socket events, DOM datasets) but was never actually read
      anywhere; every score query hardcoded `ORDER BY h.score DESC`, and the form control that
      would have let an admin set it was commented out of `scoreboard.jinja`. Fixed both ends:
      un-commented the "Sort Ascending" field (`gameManagement.js` already read/saved it once
      present, via `FormData`, no JS change needed there), and every score-fetching query across
      `app/modules/scores.py`, `app/modules/webhooks.py`, `app/modules/vpin_integration.py`,
      `app/routes/api/v1/publicCommands.py`, and `app/routes/api/v1/users.py` (2 queries) now
      orders by `CASE WHEN g.sort_ascending = 'TRUE' THEN h.score ELSE -h.score END ASC` instead
      of a flat `DESC`. Verified live: set a game to ascending, added two real scores through
      `publicCommands.php`'s `addScore`, and confirmed both the initial Jinja-rendered page and
      the `/api/<user>` JSON endpoint returned the lower score first.
- [x] "Selected Style Preset is not remembered when new games are added via webhooks" — found via
      literal `# TODO: Should be loaded from default style` comments already marking the gap in
      `webhook_game` (`app/modules/webhooks.py`). Root cause was one level deeper than the TODO
      suggested: `settings.default_preset` was never actually written at room creation (every
      room silently sat at the schema default of preset `1`, regardless of what the wizard's user
      actually picked), so there was nothing for the webhook path to look up even if it tried.
      Fixed both: `create_scoreboards.py` now persists the wizard's chosen `preset_id` into
      `settings.default_preset`, and `webhook_game` now resolves that preset's CSS for a genuinely
      new game. Also fixed an adjacent, more impactful bug found while touching this: the same
      hardcoded-`None` styling was applied unconditionally on *every* UPDATE webhook too (e.g. a
      plain name change from VPin Studio), silently blanking a game's existing styling on every
      metadata update - now preserved from the existing row instead, the same way `game_color`
      already was.
- [x] Removed the 3 already-fixed player bugs still listed in the README ("New Player alias
      default changes when adding new aliases" — fixed in Phase 2c's alias-radio-sync fix;
      "Deleting players requires a refresh to propigate correctly" and "Changing players default
      alias requires page refresh to propigate" — both fixed by Phase 2b's `BUG-14` fix, which
      made the `players_updated` socket event fire for the first time; `refreshPlayerList()`
      already fully re-renders `#player-list` from that event). Confirmed each fix is still
      present in the code (not just "fixed then regressed") before removing the README entries.
      The two already-obsolete entries this phase's original write-up guessed at (VPS image
      compression, default-avatar deletion) and the "most settings don't work" claim were already
      gone from the README by the time this phase started — someone had already cleaned those up.
      README's "Known Bugs" section now reads "No known bugs at the moment" with a link to file
      an issue; also fixed two stale `yourusername/Arcadescore` placeholder links elsewhere in the
      README to the real repo.

---

## Phase 6 — Polish and stretch ✅ done

- [x] **2026-08-19: Hamburger menu + creation wizard UI modernization.** The whole
      hamburger menu (`app/templates/scoreboard.jinja`) and the scoreboard-creation wizard
      (`app/templates/index.jinja`) had no shared design system — zero CSS custom
      properties anywhere in the codebase, colors hardcoded ad hoc per-selector
      (independently in `scoreboard.css` and `index.css`, no sharing), at least 6 different
      border-radius values, and every success/error/destructive-confirm was a native
      `alert()`/`confirm()` (45 call sites). Built once, applied everywhere:
      - CSS custom properties + a unified `.btn`/`.btn-secondary`/`.btn-danger`/
        `.btn-small`/`.btn-icon` button system in `global.css`.
      - `showToast()`/`showConfirm()` in `utils.js`, replacing every `alert()`/`confirm()`
        across `players.js`, `settings.js`, `styleManagement.js`, `gameManagement.js`,
        `integrations.js`, `VPSDB.js`, and `index.js`. `players.js`/`settings.js`/
        `styleManagement.js` had to move from classic `<script>` tags to `type="module"`
        to import them.
      - `initAccordions()`/`initDropdowns()` for collapsible `.menu-section-part`s (Styles'
        3 subsections; Admin split into Room & Display / Password / Danger Zone) and a
        kebab menu consolidating the VPin server row's 5 grouped actions (Import Games/
        Players, Resync Media/Scores, Register Webhook) — destructive actions
        (Unlink/Delete/Clear/Hide) deliberately stay as always-visible buttons, never
        hidden in a menu.
      Found and fixed several real bugs along the way, unrelated to styling: a CSS
      specificity bug (`:where()`-wrapped the legacy `.menu-section button` fallback,
      which as an element+class selector was silently beating the new single-class
      `.btn`); `scoreboard.jinja`'s player-view buttons and `#add-alias-button` had been
      rendering fully unstyled (`class="btn"` was never defined on this page before now;
      `secondary-btn` was defined only on `index.css`, never loaded here); `Clear Scores`/
      `Clear Games`/`Delete Scoreboard` were rendering as plain gray buttons despite being
      destructive (`.delete-scoreboard-btn` targeted a class the button never had); and
      `settings.js`'s debounced auto-save read four checkboxes that are commented out in
      the template, throwing on the null `.checked` read and silently breaking the entire
      Admin Settings auto-save (room name, date format, scrolling, everything) before the
      save request ever fired.
- [x] **2026-08-19: Self-updater**, checking GitHub Releases. New "Updates" modal on the
      landing page, next to Import/Export and the Ko-fi link — app-wide/instance-level,
      not tied to any one room, matching where those two already live.
      (`app/modules/updater.py`, `app/routes/api/v1/updates.py`,
      `app/static/js/index/updates.js`). Versioning moved from semver to a plain
      incrementing build number (new root `BUILD_NUMBER` file) — the release's own
      `published_at` timestamp is the human-visible "released on" date, so there's no
      manual step to get wrong. Pre-release opt-in (off by default), cached status in the
      `meta` table (same pattern `db_version` already uses), gated by
      `require_any_room_admin` like import/export. "Update Now" (git checkouts only) runs
      `git fetch`/`checkout` + `pip install`, then attempts a best-effort automatic
      restart, falling back to a "restart manually" message if it doesn't come back —
      confirmed live, not just reviewed, including three real bugs the restart mechanism
      didn't survive without: `run.py`'s startup banner crashing non-UTF-8 Windows
      consoles (the exact issue this session kept working around by hand), eventlet's
      monkey-patched `subprocess.Popen` silently failing to produce a real detached
      process on Windows (fixed via `eventlet.patcher.original()`), and a genuine
      port-release race against the exiting old process (fixed with a bind
      retry-with-backoff in `run.py`, which also hardens *every* restart, not just
      updater-triggered ones). `docker-publish.yml` updated as a direct consequence of
      the versioning change (a bare integer tag matched none of its old semver regexes;
      now requires one and decides `:latest` from GitHub's own pre-release checkbox
      instead of guessing from tag text) and the Dockerfile now ships `BUILD_NUMBER`.
      Two local-testing overrides (`ARCADESCORE_UPDATE_REPO`, `ARCADESCORE_UPDATE_FEED_OVERRIDE`,
      documented in `.env.sample`) let this be exercised without ever touching the real
      project's releases.
- [x] **2026-08-19: Font installer.** All four preset fonts vendored locally
      (`app/static/fonts/`, `@font-face` rules in `app/static/css/fonts.css`, loaded on both
      `index.jinja` and `scoreboard.jinja`) — no more silent fallback to sans-serif, and no
      runtime dependency on an external font CDN for a self-hosted app. Orbitron (Neon Glow) and
      Press Start 2P (Retro Arcade) are the real, correctly-licensed (SIL OFL) Google Fonts the
      presets already named. `Federation` (Default) and `Cyber` (Cyberpunk) turned out to be
      personal-use-only freeware fonts (typical of dafont.com-style sites) — not safe to bundle
      into this MIT-licensed, openly-redistributed repo. Per user decision, substituted
      open-licensed (SIL OFL) lookalikes instead: Audiowide and Bungee. New `db_version` 5
      migration rewrites any existing preset *or already-created game's* `css_title`/`css_initials`
      that still referenced the old names — a preset is only a copy source at game-creation time,
      not a live reference, so games created from Default/Cyberpunk had the old font name baked
      into their own row. Verified live against the real dev database: all 4 vendored `.woff2`
      files serve 200, and the migration correctly rewrote both presets and all 194 real
      `Federation`-referencing games in the MorrisArcade room with zero remaining after.
      Full OFL license text bundled per font (`app/static/fonts/OFL-licenses/`).
- [x] **2026-08-19: Tests — started with the webhook handlers**, per this item's own suggestion.
      `pytest` (new `requirements-dev.txt`, `pytest.ini`), `tests/conftest.py` builds a real
      throwaway SQLite database per test via the actual `init_db()`/`migrate_db()` a fresh install
      goes through (not a hand-rolled schema that could drift from reality), plus small fixture
      helpers (`make_room`, `make_game`, `make_webhook`, `make_player`, `link_vpin_game`,
      `link_vpin_player`). One real gotcha: `flask_socketio.SocketIO.emit()` reads `self.server`,
      which stays `None` until `init_app()` runs at least once — webhook handlers call it
      unconditionally (not every call site is mocked per-test), so a session-scoped fixture calls
      `socketio.init_app()` once against a bare Flask app with no real transport, making every
      emit a safe no-op broadcast to zero clients, same as what actually happens for a room nobody
      has open. `tests/test_webhooks.py`: 16 tests across `webhook_log_score`, `webhook_player`,
      `webhook_delete_player`, `webhook_game`, `webhook_delete_game`, `webhook_pause_state` —
      token verification, dedup, the auto-hide integration, and direct regression tests for two
      bugs fixed this session (VPIN-14's `name`/`initials` vs `fullName`/`alias` field mix-up, and
      `webhook_game` blanking a game's existing style/color on every plain UPDATE). Verified the
      regression tests actually have teeth, not just passing trivially: reverted the
      `webhook_game` style-preservation fix via `git stash` and confirmed the two style tests
      failed with it gone, then restored the fix and confirmed all 16 pass again.
- [x] **2026-08-19: Performance pass** — profiled against the real 194-game MorrisArcade room
      rather than a synthetic one. Server-side render (`/morrisarcade`, the Jinja-rendered page)
      measured a consistent ~210ms for a ~600KB payload across 3 runs — no N+1 query pattern
      (games/scores/players/aliases are each one query, grouped in Python) and not worth chasing
      further for a self-hosted app serving a handful of concurrent wall displays. The real,
      measurable issue was client-side: `resetScoreScroll()` (`app/static/js/scoreboard/
      autoScroll.js`), the "return score list to top after idle" half of vertical auto-scroll, ran
      `document.querySelectorAll(".score-container")` — a full DOM query across every game card —
      on every 30ms interval tick, i.e. 33 times a second, continuously, for as long as vertical
      auto-scroll is active. That's not a rare state; it's this app's normal steady state on an
      idle wall display. Fixed by querying once when the interval (re)starts instead of on every
      tick — cheap enough to re-query on every idle-cycle restart (which already happens on any
      user interaction) without paying the cost 33x/second. Confirmed the hot live-update path
      (`game_score_update`, by far the most frequent event during actual gameplay) was already
      efficient — `updateGameScores` targets one card via `[data-id]` attribute selector and only
      replaces that card's own score HTML, with no cost that scales with total game count.
- [x] **2026-08-19: macOS deployment script** — turned out to already exist. `setup.sh` already
      branches on `$OSTYPE == darwin*` to install `p7zip` via Homebrew, and every other step
      (venv creation, `pip install`, starting the server) is portable POSIX bash with nothing
      requiring bash 4+ (macOS still ships an ancient bash 3.2) or any Linux-only tool. Confirmed
      via code review; not run on real Mac hardware from this environment, so the README notes
      that gap honestly rather than claiming full verification.
- [x] hi2txt / MAME support — intentionally not built. README's Planned Features list already
      lists it correctly as planned-not-committed (its "looking for assistance" framing referenced
      here was from an even earlier README snapshot; the current one is fine as-is). This is the
      one Phase 6 item this pass deliberately left alone, per its own instruction.

**Deliberately deferred past 1.0:** public tournaments, friend score syncing, public tournament
brackets. All three imply a hosted service and an account system; none should gate a self-hosted
1.0, and all three become far more expensive if Phase 2a isn't done first.
