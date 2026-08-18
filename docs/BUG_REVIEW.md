# ArcadeScore — Bug Review Pass

**Reviewed:** 2026-08-18 · **Tree at HEAD:** `556c7b2` · **Tree actually reviewed:** `4d8f260`

Findings are against `4d8f260`, the last real development commit, because HEAD is a
snapshot-overwrite regression (see REG-01). Line references are to the `4d8f260` tree; the
orphaned `app/modules/*` files are byte-identical at HEAD, so those references hold either way.

Severity: 🔴 blocking · 🟠 broken feature · 🟡 wrong behaviour · ⚪ hardening / cleanup

---

## Repository integrity

### REG-01 🔴 HEAD replaced 12 commits of work with a Feb-2025 snapshot
**Where:** commit `556c7b2`, whole tree

`ArcadeScore-rc1.zip` (dated Feb 9 2025, sitting in the parent directory) was extracted over the
repo and committed with an auto-generated message. Because it was extracted *over* rather than
*replacing*, March-only files survived as orphans, leaving two parallel data layers wired to
neither consistently.

Verified regressions in `556c7b2`:
- `app/routes/__init__.py` — dropped `public_commands_bp`, `webhook_scores_bp`, `webhook_games_bp`,
  `webhook_players_bp`; repointed `settings_bp` from `app.routes.api.v1.settings` to
  `app.routes.settings`.
- `app/models.py` re-added **without** `vpin_webhooks`, without `players.hidden`, and with 1 preset
  instead of 4.
- `app/routes/api/v1/scoreboards.py` — lost the cascade delete and webhook deregistration from
  `0964f59`, and lost the `/scores` + `/games` clear endpoints that `settings.js` calls.
- `.env.sample` — lost `SERVER_HOST_IP`, which `get_server_base_url()` needs to build a reachable
  webhook callback URL under Docker.
- `run.py` — lost `ARCADESCORE_HTTP_PORT` handling, hardcoded to 8080.
- `README.md` — reverted past `425f14f`/`55c3104`/`1ad261a` (DockerHub + RC build docs).

**Fix:** `git revert 556c7b2`. Nothing in that commit is worth keeping except possibly the
`certs/openssl.cnf` addition, which can be cherry-picked back by hand.

---

## VPin Studio integration

### VPIN-01 🔴 Game and Player webhooks read the wrong body key
**Where:** `app/modules/webhooks.py:474`, `app/modules/webhooks.py:339`

```python
if not vpin_game_id and "gameID" in data:      # line 474
    vpin_game_id = data["gameID"]
if not vpin_player_id and "playerID" in data:  # line 339
    vpin_player_id = data["playerID"]
```

The wiki is explicit that every event carries an **`id`** parameter. The score handler already gets
this right (`data.get("id")` at line 120) and is the one handler confirmed working. `gameID` /
`playerID` are never present, so `vpin_game_id` stays `None` and the return call becomes
`GET {host}/api/v1/games/None` → 404 → the handler returns "Error fetching game details".

**Fix:** read `data.get("id")`, keeping the URL-segment value as the override for DELETE.

### VPIN-02 🔴 UPDATE webhooks have no matching route
**Where:** `app/routes/webhooks/games.py:8`, `app/routes/webhooks/players.py:8`

Per the wiki, only **DELETE** appends the id as a URL segment; CREATE and UPDATE pass it as a
parameter to the registered endpoint. So a game update arrives as `PUT /webhook/games` — but the
only registered PUT rule is `/webhook/games/<int:vpin_game_id>`. Flask returns **405**.

**Fix:** add `@bp.route("/webhook/games", methods=["PUT"])` (same for players) and resolve the id
from the body.

### VPIN-03 🟠 DELETE handlers require a `roomID` that is never sent
**Where:** `app/modules/webhooks.py:554-557` (games), `:408-411` (players)

```python
if "roomID" not in data:
    return {"success": False, "error": "Missing required parameter: roomID"}
```

The wiki's field table says `parameters` is *"An optional map of fix parameters. This will be passed
to all PUT and POST requests."* — DELETE is excluded. A DELETE webhook therefore has no body at all,
which also means `request.get_json()` in the route raises before the handler is even reached.

**Fix:** resolve the room from `vpin_games` / `vpin_players` using the URL-segment id plus the
server URL, and use `request.get_json(silent=True) or {}`.

### VPIN-04 🟠 Player webhook registration omits `parameters` entirely
**Where:** `app/modules/webhooks.py:62-69`

```python
payload["players"] = {
    "endpoint": f"{server_base_url}/webhook/players",
    "subscribe": [...]           # ← no "parameters" key
}
```

The `scores` and `games` blocks both pass `{"roomID": room_id}`. The players block does not, so
`roomID` is missing from *every* player event — not just DELETE — and `webhook_player` bails at its
first check. This alone would explain "player webhooks don't work".

**Fix:** add `"parameters": {"roomID": room_id}`.

### VPIN-05 🔴 `link_vpin_player` called with the wrong signature
**Where:** `app/modules/webhooks.py:388` calls · `app/modules/players.py:256` defines

```python
link_vpin_player(conn, new_player_id, vpin_api_url, vpin_player_id)   # 4 positional args
def link_vpin_player(conn, data):                                     # takes 2
```

`TypeError` on every player-CREATE webhook, swallowed by the outer `except` and reported as
"Internal Server Error".

**Fix:** build the `{"server_url": …, "players": [{…}]}` dict the function expects.

### VPIN-06 🟠 `add_player_to_db` returns a 2-tuple on failure, 3-tuple on success
**Where:** `app/modules/players.py:172` vs `:175`

```python
return True, "Player added successfully!", player_id   # success
return False, f"Failed to add player: {str(e)}"        # failure — only 2 values
```

`app/modules/webhooks.py:386` does `success, message, new_player_id = add_player_to_db(...)` and
raises `ValueError: not enough values to unpack` on the failure path, replacing the real error with
a confusing one. `app/routes/api/v1/players.py:111-118` works around this with an `isinstance`
length check — proof the inconsistency was already causing pain.

**Fix:** always return `(bool, str, Optional[int])`, then drop the workaround.

### VPIN-07 🟠 `aliases` passed as a list into a `json.loads`
**Where:** `app/modules/webhooks.py:370` → `app/modules/players.py:143`

```python
"aliases": player_details.get("aliases", []),   # a Python list
...
aliases = json.loads(data.get("aliases", "[]")) # expects a JSON string
```

`TypeError: the JSON object must be str, bytes or bytearray, not list`. The HTTP route path works
because `request.form.to_dict()` yields strings; only the webhook path is broken.

**Fix:** accept either — `aliases = data.get("aliases") or []; if isinstance(aliases, str): aliases = json.loads(aliases)`.

### VPIN-08 🟠 `pause` / `unpause` webhook types are unsupported
**Where:** wiki §Webhook Events; not present anywhere in the codebase

The wiki now documents two event types ArcadeScore doesn't know about:

| Endpoint | Event | Method | Fires when |
|---|---|---|---|
| Pause | UPDATE | PUT | pause menu opened, `id` = game id |
| Unpause | UPDATE | PUT | pause menu closed, `id` = game id |

They follow the same `{endpoint, parameters, subscribe}` shape and can be added to the same
registration payload. This is a genuine new capability — "table currently being played" is exactly
the kind of thing a scoreboard wants to highlight.

**Fix:** add `pause_update` / `unpause_update` columns to `vpin_webhooks`, checkboxes to the wizard,
a `/webhook/pause` + `/webhook/unpause` route pair, and a `game_pause_state` socket event.

### VPIN-09 🟡 Score read-back race, workaround removed with no replacement
**Where:** `app/modules/webhooks.py:167-180`; workaround added in `29b56c9`, removed in `1be01eb`

`29b56c9` added `time.sleep(30)` before the score return call with the comment *"Delay to give VPin
Studio time to update on its end (this is pretty extreme but shouldn't be permanent)"*. It was
removed 7 days later without anything taking its place. If VPin Studio still fires the highscore
webhook before committing, `GET /api/v1/games/scores/{id}` returns the pre-update set and the new
score is silently dropped.

**Fix:** verify against your current VPin Studio build. If the race persists, replace the blocking
sleep with a short bounded retry (e.g. up to 5 attempts, 2 s apart, stopping as soon as a score
appears that isn't already in `highscores`) — note that under eventlet a bare `time.sleep` blocks
the whole greenlet handling that request.

### VPIN-10 🟡 Inconsistent trailing-slash handling on the VPin base URL
**Where:** across `webhooks.py`, `vpinstudio.py`

```python
f"{vpin_api_url.rstrip('/')}/api/v1/webhooks"          # webhooks.py:74   tolerant
f"{vpin_api_url}api/v1/games/scores/{vpin_game_id}"    # webhooks.py:167  needs trailing /
f"{vpin_api_url}api/v1/media/{id}/PlayField"           # vpinstudio.py:16 needs trailing /
f"{vpin_api_url.rstrip('/')}/api/v1/players/{id}"      # webhooks.py:355  tolerant
```

This only works because `normalizeUrl()` in `index.js:641` appends a slash before the URL is stored.
Any URL that reaches the DB by another path (import, manual edit, future integrations menu) produces
`http://host:8089api/v1/...`.

**Fix:** normalise once on write, and add a single `vpin_url(base, path)` helper.

### VPIN-11 🟡 A room's VPin server URL is only discoverable via `vpin_webhooks` / `vpin_games`
**Where:** `create_scoreboards.py:109-115`, `webhooks.py:128-136`

The March schema dropped `settings.vpin_api_enabled` / `settings.vpin_api_url`. Every inbound
webhook resolves the server with `SELECT DISTINCT server_url FROM vpin_webhooks WHERE room_id = ?`
and takes `fetchone()`. Two consequences: a room created with media import but no webhook
subscription has no addressable server at all, and a room with two VPin servers silently picks one
at random.

**Fix:** the "Integrations Menu" started in `4d8f260` is the right home for this — give a room an
explicit list of linked VPin servers and resolve through that.

### VPIN-12 🟠 Webhook endpoints are unauthenticated and trust `roomID` from the body
**Where:** `app/routes/webhooks/*.py`

Anything that can reach the port can `PUT /webhook/scores` with `{"roomID": 1, "id": 5}` and cause
ArcadeScore to ingest whatever the named VPin server reports. The wiki notes VPin Studio itself
*"currently only provides unauthorized HTTP calls"*, so this can't be fixed by borrowing its auth.

**Fix:** register a per-room shared secret as a static `parameter` at registration time
(`{"roomID": 1, "token": "<random>"}`), store it in `vpin_webhooks`, and reject mismatches.
This works with the documented `parameters` map today and needs nothing from upstream.

---

## Correctness

### BUG-13 🟠 `get_docker_host_ip()`'s `def` line was lost — its body ran inside `cleanup_unused_images`
**Where:** `app/modules/utils.py:124-146`

```python
    print(f"Cleanup complete. {removed_count} images removed.")


    """Detect the host machine's LAN IP from inside a Docker container."""   # ← orphaned docstring
    try:
        return socket.gethostbyname("host.docker.internal")
    ...
    return get_host_lan_ip()
```

The function header vanished in a merge. `cleanup_unused_images` now ends by doing a DNS lookup,
shelling out to `ip route`, and returning an IP address. On Windows the `subprocess.run(["ip", …])`
raises `FileNotFoundError` on every export. Nothing calls `get_docker_host_ip` anymore — note that
`get_server_base_url()` uses `get_host_lan_ip()` directly, so Docker host detection is simply gone.

**Fix:** restore `def get_docker_host_ip():` before the docstring and decide whether
`get_server_base_url()` should call it in the Docker branch.

### BUG-14 🟠 `emit_player_changes` queries a column that doesn't exist
**Where:** `app/modules/socketio.py:16`

```sql
SELECT id, full_name, icon, default_alias, long_names_enabled, room_id FROM players;
```

`players` has no `room_id` (see `models.py:145-155`). Every call raises
`OperationalError: no such column: room_id`, is caught by the bare `except`, prints one line, and
returns. **The `players_updated` socket event has never fired.** Add/update/delete player all call
this, so the scoreboard's player list only refreshes on a full page reload.

**Fix:** drop `room_id` from the SELECT and from the emitted dict, or add a real room association
(see BUG-20).

### BUG-15 🟠 `save_preset` cross-joins `settings` — breaks with more than one scoreboard
**Where:** `app/routes/api/v1/styles.py:77-82`

```sql
INSERT INTO presets (name, css_body, css_card, …)
SELECT ?, settings.css_body, settings.css_card, g.css_score_cards, …
FROM games g, settings
WHERE g.id = ?;
```

`FROM games g, settings` is an unqualified cross join. With N scoreboards this tries to insert N
rows all carrying the same `name`, and `presets.name` is `UNIQUE` → `IntegrityError` on the second
row. The route has no `try/except`, so the user gets a bare 500. The overwrite branch has the same
flaw via `(SELECT css_body FROM settings)`, which silently takes whichever row SQLite returns first.

**Fix:** pass `roomID` from the client (the other style endpoints already do) and scope both
branches with `WHERE settings.id = ?`.

### BUG-16 🟡 Global styles read `settings LIMIT 1` instead of the room's row
**Where:** `styles.py:17` (`get_global_style`), `games.py:87` (`save_game_to_db`)

```sql
SELECT css_body, css_card FROM settings LIMIT 1;
```

Both silently use scoreboard #1's CSS. In `save_game_to_db` the value is emitted as `css_card` on
the `game_update` socket event, so editing a game in room 3 pushes room 1's card CSS to every
listening client in room 3.

**Fix:** thread `room_id` through — `save_game_to_db` already has it in `data["room_id"]`.

### BUG-17 🟡 `get_high_scores` maps columns to the wrong keys
**Where:** `app/modules/scores.py:76-86`

The query selects `game_id, player_name, score, event, wins, losses, timestamp, hidden`, but the
dict comprehension reads:

```python
"gameName":   row[0],   # actually game_id
"playerName": row[1],   # ok
"score":      row[2],   # ok
"roomID":     row[3],   # actually event
"timestamp":  row[4],   # actually wins
```

`/highscores` therefore returns nonsense for three of five fields. The function is also marked
`# TODO: This needs to be fixed as it currently does not get passed a room_id` and returns every
room's scores.

**Fix:** take `room_id`, restore the commented-out `WHERE h.room_id = ?`, and align the keys.

### BUG-18 🟡 `emit_progress` called without its `app` argument
**Where:** `app/background/export_task.py:76`

```python
emit_progress(-1, "Error: 7z.exe not found. Install 7-Zip and add it to your PATH.")
```

Signature is `emit_progress(app, progress, message)`. `TypeError` is caught by the outer handler,
which then calls `emit_progress(app, -1, f"Export failed: …")` — so the user does get *an* error,
just the wrong one, and only when 7-Zip is missing (exactly when the clear message matters).

**Fix:** `emit_progress(app, -1, …)`.

### BUG-19 🟡 `addScore` raises `NameError` when long names are enabled
**Where:** `app/routes/api/v1/publicCommands.py:159-175` (and the duplicate in
`app/routes/settings.py:309-325` at HEAD)

```python
if long_names_enabled == "TRUE":
    cursor.execute("SELECT id FROM players WHERE full_name = ?", (player_name,))
    # ← never assigns player_id_row
else:
    cursor.execute(...)
    player_id_row = cursor.fetchone()
    if not player_id_row: ...
if player_id_row:        # NameError when the TRUE branch ran
```

Any room with `long_names_enabled = TRUE` gets a 500 on every legacy score submission.

**Fix:** `player_id_row = cursor.fetchone()` inside the `TRUE` branch too.

### BUG-20 🟡 `fullName` and `defaultAlias` are swapped in the addScore socket payload
**Where:** `app/routes/api/v1/publicCommands.py:201-210`

The SELECT is `p.full_name, p.default_alias, …` so `row[0]` is the full name, yet:

```python
"fullName":     row[1],   # default_alias
"defaultAlias": row[0],   # full_name
```

`displayName` is computed correctly, so this only surfaces when the client toggles long names
(`updateLongNames` in `settings.js` reads `data-full-name` / `data-default-alias`) — names flip.

Related: the HEAD copy in `app/routes/settings.py:351-357` emits a completely different shape
(`playerName` only, no `displayName` / `formatted_timestamp`), which `socketModules/games.js` can't
consume. Another symptom of REG-01.

### BUG-21 🟡 `store_image` returns a bare filename where every other path returns a URL
**Where:** `app/routes/api/v1/styles.py:323`

```python
return jsonify({"localPath": filename}), 200          # store_image  → "table.png"
local_path = f"/static/images/{image_type}/{filename}" # upload_image → "/static/images/…"
```

Whatever is stored from `store_image` won't render as an `<img src>` and won't satisfy
`convert_to_absolute()`'s `path.startswith("/static/images/")` guard in `cleanup_unused_images` —
so the file is treated as unreferenced and **deleted on the next export**.

**Fix:** return `f"/static/images/{image_type}/{filename}"`.

### BUG-22 🟡 Socket.IO broadcasts everything to every client
**Where:** `app/modules/socketio.py` (all emits use `namespace="/"` with no `room=`), consumed in
`app/static/js/socketModules/websocket.js`

The client filters `game_update` and `game_score_update` by `roomID`, but these have no filter at
all:

| Event | Consequence |
|---|---|
| `progress_update` | the creation/export modal pops up on *every* open scoreboard, in every browser |
| `game_deleted` | `removeGameFromDOM(data.gameID)` runs unconditionally |
| `game_visibility_toggled` | applied without a room check |
| `game_order_update` | applied without a room check |
| `styles_updated` | preset list refreshed everywhere (harmless but noisy) |
| `players_updated` | would leak across rooms if BUG-14 were fixed |

It also means every scoreboard receives every other scoreboard's traffic — a real cost on a wall
display running 24/7.

**Fix:** `join_room(f"room_{roomID}")` on connect and emit with `room=`. This is the single
highest-value structural fix in the socket layer.

### BUG-23 ⚪ `new_sort_order` collides when `MAX(game_sort)` is 0
**Where:** `app/modules/games.py:73`

```python
new_sort_order = (max_sort + 1) if max_sort else 1
```

`max_sort == 0` is falsy, so the next game also gets `1`. `create_scoreboards.py` starts its own
counter at 0, so a room built by the wizard then extended by hand hits this immediately.

**Fix:** `new_sort_order = (max_sort + 1) if max_sort is not None else 1`.

### BUG-24 ⚪ `datetime.utcfromtimestamp` / `utcnow` are deprecated
**Where:** `app/modules/webhooks.py:212, 216`

Deprecated in Python 3.12 and slated for removal. The Docker image is Ubuntu 22.04 (Python 3.10) so
it works today, but this will start emitting `DeprecationWarning` the moment the base image moves.

**Fix:** `datetime.fromtimestamp(ts / 1000, tz=timezone.utc)`.

### BUG-25 ⚪ `players` and `aliases` are global, not room-scoped
**Where:** `app/modules/models.py:145-165`, `app/routes/api/v1/users.py:115-119`

`user_scoreboard` fetches *all* players with no room filter, so every scoreboard's admin menu lists
everyone. `aliases.alias` is `UNIQUE` globally, so two rooms can't both have a player using the
initials "MDM". `players.hidden` is likewise a single global flag.

This may well be intentional (one household, many themed boards) — but it isn't documented, and
BUG-14 shows someone once assumed a `players.room_id` existed. Worth a deliberate decision.

### BUG-26 ⚪ `migrate_db` is an empty ladder and `db_version` is pinned at 1
**Where:** `app/modules/models.py:322-374`, `app/modules/database.py:4`

Every migration step is commented out, and `init_db` only creates tables when `meta.db_version` is
absent. Any user upgrading from an older build keeps their old schema forever — which is exactly why
the README says *"you may need to delete your `highscores.db` file and start fresh"*. The import
endpoint's version gate is also meaningless while the number never changes.

**Fix:** this needs solving before 1.0. See `Roadmap.md` → Phase 3.

### BUG-27 ⚪ Early returns skip `close_db()`
**Where:** `styles.py:116, 193, 235, 364`, `scoreboards.py:88, 104`, and others

`app.teardown_appcontext(close_db)` covers this in practice, so it's not a leak — but the pattern is
inconsistent enough that it reads as a bug and invites one. Since teardown already handles it, the
cleaner fix is to delete the manual `close_db()` calls entirely rather than add more.

### BUG-28 ⚪ `conn.close()` inside a request breaks any later `get_db()`
**Where:** `app/routes/settings.py:98, 181, 254` (HEAD tree only)

`get_db` caches the connection on `flask.g`; `conn.close()` closes it without popping `g.db`, so a
subsequent `get_db()` in the same request returns a closed handle. The Tree B code correctly uses
`close_db()`. Goes away with the REG-01 revert.

### BUG-29 ⚪ `update_settings` broadcasts nothing
**Where:** `app/routes/api/v1/settings.py:22-90`

Room name, date format, scroll behaviour, and long-name mode are all changed via PUT with no socket
emit. `settings.js` patches its own DOM optimistically, so the editing tab looks right while every
other display stays stale until reload. On a multi-display setup that's the common case.

**Fix:** emit a `settings_updated` event scoped to the room (needs BUG-22).

---

## Security

All findings assume the documented deployment: a LAN-exposed container with no auth in front of it.
None of these are remotely exploitable from the internet unless the user forwards the port — but the
README's own "Planned Features" list includes public tournaments and friend sync, which would change
that.

### SEC-01 🔴 `/api/v1/proxy` is an unauthenticated SSRF
**Where:** `app/routes/api/v1/vpin_proxy.py:9-15`

```python
target_url = request.args.get("url").rstrip("/")
if not target_url: ...
response = requests.get(target_url, timeout=5)
```

Fetches any URL the caller names and returns the body verbatim. From a browser on the LAN this maps
the internal network, reaches other admin panels, and — in a cloud deployment — hits
`169.254.169.254` metadata. Also, `.rstrip()` runs *before* the `None` check, so a request with no
`url` param raises `AttributeError` → 500 instead of the intended 400.

**Fix:** move the `None` check first; then restrict to `http`/`https` with a private-IP host and a
`:8089`-style port allowlist, or better, to the set of server URLs already recorded in
`vpin_games` / `vpin_webhooks`.

### SEC-02 🔴 `/api/v1/import` replaces the database, unauthenticated
**Where:** `app/routes/api/v1/importExport.py:49-140`

A single unauthenticated `POST` with a `.7z` file overwrites `data/highscores.db` and merges
arbitrary files into `app/static/images/`. Two compounding issues:

1. `subprocess.run([7z, "x", archive, f"-o{tmp}", "-y"])` does not pass `-snld`/path restrictions,
   so archive entries containing `../` can be written outside `temp_import` (zip-slip).
2. `shutil.copytree(src, dest, dirs_exist_ok=True)` then copies whatever landed there into the
   served static tree — including, potentially, a `.py` file into the app directory.

`/api/v1/export` is the mirror image: anyone can download the full database.

**Fix:** gate both behind the admin password (once SEC-05 is real), and validate extracted paths
stay under `temp_import` before copying.

### SEC-03 🟡 Hardcoded `SECRET_KEY`
**Where:** `app/__init__.py:15` — `app.config["SECRET_KEY"] = "supersecret"`

Currently only signs nothing of consequence, but it's the key any future session/CSRF work will
use, and it's public in the repo.

**Fix:** read from env with a generated fallback persisted to `data/`.

### SEC-04 🟡 `debug=True` in the shipped entrypoint
**Where:** `run.py:19`

`socketio.run(app, host="0.0.0.0", …, debug=True)`. Under eventlet the interactive Werkzeug debugger
generally isn't reachable, but debug mode still leaks tracebacks and this is the *documented*
production launch path (`setup.sh`/`setup.bat` call it directly).

**Fix:** `debug=os.getenv("ARCADESCORE_DEBUG", "0") == "1"`.

### SEC-05 🟠 There is no authentication anywhere
**Where:** whole app; `settings.secure` column, `save-password-btn` in `scoreboard.jinja`

The README advertises *"(Optional) Password-protected admin menu"*. The column exists, the button
exists, and `user_scoreboard` passes `secure_password` to the template — but no listener is bound to
the button, there is no endpoint to set it, and nothing checks it. Every destructive endpoint
(delete scoreboard, clear scores, clear games, import DB) is open.

**Fix:** this is the largest single gap between the README and reality. See `Roadmap.md` → Phase 2.

### SEC-06 ⚪ `cors_allowed_origins="*"` on Socket.IO
**Where:** `app/__init__.py:29`, `app/modules/socketio.py:4`

Any page in any tab can open a socket and read every score, style, and progress event. Low impact
today because everything broadcast is already public within the room; it becomes a real leak the
moment auth exists.

### SEC-07 ⚪ DOM XSS via `innerHTML` with VPin-sourced strings
**Where:** `app/static/js/index/index.js:112-189`, `:339-364`

Player names, initials, game display names, ROM names, and file names from the VPin Studio API are
interpolated straight into `innerHTML` templates. A table named
`<img src=x onerror=…>` executes in the wizard. Jinja-rendered pages are fine (auto-escaping is on);
this is limited to the JS-built wizard lists.

**Fix:** build these nodes with `textContent`, or escape via a small helper.

---

## Summary

| Severity | Count |
|---|---|
| 🔴 Blocking | 6 (REG-01, VPIN-01, VPIN-02, VPIN-05, SEC-01, SEC-02) |
| 🟠 Broken feature | 11 |
| 🟡 Wrong behaviour | 12 |
| ⚪ Hardening | 8 |

**Highest leverage, in order:**

1. `git revert 556c7b2` — restores four fixes and re-registers the entire webhook surface (REG-01).
2. Fix the `id` key, add the PUT routes, add `parameters` to the players block, fix
   `link_vpin_player` — this is the whole "Game and Player webhooks don't work" cluster, and it's
   maybe 40 lines (VPIN-01…07).
3. Socket.IO rooms (BUG-22) — removes a class of cross-scoreboard bugs rather than one instance.
4. Auth on destructive endpoints (SEC-02, SEC-05) — the README already promises it.

**Needs verification against a live VPin Studio server** (I read the wiki, not your server):
the `score` vs `numericScore` field name in `/api/v1/games/scores/{id}`, whether the read-back race
in VPIN-09 still occurs, and whether `parameters` really are omitted on DELETE.
