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
- [ ] Delete `../ArcadeScore-rc1.zip` or move it well outside the repo so this can't recur.
- [ ] Add a `.gitignore` entry for `*.zip` and a pre-commit sanity check on `app/routes/__init__.py`
      blueprint count.

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

**Not yet done — needs an actual webhook delivery from VPin Studio itself, not a simulated call:**
- [ ] End-to-end verification: create/rename/delete a table (or add a score) in VPin Studio's own
      UI and confirm it reflects on the scoreboard within seconds with no manual refresh. Today's
      testing proved the handlers behave correctly when called with realistic data; it did not
      prove VPin Studio's registered webhook actually reaches this app's endpoint over the
      network (firewall/routing between the two machines, `get_server_base_url()`'s LAN-IP
      detection picking the right interface, etc.).
- [ ] Confirm the DELETE id-collision edge case above doesn't bite in your actual setup (single
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

Right now the README tells users to *delete their database* when upgrading. That's disqualifying for
a 1.0.

- [ ] `BUG-26` — implement the migration ladder. `db_version` has been pinned at 1 forever and every
      step in `migrate_db` is commented out.
- [ ] Bump `db_version` for the `vpin_webhooks` / `players.hidden` / 4-preset changes that currently
      only land on fresh installs.
- [ ] Make the import endpoint's version gate meaningful.
- [ ] Write the upgrade path from the last public RC build and test it on a real user database.
- [ ] Remove the "delete your `highscores.db`" warning from the README.

---

## Phase 4 — Correctness cleanup

Batch of independent fixes from `BUG_REVIEW.md`, roughly by value:

- [ ] `BUG-13` — restore the lost `def get_docker_host_ip():`; its body currently runs inside
      `cleanup_unused_images`.
- [ ] `BUG-15` — `save_preset`'s cross join breaks entirely once a second scoreboard exists.
- [x] `BUG-16` — fixed both instances found: `save_game_to_db` and the inbound `webhook_game`
      handler both scoped `settings`/`game_color` to the wrong room on update (Phase 1/2b work).
      `get_global_style` (styles.py) still has its own `LIMIT 1` instance — that route takes no
      room_id param at all today, so fixing it means changing its contract, not just its query;
      still open.
- [ ] `BUG-21` — `store_image` returns a bare filename; those files get deleted on the next export.
- [ ] `BUG-19`, `BUG-20` — `publicCommands` `NameError` and swapped name fields.
- [ ] `BUG-17` — `/highscores` returns three wrong fields and every room's scores.
- [x] `BUG-18` — fixed both instances: `export_task.py`'s 7z-not-found path and the analogous
      pattern in `create_scoreboards.py` were absorbed into a `progress()` closure (Phase 2b) that
      always passes `app` correctly.
- [ ] `BUG-23`, `BUG-24`, `BUG-27`, `BUG-28` — small ones.
- [ ] `SEC-07` — escape VPin-sourced strings in the wizard's `innerHTML` templates.

---

## Phase 5 — Known bugs from the README

- [ ] Vertical score scrolling on mobile.
- [ ] Drag reordering is slow when dragging down the list.
- [ ] Reverse sort — the `sort_ascending` column survives; the UI was pulled in `02b9f2b`.
- [ ] Remove the two entries that are already fixed (VPS image compression, default-avatar deletion)
      and the stale "most settings don't work" claim.

---

## Phase 6 — Polish and stretch

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
- [ ] **Font installer.** Three of the four shipped presets reference fonts (`Federation`,
      `Orbitron`, `Press Start 2P`, `Cyber`) that are never loaded, so they silently fall back to
      sans-serif. Either vendor the fonts or fix the presets — right now the themes don't look like
      their screenshots.
- [ ] Tests. There are currently none. Start with the webhook handlers: they're pure functions over
      a connection and a dict, which is the easiest possible thing to test, and they're where the
      bugs are.
- [ ] Performance pass (README item) — profile the scoreboard render with 100+ games.
- [ ] macOS deployment script.
- [ ] hi2txt / MAME support — README notes this is *"looking for assistance"*; keep it flagged as a
      contribution opportunity rather than a commitment.

**Deliberately deferred past 1.0:** public tournaments, friend score syncing, public tournament
brackets. All three imply a hosted service and an account system; none should gate a self-hosted
1.0, and all three become far more expensive if Phase 2a isn't done first.
