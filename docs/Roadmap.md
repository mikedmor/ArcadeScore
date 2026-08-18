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
- [ ] Smoke test: app boots, `data/highscores.db` gets a `vpin_webhooks` table and 4 presets,
      landing page lists scoreboards, a room renders, `/webhook/scores` returns 400 (not 404) for
      an empty PUT. *(not yet run — no runnable Python env available in this pass; do this before
      relying on the revert.)*
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

**Not yet done — needs a live VPin Studio server, not just code review:**
- [ ] End-to-end verification: create/rename/delete a table in VPin Studio and confirm it reflects
      on the scoreboard within seconds, no manual refresh.
- [ ] Confirm the DELETE id-collision edge case above doesn't bite in your actual setup (single
      VPin server = no risk).

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
- [ ] Verify `score` vs `numericScore` in `/api/v1/games/scores/{id}` against a live server —
      **still unverified**, needs an actual VPin Studio instance. Left unchanged (still `score`)
      since guessing wrong would break the one confirmed-working webhook path.

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
- [ ] **Deliberately not built:** registering a *new* webhook subscription against an existing
      room (only view/delete of what the wizard already registered). Doing this properly needs
      the wizard's whole subscription-checkbox UI re-exposed outside the wizard, which felt like
      a separate, larger unit of work rather than something to bolt on here. Also not built:
      editing an existing webhook's subscriptions in place — delete and re-run the wizard covers
      it for now.

Frontend: `app/static/js/scoreboard/integrations.js` (new), wired into `scoreboard.jinja`'s
existing VPin Studio menu section.

---

## Phase 2 — Close the gap between the README and reality

Three features are advertised but not implemented. Each is a small, self-contained project.

### 2a. Authentication *(`SEC-05`, `SEC-02`)*

The README promises *"(Optional) Password-protected admin menu"*. The `settings.secure` column and
the `save-password-btn` element both exist; nothing is wired.

- [ ] `POST /api/v1/settings/<room_id>/password` — set/clear, hashed (werkzeug `generate_password_hash`).
- [ ] Session cookie or bearer token; `@require_room_admin` decorator.
- [ ] Apply to: delete scoreboard, clear scores, clear games, all style writes, settings PUT,
      player/game mutations, **import and export**.
- [ ] Honour the flags that are already stored but never enforced: `public_scores_enabled`,
      `public_score_entry_enabled`, `api_read_access`, `api_write_access`.
- [ ] Replace the hardcoded `SECRET_KEY` (`SEC-03`) and default `debug=True` (`SEC-04`).

### 2b. Socket.IO rooms *(`BUG-22`)*

Every event currently broadcasts to every connected client. The creation-progress modal pops up on
unrelated scoreboards; deletes and reorders apply without a room check.

- [ ] `join_room(f"room_{roomID}")` on connect (room id already in the page context).
- [ ] Scope all emits with `room=`; keep the client-side `roomID` checks as a belt-and-braces guard.
- [ ] Add `settings_updated` so admin changes propagate to other displays (`BUG-29`).
- [ ] Fix `emit_player_changes`' non-existent `players.room_id` column (`BUG-14`) — this is why the
      player list has never live-refreshed.

### 2c. Player management UI

Backend functions exist (`update_player_in_db`, `delete_player_from_db`,
`toggle_player_score_visibility`); the scoreboard menu doesn't expose them.

- [ ] Edit / delete / hide player from the scoreboard admin menu.
- [ ] Fix the known bug: "New player alias default changes when adding new aliases".
- [ ] Decide and document whether players are global or per-room (`BUG-25`) — the schema says
      global, but code has assumed otherwise.

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
- [ ] `BUG-16` — room-scope `settings LIMIT 1` in `get_global_style` and `save_game_to_db`.
- [ ] `BUG-21` — `store_image` returns a bare filename; those files get deleted on the next export.
- [ ] `BUG-19`, `BUG-20` — `publicCommands` `NameError` and swapped name fields.
- [ ] `BUG-17` — `/highscores` returns three wrong fields and every room's scores.
- [ ] `BUG-18` — `emit_progress` missing its `app` arg in the 7-Zip-not-found path.
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
