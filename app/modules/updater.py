import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

import eventlet
import requests

DEFAULT_REPO = "mikedmor/ArcadeScore"
CACHE_TTL_SECONDS = 3600  # don't hit GitHub's API more than once an hour unless forced


def _project_root():
    # app/modules/updater.py -> app/modules -> app -> project root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_current_build_number():
    """Reads the BUILD_NUMBER file at the project root. Returns 0 (never "up to date")
    if it's missing or unreadable, rather than raising - a broken version file shouldn't
    take down update-checking, it should just always report an update as available."""
    path = os.path.join(_project_root(), "BUILD_NUMBER")
    try:
        with open(path, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0


def detect_deployment_type():
    """"docker" (running in a container - update by pulling/rebuilding the image, not
    git), "git" (a real git checkout - the only case apply_update() supports), or
    "standalone" (e.g. a downloaded release archive with no git metadata - can still
    check for updates, just can't apply one automatically)."""
    if os.path.exists("/.dockerenv"):
        return "docker"
    if os.path.isdir(os.path.join(_project_root(), ".git")):
        return "git"
    return "standalone"


def fetch_available_releases():
    """Returns a list of releases shaped like GitHub's release-list API response
    (fields used: tag_name, prerelease, draft, published_at, html_url).

    Two local-testing overrides, both env vars, checked before touching the real
    project's releases:
      - ARCADESCORE_UPDATE_FEED_OVERRIDE: path to a local JSON file with a hand-written
        release list. If set, this is used instead of any network call at all.
      - ARCADESCORE_UPDATE_REPO: "owner/repo" to check instead of the real project -
        point this at a disposable test repo with fake integer-tagged releases to
        exercise the real network path without touching the real repo's releases.
    """
    override_path = os.getenv("ARCADESCORE_UPDATE_FEED_OVERRIDE")
    if override_path:
        with open(override_path, "r", encoding="utf-8") as f:
            return json.load(f)

    repo = os.getenv("ARCADESCORE_UPDATE_REPO", DEFAULT_REPO)
    url = f"https://api.github.com/repos/{repo}/releases"
    response = requests.get(url, headers={"Accept": "application/vnd.github+json"}, timeout=10)
    response.raise_for_status()
    return response.json()


def find_latest_applicable_release(releases, include_prereleases):
    """Picks the highest build number among releases whose tag_name parses as a plain
    integer (silently skips this project's older semver-style tags like "1.0.0-rc1" -
    those predate this versioning scheme), honoring the pre-release opt-in."""
    best = None
    for release in releases or []:
        if release.get("draft"):
            continue
        if release.get("prerelease") and not include_prereleases:
            continue

        try:
            build = int(str(release.get("tag_name", "")).strip())
        except ValueError:
            continue

        if best is None or build > best["build"]:
            best = {
                "build": build,
                "tag_name": release.get("tag_name"),
                "published_at": release.get("published_at"),
                "url": release.get("html_url"),
                "prerelease": bool(release.get("prerelease")),
            }
    return best


def _get_meta(cursor, key, default=None):
    cursor.execute("SELECT value FROM meta WHERE key = ?", (key,))
    row = cursor.fetchone()
    return row[0] if row else default


def _set_meta(cursor, key, value):
    cursor.execute("SELECT 1 FROM meta WHERE key = ?", (key,))
    if cursor.fetchone():
        cursor.execute("UPDATE meta SET value = ? WHERE key = ?", (str(value), key))
    else:
        cursor.execute("INSERT INTO meta (key, value) VALUES (?, ?)", (key, str(value)))


def _status_from_cache(cursor, current_build, deployment_type, include_prereleases):
    latest_build_raw = _get_meta(cursor, "update_latest_build")
    latest_build = int(latest_build_raw) if latest_build_raw else None
    return {
        "current_build": current_build,
        "deployment_type": deployment_type,
        "include_prereleases": include_prereleases,
        "last_checked_at": _get_meta(cursor, "update_last_checked_at"),
        "latest_build": latest_build,
        "latest_published_at": _get_meta(cursor, "update_latest_published_at") or None,
        "latest_prerelease": _get_meta(cursor, "update_latest_prerelease") == "TRUE",
        "latest_url": _get_meta(cursor, "update_latest_url") or None,
        "update_available": bool(latest_build and latest_build > current_build),
        "error": None,
    }


def check_for_update(conn, force=False):
    """Returns the update status dict the API/UI use, using a cached result (in the
    meta table) when checked within the last hour unless force=True."""
    cursor = conn.cursor()
    include_prereleases = _get_meta(cursor, "update_include_prereleases", "FALSE") == "TRUE"
    current_build = get_current_build_number()
    deployment_type = detect_deployment_type()

    if not force:
        last_checked_raw = _get_meta(cursor, "update_last_checked_at")
        if last_checked_raw:
            try:
                last_checked = datetime.fromisoformat(last_checked_raw)
                if (datetime.now(timezone.utc) - last_checked).total_seconds() < CACHE_TTL_SECONDS:
                    return _status_from_cache(cursor, current_build, deployment_type, include_prereleases)
            except ValueError:
                pass

    try:
        releases = fetch_available_releases()
        latest = find_latest_applicable_release(releases, include_prereleases)
        error = None
    except Exception as e:
        latest = None
        error = str(e)

    now_iso = datetime.now(timezone.utc).isoformat()
    _set_meta(cursor, "update_last_checked_at", now_iso)
    if latest:
        _set_meta(cursor, "update_latest_build", latest["build"])
        _set_meta(cursor, "update_latest_published_at", latest["published_at"] or "")
        _set_meta(cursor, "update_latest_prerelease", "TRUE" if latest["prerelease"] else "FALSE")
        _set_meta(cursor, "update_latest_url", latest["url"] or "")
    conn.commit()

    return {
        "current_build": current_build,
        "deployment_type": deployment_type,
        "include_prereleases": include_prereleases,
        "last_checked_at": now_iso,
        "latest_build": latest["build"] if latest else None,
        "latest_published_at": latest["published_at"] if latest else None,
        "latest_prerelease": latest["prerelease"] if latest else None,
        "latest_url": latest["url"] if latest else None,
        "update_available": bool(latest and latest["build"] > current_build),
        "error": error,
    }


def set_prerelease_opt_in(conn, enabled):
    cursor = conn.cursor()
    _set_meta(cursor, "update_include_prereleases", "TRUE" if enabled else "FALSE")
    conn.commit()


def restart_app():
    """Best-effort self-restart: spawns a detached copy of run.py that survives this
    process exiting, then exits this process to free the port. Not a supervisor - if
    the new process fails to come up, nothing brings the app back automatically. The
    frontend polls for the app coming back and falls back to telling the admin to
    restart manually if it doesn't, rather than this function trying to guarantee
    success itself."""
    root = _project_root()
    python_exe = sys.executable
    script = os.path.join(root, "run.py")

    try:
        if os.name == "nt":
            subprocess.Popen(
                [python_exe, script],
                cwd=root,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )
        else:
            subprocess.Popen(
                [python_exe, script],
                cwd=root,
                start_new_session=True,
                close_fds=True,
            )
    except Exception as e:
        print(f"⚠️ Failed to spawn relaunch process for auto-restart: {e}")
        return

    # Give the new process's Python/eventlet startup a head start before this one
    # releases the port - best-effort, not a guarantee (see docstring).
    time.sleep(1)
    os._exit(0)


def apply_update(conn):
    """Only meaningful for a git deployment. Fetches the latest applicable tag, checks
    it out, reinstalls requirements, and schedules a restart attempt - never leaves a
    half-updated checkout on failure (each step raises before the next runs)."""
    deployment_type = detect_deployment_type()
    if deployment_type != "git":
        return {
            "success": False,
            "error": f"Automatic updates aren't available for a {deployment_type} deployment.",
        }

    cursor = conn.cursor()
    include_prereleases = _get_meta(cursor, "update_include_prereleases", "FALSE") == "TRUE"

    try:
        releases = fetch_available_releases()
    except Exception as e:
        return {"success": False, "error": f"Failed to check for releases: {e}"}

    latest = find_latest_applicable_release(releases, include_prereleases)
    current_build = get_current_build_number()
    if not latest or latest["build"] <= current_build:
        return {"success": False, "error": "No newer build is available."}

    root = _project_root()
    tag = latest["tag_name"]

    try:
        subprocess.run(["git", "fetch", "--tags"], cwd=root, check=True, capture_output=True, text=True, timeout=60)
        subprocess.run(["git", "checkout", tag], cwd=root, check=True, capture_output=True, text=True, timeout=60)
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=root, check=True, capture_output=True, text=True, timeout=300,
        )
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or str(e)).strip()
        return {"success": False, "error": f"Update failed: {detail}"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Update timed out."}

    eventlet.spawn_after(1, restart_app)
    return {
        "success": True,
        "message": f"Updated to build {latest['build']}. Attempting automatic restart...",
    }
