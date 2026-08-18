# ArcadeScore — Roadmap

**Target:** ship `1.0.0` · **Written:** 2026-08-18 · **Companion docs:** `Progress.md`, `BUG_REVIEW.md`

Phases are ordered by dependency, not by appeal. Phase 0 blocks everything; Phase 1 is what makes
the project's headline feature actually work; Phases 2–3 are what "1.0" honestly requires.

---

## Phase 0 — Recover the tree ⛔ blocks everything

Commit `556c7b2` overwrote 12 commits of March-2025 work with a Feb-2025 zip (`REG-01`). Nothing
downstream is worth doing until this is undone.

- [ ] `git revert 556c7b2` on a branch; confirm `app/routes/__init__.py` registers 14 blueprints
      again and that `app/models.py`, `app/database.py`, `app/routes/settings.py`,
      `app/socketio_instance.py`, `app/modules/sockets.py`, `app/utils.py` are gone.
- [ ] Cherry-pick back the one thing worth keeping from `556c7b2`: `certs/openssl.cnf`.
- [ ] Smoke test: app boots, `data/highscores.db` gets a `vpin_webhooks` table and 4 presets,
      landing page lists scoreboards, a room renders, `/webhook/scores` returns 400 (not 404) for
      an empty PUT.
- [ ] Delete `../ArcadeScore-rc1.zip` or move it well outside the repo so this can't recur.
- [ ] Add a `.gitignore` entry for `*.zip` and a pre-commit sanity check on `app/routes/__init__.py`
      blueprint count.

**Exit criteria:** `git diff 4d8f260 HEAD` shows only the openssl.cnf addition.

---

## Phase 1 — Make the VPin Studio integration real

The headline feature. Score webhooks work; games, players, and the two new pause events do not.
Most of this is small and mechanical — the hard part was finding it.

### 1a. Fix the broken webhook cluster *(~40 lines, high value)*

- [ ] `VPIN-01` — read `data.get("id")` in `webhook_game` / `webhook_player`, not
      `gameID` / `playerID`.
- [ ] `VPIN-02` — add `PUT /webhook/games` and `PUT /webhook/players` (no URL segment); the
      documented UPDATE shape puts the id in the body.
- [ ] `VPIN-04` — add `"parameters": {"roomID": room_id}` to the `players` block in
      `register_vpin_webhook`.
- [ ] `VPIN-05` — call `link_vpin_player(conn, {"server_url": …, "players": [{…}]})`.
- [ ] `VPIN-06` — make `add_player_to_db` always return `(bool, str, Optional[int])`; drop the
      `isinstance` workaround in `players.py`.
- [ ] `VPIN-07` — accept `aliases` as list *or* JSON string.
- [ ] `VPIN-03` — resolve the room from `vpin_games` / `vpin_players` on DELETE instead of demanding
      a `roomID` the spec says isn't sent; use `request.get_json(silent=True) or {}`.
- [ ] Re-enable the Game and Player subscription checkboxes in `index.jinja` (currently `{# Not
      working yet #}` from `1be01eb`) and restore the matching branches in `index.js`.

**Exit criteria:** creating, renaming, and deleting a table in VPin Studio is reflected on the
scoreboard within seconds, with no manual refresh.

### 1b. Support the new `pause` / `unpause` events *(new capability)*

The wiki now documents these; ArcadeScore has no concept of them.

- [ ] Migration: add `pause_update`, `unpause_update` to `vpin_webhooks`.
- [ ] `register_vpin_webhook`: emit `pause` / `unpause` blocks (same `{endpoint, parameters,
      subscribe}` shape).
- [ ] Routes: `PUT /webhook/pause`, `PUT /webhook/unpause`, resolving game via `vpin_games`.
- [ ] Socket: `game_pause_state {gameID, roomID, paused}` → scoreboard highlights the card for the
      table currently being played. This is the visible payoff and a genuinely nice feature for a
      wall display.
- [ ] Wizard checkboxes + a `.game-card.is-playing` style hook in the presets.

### 1c. Harden the integration

- [ ] `VPIN-09` — determine whether the score read-back race still exists. If it does, replace the
      removed `time.sleep(30)` with a bounded retry (5 × 2 s, exit early on a new score) — never a
      blocking sleep under eventlet.
- [ ] `VPIN-10` — normalise the base URL once on write; add a `vpin_url(base, path)` helper and use
      it everywhere.
- [ ] `VPIN-12` — generate a per-room token at registration, pass it as a static `parameter`, store
      it in `vpin_webhooks`, reject mismatches. Works with today's spec, needs nothing upstream.
- [ ] `SEC-01` — restrict `/api/v1/proxy` to known VPin server URLs; fix the `None`-before-`rstrip`
      crash.
- [ ] Verify `score` vs `numericScore` in `/api/v1/games/scores/{id}` against a live server; the
      pre-March code used `numericScore`, the current code uses `score`.

### 1d. Finish the Integrations Menu

Started in `4d8f260` and never completed. It's the right home for several loose ends.

- [ ] Per-room list of linked VPin servers (fixes `VPIN-11` — the server URL is currently only
      recoverable from `vpin_webhooks` / `vpin_games`).
- [ ] View / edit / delete registered webhooks after creation, without deleting the scoreboard.
- [ ] Re-run player import and game import from an existing scoreboard, not just the wizard
      (README has these as unchecked: "Import/Update Players → Scoreboard", "Import Scores →
      Scoreboard").
- [ ] Show webhook health: last event received, last error.

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
