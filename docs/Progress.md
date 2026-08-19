# ArcadeScore — Progress

**Branch:** `1.0.0-rc` · **Reviewed at:** `556c7b2` · **Date:** 2026-08-18

---

## ⚠ Read this first: the working tree is not your latest code

Commit `556c7b2` ("Add WebSocket support and settings management", 2026-08-16) is **not** a feature
commit. It is a Feb-2025 snapshot that was extracted over the repo and committed on top of
12 commits of March-2025 work. Evidence:

| Signal | Finding |
|---|---|
| Commit gap | `4d8f260` (2025-03-17) → `556c7b2` (2026-08-16), 17 months |
| Source artifact | `../ArcadeScore-rc1.zip`, dated **Feb 9 2025**, sits next to the repo |
| File mtimes | Most restored files carry Feb 8 2025 timestamps |
| README | Reverted to pre-`425f14f` content — lost DockerHub + RC build instructions |
| Schema | Re-added `app/models.py` **without** the `vpin_webhooks` table, `players.hidden`, or 3 of the 4 presets |
| Routing | Dropped `publicCommands` and all three `webhook/*` blueprint registrations |
| Env | `.env.sample` lost `SERVER_HOST_IP` (required for webhook callback URL resolution) |

Because the zip was extracted **over** the repo rather than replacing it, files that existed only in
the March tree survived as orphans. The result is a Frankenstein tree with two parallel data layers:

```
Tree A — Feb 2025, currently wired up          Tree B — March 2025, orphaned
──────────────────────────────────────         ──────────────────────────────────────
app/database.py                                app/modules/database.py
app/models.py            (no vpin_webhooks)    app/modules/models.py    (has it)
app/modules/sockets.py   (emit bug)            app/modules/socketio.py  (fixed)
app/socketio_instance.py                       app/modules/socketio.py
app/routes/settings.py                         app/routes/api/v1/settings.py
app/background/create_scoreboards.py (old)     app/routes/api/v1/publicCommands.py
app/utils.py             (empty file)          app/routes/webhooks/{scores,games,players}.py
                                               app/modules/{webhooks,players,games,scores,
                                                            vpinstudio,vpspreadsheet,
                                                            imageProcessor,utils}.py
```

`app/__init__.py` and `app/routes/__init__.py` both point at **Tree A**. Every module in Tree B is
dead code at HEAD.

**Concrete consequences of running HEAD as-is:**

1. `/webhook/scores`, `/webhook/games`, `/webhook/players` all return **404** — the VPin Studio
   integration cannot receive anything.
2. The DB is created without a `vpin_webhooks` table, so any code path that touches it raises
   `no such table`.
3. `app/modules/sockets.py:emit_message` does `socketio.emit(event, args)` (tuple) instead of
   `*args` — every socket payload reaches the browser wrapped in an array, so the frontend
   handlers see `undefined` fields.
4. Tree A's `emit_message` targets `app/socketio_instance.py`'s SocketIO object while Tree B's
   modules target `app/modules/socketio.py`'s — two separate instances, only one initialised.
5. Scoreboard deletion no longer cascades (loses `0964f59`); user deletion cleanup is gone
   (loses `e253186`).

**Recommended fix:** `git revert 556c7b2`, then re-apply only what you actually wanted from that
session. See `Roadmap.md` → Phase 0.

> Everything below this line describes the **real** codebase at `4d8f260`, which is what the
> revert restores.

---

## Local dev environment (2026-08-18)

A venv now exists at `venv/` (gitignored) with `requirements.txt` installed — `python -m venv
venv`, then `venv\Scripts\pip install -r requirements.txt`, then `venv\Scripts\python run.py`.
Confirmed working on Python 3.13 / Windows.

Ran the full app against a fresh `data/highscores.db` and exercised it end to end:

- Boots clean under eventlet, zero tracebacks in the log.
- `db_version` lands at `2`; `vpin_servers` exists; `vpin_webhooks` carries all the new columns;
  4 presets seeded; one default room.
- `GET /`, `GET /default` → 200.
- `PUT /webhook/scores` (empty body) → 400 with a real error, not a crash.
- `PUT /webhook/games` with **no URL segment** → 400, not 405 — confirms the VPIN-02 fix (this
  route didn't exist before Phase 1a).
- `PUT /webhook/pause` (new route) → 400 with the expected validation error.
- Integrations Menu round-trip: `POST .../vpin-servers` normalizes `192.168.1.50:8089` to
  `http://192.168.1.50:8089/`, the room's scoreboard page renders it in the linked-servers list,
  `DELETE .../vpin-servers/<id>` removes it.
- `/api/v1/proxy` correctly 400s on a missing `url`, on `169.254.169.254` (cloud metadata), and
  on a non-`/api/v1/` path — confirms SEC-01.
- `/api/v1/players`, `/api/v1/style/presets`, and the Socket.IO handshake all respond correctly.

**2026-08-19 update — live VPin Studio server now available** (192.168.8.149:8089, on the user's
network). Confirmed `/api/v1/games/scores/{id}` returns `score`, not `numericScore` — the existing
code was already correct. Live testing (real game import + historical score sync, resync, and
directly exercising `PUT /webhook/scores` / `PUT /webhook/players` with realistic payloads against
real API responses) surfaced and fixed three real bugs static review had missed:
- `createdAt` is an ISO 8601 string, never epoch-milliseconds — the naive `/1000` division in
  `webhook_log_score` always threw, silently falling back to "now" and breaking the timestamp-based
  score dedup check (duplicate-row risk on retries/resync). `fetch_historical_scores` had a
  narrower version of the same bug for whole-second timestamps. Fixed with a shared
  `parse_vpin_timestamp()` helper; verified real historical scores now land with their actual VPin
  timestamp, and a resync produces zero duplicates.
- `webhook_player` mapped the VPin player object with the wrong field names (`fullName`/`alias`/
  `aliases` instead of the real `name`/`initials`) — every player UPDATE webhook was silently
  overwriting a real player's name/alias with `"Unknown Player"`/`null`. Fixed to match the shape
  `integrations.js` already used correctly elsewhere.
- `webhook_log_score`'s "no new scores" failure path used the wrong dict key (`message` instead of
  `error`), so the route's fallback masked the real reason — same class of bug fixed elsewhere in
  Phase 1a, one instance missed.

**Still not verified**: an actual webhook delivery triggered from VPin Studio's own UI (create/
update/delete a table, or a real game session posting a score) — today's testing proved the
handlers are correct given realistic data, not that VPin Studio's network delivery to this app
actually works end-to-end. Also still unverified: whether the score read-back race (`VPIN-09`)
happens in practice (the retry logic is now confirmed to behave correctly when scores are absent
vs. present, but a live race under real gameplay timing hasn't been observed).

---

## What ArcadeScore is

A self-hosted Flask + SQLite + Socket.IO app that tracks and displays arcade / virtual-pinball
high scores. It renders one auto-scrolling scoreboard per "room", supports multiple rooms, deep
per-game CSS customisation, and pulls games / players / scores from a
[VPin Studio](https://github.com/syd711/vpin-studio) server.

## Architecture

```
run.py  →  app/create_app()
             ├─ app/modules/models.py       schema bootstrap + (empty) migration ladder
             ├─ app/modules/database.py     per-request sqlite conn on flask.g
             ├─ app/modules/socketio.py     global SocketIO + emit helpers
             └─ app/routes/__init__.py      api_bp, aggregates 14 blueprints

Blueprints
  /                                misc         landing page, static image serving
  /<username>                      users        renders scoreboard.jinja for one room
  /api/<user>                      users        JSON read-only room dump
  /api/v1/games…                   games        CRUD, hide, reorder
  /api/v1/players…                 players      CRUD, VPin link/import, hide
  /api/v1/scoreboards…             scoreboards  create (async), list, rename, delete, clear
  /api/v1/style…                   styles       presets, global CSS, apply/copy, image upload
  /api/v1/settings/<room_id>       settings     PUT room settings
  /api/v1/proxy                    vpin_proxy   CORS/mixed-content shim for VPin Studio
  /api/v1/{export,import,download} importExport 7z round-trip of DB + media
  /publicCommands.php              publicCommands  iScored-compatible legacy API
  /webhook/{scores,games,players}  webhooks     VPin Studio callbacks
  /highscores                      scores       global score dump

Background work (eventlet greenlets, not threads)
  app/background/create_scoreboards.py   the 6-step creation wizard's worker
  app/background/export_task.py          7z export worker

Integration modules
  app/modules/vpinstudio.py     media + historical score pulls
  app/modules/vpspreadsheet.py  VPS DB cache, media fallback, spreadsheet URLs
  app/modules/webhooks.py       registration + inbound webhook handlers
  app/modules/imageProcessor.py Pillow/OpenCV resize, rotate, first-frame extraction
```

**Data model** (`app/modules/models.py`, `db_version = 1`):
`settings` (one row = one scoreboard/room) · `games` · `highscores` · `players` · `aliases` ·
`presets` · `vpin_games` · `vpin_players` · `vpin_webhooks` · `meta`.

Note: `players` and `aliases` are **global**, not room-scoped. Every scoreboard sees every player.

## Feature status

### Core scoreboard
| Feature | Status | Notes |
|---|---|---|
| Multiple scoreboards / rooms | ✅ | one `settings` row per room, addressed by slug |
| Auto-scroll (horizontal + vertical) | ✅ | vertical broken on mobile (known) |
| Drag-to-scroll, fullscreen trigger | ✅ | |
| Text auto-fit | ✅ | `textFit` vendored |
| Mobile layout | ✅ | |
| Landing page with room cards | ✅ | gradient built from game colours |

### Game management
| Feature | Status | Notes |
|---|---|---|
| List / add / edit / delete / hide | ✅ | |
| Drag reordering | ✅ | slow when dragging downward (known) |
| Load details from VPS spreadsheet | ✅ | `VPSDB.js` + `/api/vpsdata` |
| Score display options | ✅ | `score_type` = hideBoth / … |
| Per-game custom CSS | ✅ | |
| Copy CSS between games | ✅ | |
| Reverse sort | ❌ | `sort_ascending` column exists, UI removed in `02b9f2b` |

### Player management
| Feature | Status | Notes |
|---|---|---|
| List / add | ✅ | |
| Multiple initials → one player | ✅ | `aliases` table |
| Edit / delete | ✅ | *(corrected — this was already fully wired: click a player → view → Edit/Hide → form → Delete, all round-trip live-verified)* |
| Hide player | ✅ | `toggle_player_score_visibility` + `players.hidden`, live-verified |
| New-alias default bug | ✅ fixed | radio value wasn't kept in sync with the typed alias text (Phase 2c) |
| Live refresh over socket | ✅ fixed | `emit_player_changes` queried a non-existent `players.room_id` (BUG-14); fixed in Phase 2b |
| Players global vs. per-room | Deliberately global | matches the schema and every existing code path; documented in `docs/Roadmap.md` Phase 2c |

### Styles
| Feature | Status | Notes |
|---|---|---|
| 4 preset themes | ✅ | Default, Neon Glow, Retro Arcade, Cyberpunk |
| Custom CSS presets | ⚠ | saving breaks once >1 scoreboard exists (BUG-17) |
| Apply to all / global / both | ✅ | |
| Font installer | ❌ | not started; presets reference `Federation`, `Orbitron`, `Press Start 2P`, `Cyber` which are never loaded |

### Admin settings
| Feature | Status | Notes |
|---|---|---|
| Room name, date format, scroll, fullscreen, long names, public flags | ✅ | debounced PUT from `settings.js`; all element IDs verified to match |
| Changes broadcast to other tabs | ✅ fixed | `settings_updated` socket event (Phase 2b); other tabs showing the room reload, the editing tab keeps its optimistic update |
| Password protection | ✅ | full set/change/remove/login/logout flow, live-verified with real cookie sessions (Phase 2a) |
| `public_scores_enabled` / `public_score_entry_enabled` / `api_read_access` | ✅ enforced | gate the legacy `publicCommands.php` and modern `/api/<user>` read/write surfaces (Phase 2a) |
| `api_write_access` | Stored, inert | no write route exists yet on the modern `/api/<user>` surface for it to gate |

### Import / export
| Feature | Status | Notes |
|---|---|---|
| 7z export of DB + media | ✅ | background greenlet, `file_ready` socket |
| 7z import | ✅ | version-gated on `meta.db_version` |
| Authentication | ✅ fixed | gated behind `require_any_room_admin` — open only while no room has a password set anywhere (Phase 2a, SEC-02) |

### Deployment
| Target | Status |
|---|---|
| Docker (`docker-compose`, nginx + self-signed TLS) | ✅ |
| Windows (`setup.bat`) | ✅ |
| Linux / macOS (`setup.sh`) | ✅ Linux, ❓ macOS untested |
| DockerHub publish via GH Actions | ✅ |

## VPin Studio integration — detailed status

Checked against the current wiki
([Webhooks](https://github.com/syd711/vpin-studio/wiki/Webhooks)) on 2026-08-18. Updated
2026-08-18 after completing `docs/Roadmap.md` Phase 1 (1a–1d) — this section now describes the
current, fixed state, not the original findings. The original bug-by-bug list is preserved in
`docs/BUG_REVIEW.md` under `VPIN-01`…`VPIN-12` for history.

### What matches the current spec ✅

- **Registration payload.** `register_vpin_webhook` POSTs
  `{name, uuid, enabled, scores{}, games{}, players{}, pause{}, unpause{}}` to
  `{host}/api/v1/webhooks` — the documented shape, including per-resource `endpoint` /
  `parameters` / `subscribe`, now with a shared auth `token` riding in `parameters` on every
  CREATE/UPDATE subscription.
- **Deregistration.** Both scoreboard deletion and the Integrations Menu's per-webhook delete
  issue `DELETE {host}/api/v1/webhooks/{uuid}`.
- **All five documented resource types are wired up and functional**: Highscores (UPDATE), Games
  (CREATE/UPDATE/DELETE), Players (CREATE/UPDATE/DELETE), Pause (UPDATE), Unpause (UPDATE).
  CREATE/UPDATE read the id from `data["id"]` as documented; DELETE reads it from the URL segment.
  UPDATE is registered on both the URL-segment route (legacy/tolerant) and the bare route the spec
  actually documents.
- **Return-call endpoints.** `/api/v1/games/{id}`, `/api/v1/players/{id}`, `/api/v1/games/scores/{id}`
  are all used as documented.
- **URL handling.** A single `normalize_vpin_url`/`vpin_url` helper pair (`app/modules/utils.py`)
  is used everywhere a VPin base URL is stored or a request is built, replacing five different ad
  hoc trailing-slash conventions.

### Known remaining gaps (by design or unverified)

| Issue | Status |
|---|---|
| DELETE calls are unauthenticated | VPin Studio sends no `parameters` on DELETE at all — nothing to check a token against. Resolved by matching on the id alone; documented as a collision risk only if two linked servers reuse the same numeric id. |
| Rooms registered before the token feature shipped | No stored token (`NULL`) → requests are let through unchecked until the room re-registers. Not forced, to avoid silently breaking existing installs. |
| Editing an existing webhook's subscriptions in place | Not built — delete and re-register covers it. |
| Real webhook delivery triggered from VPin Studio's own UI | **Unverified** — the handlers are now confirmed correct against real API data (2026-08-19), but an actual network delivery from VPin Studio to this app's registered endpoint hasn't been observed. |

### Wizard flow (works)

1. Name → 2. Enable VPin + test `GET /api/v1/system/startupTime` → 3. Match/import players →
4. Select high-score-capable games → 5. Pick preset → 6. Background import.

The background task pulls media (VPin Studio ⇄ VPS spreadsheet, with configurable priority and
fallback), extracts a frame from `.mp4` playfield/backglass media, rotates playfields 90°, compresses
to the chosen level, generates VPS spreadsheet links, imports historical scores, and registers the
webhook — emitting `progress_update` throughout. The per-game logic now lives in a shared
`import_vpin_game_into_room()` (`app/modules/vpin_integration.py`) also used by the Integrations
Menu's game import/resync, so a game behaves identically regardless of which path added it.

### Integrations Menu (new)

Reachable from the scoreboard's hamburger menu → Integrations → VPin Studio. Per room:

- **Linked servers** — add/remove a VPin Studio server independent of any webhook subscription.
- **Registered webhooks** — view subscriptions and last-event/last-error health; delete one
  without deleting the scoreboard.
- **Import Games / Import-Link Players** — per linked server, pull the current list from VPin
  Studio and add what's missing (players reuse the same endpoints the wizard uses).
- **Resync Media / Resync Scores** — refresh already-imported games' media or historical scores
  without touching their custom per-game styling.

## Known bugs carried in README

- Vertical score scrolling does not work on mobile
- Drag reordering is slow when dragging down the list
- New-player alias default changes when adding new aliases
- Images from VP-Spreadsheet are uncompressed *(fixed — `fetch_vpspreadsheet_media` now honours
  `compression_level`)*
- Default avatar is deleted by image cleanup *(fixed — `cleanup_unused_images` skips it explicitly)*
- Most setting adjustments do not work *(stale — the current `settings.js` ↔ `scoreboard.jinja`
  wiring is correct; the real gaps are password protection and cross-tab propagation)*

See `BUG_REVIEW.md` for the full pass, including 29 correctness findings and 7 security findings
not listed above.

## Not started

Tournaments (private + public brackets) · friend/score sync · hi2txt MAME support ·
font installer · macOS deployment · any automated tests · any authentication.
