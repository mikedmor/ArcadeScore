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
| Edit / delete | ⚠ | backend exists (`update_player_in_db`, `delete_player_from_db`); scoreboard UI incomplete |
| Hide player | ⚠ | `toggle_player_score_visibility` + `players.hidden` exist; not exposed in UI |
| Live refresh over socket | ❌ | `emit_player_changes` queries a non-existent `players.room_id` and silently fails (BUG-16) |

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
| Changes broadcast to other tabs | ❌ | `update_settings` emits no socket event |
| Password protection | ❌ | `settings.secure` column exists; `save-password-btn` has no listener and no endpoint |
| Manual score entry toggle | ❌ | flag stored, never enforced |

### Import / export
| Feature | Status | Notes |
|---|---|---|
| 7z export of DB + media | ✅ | background greenlet, `file_ready` socket |
| 7z import | ✅ | version-gated on `meta.db_version` |
| Unauthenticated | 🔴 | anyone who can reach the port can replace your database (SEC-02) |

### Deployment
| Target | Status |
|---|---|
| Docker (`docker-compose`, nginx + self-signed TLS) | ✅ |
| Windows (`setup.bat`) | ✅ |
| Linux / macOS (`setup.sh`) | ✅ Linux, ❓ macOS untested |
| DockerHub publish via GH Actions | ✅ |

## VPin Studio integration — detailed status

Checked against the current wiki
([Webhooks](https://github.com/syd711/vpin-studio/wiki/Webhooks)) on 2026-08-18.

### What matches the current spec ✅

- **Registration payload.** `register_vpin_webhook` POSTs
  `{name, uuid, enabled, scores{}, games{}, players{}}` to `{host}/api/v1/webhooks` — exactly the
  documented shape, including per-resource `endpoint` / `parameters` / `subscribe`.
- **Deregistration.** Scoreboard deletion issues `DELETE {host}/api/v1/webhooks/{uuid}` — correct.
- **Score webhook.** `PUT /webhook/scores` reading `data["id"]` as the *game* id, then calling back
  to `GET /api/v1/games/scores/{id}` — matches "only ids are passed… these need a return call".
- **Return-call endpoints.** `/api/v1/games/{id}`, `/api/v1/players/{id}`, `/api/v1/games/scores/{id}`
  are all used as documented.
- **Game DELETE URL shape.** Route is `/webhook/games/<int:id>` (DELETE), matching "appended as URL
  segment".

### What has drifted or was never right ❌

| # | Issue | Impact |
|---|---|---|
| 1 | Game/Player handlers read `data["gameID"]` / `data["playerID"]`; VPin sends `id` | ID is always `None` → callback hits `/api/v1/games/None` |
| 2 | UPDATE arrives as `PUT` to the **registered URL** (id in body), but the only PUT route is `/webhook/games/<int:id>` | 405 Method Not Allowed |
| 3 | `parameters` are documented as sent on **PUT and POST only**; DELETE handlers hard-require `roomID` in the body | every delete webhook fails |
| 4 | The `players` block in `register_vpin_webhook` omits `parameters` entirely | `roomID` is never sent for *any* player event |
| 5 | `link_vpin_player(conn, new_player_id, url, id)` called with 4 args; signature is `(conn, data)` | `TypeError` on player CREATE |
| 6 | `add_player_to_db` returns a 2-tuple on failure but callers unpack 3 | `ValueError` masks the real error |
| 7 | `webhooks.py` passes `aliases` as a `list`; `add_player_to_db` runs `json.loads` on it | `TypeError` |
| 8 | **`pause` / `unpause` webhook types are new in the wiki** and unsupported — no UI, no route, no `vpin_webhooks` columns | missing feature |
| 9 | The `time.sleep(30)` race workaround (`29b56c9`) was removed in `1be01eb` with no replacement | scores may be read back before VPin Studio has committed them |
| 10 | Trailing-slash handling is inconsistent across URL builders (`rstrip('/')` in some, bare concat in others) | works only because `normalizeUrl()` in the browser appends `/` |
| 11 | The VPin server URL is only recoverable from `vpin_webhooks` / `vpin_games` | a room created with media import but no webhook has no addressable server |
| 12 | Webhook endpoints are unauthenticated and trust `roomID` from the request body | anyone on the LAN can inject scores (VPin Studio itself is unauthenticated too — see wiki note) |

This is consistent with `1be01eb`, which disabled the Game and Player subscription checkboxes in
`index.jinja` with the comment *"Not working yet"*. Only the **Highscores → UPDATE** subscription is
currently offered to users, and that one does work.

### Wizard flow (works)

1. Name → 2. Enable VPin + test `GET /api/v1/system/startupTime` → 3. Match/import players →
4. Select high-score-capable games → 5. Pick preset → 6. Background import.

The background task pulls media (VPin Studio ⇄ VPS spreadsheet, with configurable priority and
fallback), extracts a frame from `.mp4` playfield/backglass media, rotates playfields 90°, compresses
to the chosen level, generates VPS spreadsheet links, imports historical scores, and registers the
webhook — emitting `progress_update` throughout.

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
