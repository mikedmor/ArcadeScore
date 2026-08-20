"""Tests for the inbound VPin Studio webhook handlers (app/modules/webhooks.py).

These are pure functions over (conn, data) - the easiest thing in the app to
test, and historically where most of the real bugs lived. Several cases here
are direct regression tests for bugs that were found and fixed by hand -
the comments say which.
"""
from unittest.mock import patch, Mock

from app.modules.webhooks import (
    webhook_log_score,
    webhook_player,
    webhook_delete_player,
    webhook_game,
    webhook_delete_game,
    webhook_pause_state,
)
from tests.conftest import make_room, make_game, make_webhook, make_player, link_vpin_game, link_vpin_player


def _score_response(vpin_player_id, score, created_at="2026-08-19T12:00:00Z"):
    resp = Mock()
    resp.raise_for_status = Mock()
    resp.json.return_value = {"scores": [{
        "player": {"id": vpin_player_id},
        "score": score,
        "createdAt": created_at,
    }]}
    return resp


class TestWebhookLogScore:
    def test_missing_required_params(self, conn):
        result = webhook_log_score(conn, {})
        assert result["success"] is False
        assert "Missing required" in result["error"]

    def test_no_webhook_registered_for_room(self, conn):
        room_id = make_room(conn)
        result = webhook_log_score(conn, {"roomID": room_id, "id": 1})
        assert result["success"] is False
        assert "No VPin API URL found" in result["error"]

    def test_rejects_wrong_token(self, conn):
        room_id = make_room(conn)
        make_webhook(conn, room_id, webhook_token="correct-token")
        result = webhook_log_score(conn, {"roomID": room_id, "id": 1, "token": "wrong-token"})
        assert result["success"] is False
        assert "Invalid or missing webhook token" in result["error"]

    @patch("app.modules.webhooks.requests.get")
    def test_logs_a_new_score_and_emits_update(self, mock_get, conn):
        room_id = make_room(conn)
        make_webhook(conn, room_id, webhook_token="tok")
        game_id = make_game(conn, room_id)
        link_vpin_game(conn, room_id, game_id, vpin_game_id=42)
        player_id = make_player(conn)
        link_vpin_player(conn, player_id, vpin_player_id=7)

        mock_get.return_value = _score_response(vpin_player_id=7, score=123456)

        with patch("app.modules.webhooks.emit_message") as mock_emit:
            result = webhook_log_score(conn, {"roomID": room_id, "id": 42, "token": "tok"})

        assert result["success"] is True
        row = conn.execute("SELECT score, player_id FROM highscores WHERE game_id = ?", (game_id,)).fetchone()
        assert row["score"] == 123456
        assert row["player_id"] == player_id

        mock_emit.assert_called_once()
        event_name, payload = mock_emit.call_args.args
        assert event_name == "game_score_update"
        assert payload["gameID"] == game_id
        assert payload["roomID"] == room_id
        assert mock_emit.call_args.kwargs["room"] == f"room_{room_id}"

    @patch("app.modules.webhooks.requests.get")
    def test_duplicate_score_is_not_logged_twice(self, mock_get, conn):
        """Regression: dedup is checked by exact (game, player, score, timestamp,
        room) match - the same webhook firing twice for an already-seen score
        (VPin Studio retries) must not create a duplicate row."""
        room_id = make_room(conn)
        make_webhook(conn, room_id, webhook_token="tok")
        game_id = make_game(conn, room_id)
        link_vpin_game(conn, room_id, game_id, vpin_game_id=42)
        player_id = make_player(conn)
        link_vpin_player(conn, player_id, vpin_player_id=7)

        mock_get.return_value = _score_response(vpin_player_id=7, score=500, created_at="2026-08-19T12:00:00Z")

        with patch("app.modules.webhooks.emit_message"):
            webhook_log_score(conn, {"roomID": room_id, "id": 42, "token": "tok"})
            result = webhook_log_score(conn, {"roomID": room_id, "id": 42, "token": "tok"})

        assert result["success"] is False
        assert "No new scores" in result["error"]
        count = conn.execute("SELECT COUNT(*) c FROM highscores WHERE game_id = ?", (game_id,)).fetchone()["c"]
        assert count == 1

    @patch("app.modules.webhooks.requests.get")
    def test_auto_unhides_a_hidden_game_when_room_has_auto_hide_enabled(self, mock_get, conn):
        """A hidden (no-score) game becomes visible again the moment a real
        score lands, when the room's auto-hide setting is on."""
        room_id = make_room(conn, auto_hide_no_score_games="TRUE")
        make_webhook(conn, room_id, webhook_token="tok")
        game_id = make_game(conn, room_id, hidden="TRUE")
        link_vpin_game(conn, room_id, game_id, vpin_game_id=42)
        player_id = make_player(conn)
        link_vpin_player(conn, player_id, vpin_player_id=7)

        mock_get.return_value = _score_response(vpin_player_id=7, score=999)

        with patch("app.modules.webhooks.emit_message"):
            result = webhook_log_score(conn, {"roomID": room_id, "id": 42, "token": "tok"})

        assert result["success"] is True
        hidden = conn.execute("SELECT hidden FROM games WHERE id = ?", (game_id,)).fetchone()["hidden"]
        assert hidden == "FALSE"


class TestWebhookPlayer:
    @patch("app.modules.webhooks.requests.get")
    def test_create_uses_name_and_initials_not_fullname_alias(self, mock_get, conn):
        """Regression for VPIN-14: VPin Studio's real player object uses "name"
        and a single "initials" string - there is no fullName/alias/aliases
        field. A webhook_player CREATE that read the wrong keys silently
        created every new player as "Unknown Player"."""
        room_id = make_room(conn)
        make_webhook(conn, room_id, webhook_token="tok")

        resp = Mock()
        resp.raise_for_status = Mock()
        resp.json.return_value = {"name": "Michael Morris", "initials": "MDM"}
        mock_get.return_value = resp

        result = webhook_player(conn, {"roomID": room_id, "id": 99, "token": "tok"})

        assert result["success"] is True
        player = conn.execute("SELECT full_name, default_alias FROM players WHERE id = ?", (result["player_id"],)).fetchone()
        assert player["full_name"] == "Michael Morris"
        assert player["default_alias"] == "MDM"

    @patch("app.modules.webhooks.requests.get")
    def test_update_preserves_existing_link_and_changes_name(self, mock_get, conn):
        room_id = make_room(conn)
        make_webhook(conn, room_id, webhook_token="tok")
        player_id = make_player(conn, full_name="Old Name", default_alias="OLD")
        link_vpin_player(conn, player_id, vpin_player_id=99)

        resp = Mock()
        resp.raise_for_status = Mock()
        resp.json.return_value = {"name": "New Name", "initials": "NEW"}
        mock_get.return_value = resp

        result = webhook_player(conn, {"roomID": room_id, "id": 99, "token": "tok"})

        assert result["success"] is True
        assert result["player_id"] == player_id
        player = conn.execute("SELECT full_name FROM players WHERE id = ?", (player_id,)).fetchone()
        assert player["full_name"] == "New Name"


class TestWebhookDeletePlayer:
    def test_deletes_player_resolved_by_vpin_id(self, conn):
        player_id = make_player(conn)
        link_vpin_player(conn, player_id, vpin_player_id=55)

        result = webhook_delete_player(conn, {}, vpin_player_id=55)

        assert result["success"] is True
        assert conn.execute("SELECT COUNT(*) c FROM players WHERE id = ?", (player_id,)).fetchone()["c"] == 0

    def test_unknown_vpin_id_returns_error(self, conn):
        result = webhook_delete_player(conn, {}, vpin_player_id=999)
        assert result["success"] is False


class TestWebhookGame:
    @patch("app.modules.webhooks.fetch_game_images")
    @patch("app.modules.webhooks.requests.get")
    def test_new_game_applies_rooms_default_preset(self, mock_get, mock_media, conn):
        """Regression: webhook_game used to hardcode css_score_cards/css_initials/
        css_scores/css_box/css_title to None for every new game, ignoring the
        room's chosen style entirely (the "Selected Style Preset is not
        remembered when new games are added via webhooks" README bug)."""
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO presets (name, css_score_cards, css_initials, css_scores, css_box, css_title) "
            "VALUES ('Test Preset', 'sc', 'in', 'sco', 'bx', 'tt');"
        )
        preset_id = cursor.lastrowid
        conn.commit()

        room_id = make_room(conn, default_preset=preset_id)
        make_webhook(conn, room_id, webhook_token="tok")
        mock_media.return_value = {"backglass": None, "playfield": None}

        resp = Mock()
        resp.raise_for_status = Mock()
        resp.json.return_value = {"gameDisplayName": "New Game"}
        mock_get.return_value = resp

        result = webhook_game(conn, {"roomID": room_id, "id": 321, "token": "tok"})

        assert result["success"] is True
        game = conn.execute(
            "SELECT css_score_cards, css_initials, css_scores, css_box, css_title FROM games WHERE id = ?",
            (result["game_id"],),
        ).fetchone()
        assert dict(game) == {
            "css_score_cards": "sc", "css_initials": "in", "css_scores": "sco",
            "css_box": "bx", "css_title": "tt",
        }

    @patch("app.modules.webhooks.fetch_game_images")
    @patch("app.modules.webhooks.requests.get")
    def test_update_preserves_existing_color_and_style(self, mock_get, mock_media, conn):
        """Regression: a plain UPDATE webhook (e.g. a name change in VPin
        Studio) used to blank an already-styled game's CSS and color back to
        None/random, the same way it did for brand-new games."""
        room_id = make_room(conn)
        make_webhook(conn, room_id, webhook_token="tok")
        game_id = make_game(
            conn, room_id, game_name="Old Name", game_color="#abcdef",
            css_score_cards="keep-sc", css_initials="keep-in",
            css_scores="keep-sco", css_box="keep-bx", css_title="keep-tt",
        )
        link_vpin_game(conn, room_id, game_id, vpin_game_id=321)
        mock_media.return_value = {"backglass": None, "playfield": None}

        resp = Mock()
        resp.raise_for_status = Mock()
        resp.json.return_value = {"gameDisplayName": "Renamed Game"}
        mock_get.return_value = resp

        result = webhook_game(conn, {"roomID": room_id, "id": 321, "token": "tok"})

        assert result["success"] is True
        game = conn.execute(
            "SELECT game_name, game_color, css_score_cards, css_initials, css_scores, css_box, css_title "
            "FROM games WHERE id = ?", (game_id,),
        ).fetchone()
        assert game["game_name"] == "Renamed Game"
        assert game["game_color"] == "#abcdef"
        assert game["css_score_cards"] == "keep-sc"
        assert game["css_initials"] == "keep-in"
        assert game["css_scores"] == "keep-sco"
        assert game["css_box"] == "keep-bx"
        assert game["css_title"] == "keep-tt"

    def test_missing_room_id_is_rejected(self, conn):
        result = webhook_game(conn, {"id": 1})
        assert result["success"] is False
        assert "roomID" in result["error"]


class TestWebhookDeleteGame:
    def test_deletes_game_and_scores(self, conn):
        room_id = make_room(conn)
        game_id = make_game(conn, room_id)
        link_vpin_game(conn, room_id, game_id, vpin_game_id=88)
        conn.execute(
            "INSERT INTO highscores (game_id, player_id, score, room_id) VALUES (?, ?, ?, ?)",
            (game_id, make_player(conn), 100, room_id),
        )
        conn.commit()

        result = webhook_delete_game(conn, {}, vpin_game_id=88)

        assert result["success"] is True
        assert conn.execute("SELECT COUNT(*) c FROM games WHERE id = ?", (game_id,)).fetchone()["c"] == 0
        assert conn.execute("SELECT COUNT(*) c FROM highscores WHERE game_id = ?", (game_id,)).fetchone()["c"] == 0


class TestWebhookPauseState:
    def test_emits_pause_state_for_mapped_game(self, conn):
        room_id = make_room(conn)
        make_webhook(conn, room_id, webhook_token="tok")
        game_id = make_game(conn, room_id)
        link_vpin_game(conn, room_id, game_id, vpin_game_id=15)

        with patch("app.modules.webhooks.emit_message") as mock_emit:
            result = webhook_pause_state(conn, {"roomID": room_id, "id": 15, "token": "tok"}, paused=True)

        assert result["success"] is True
        mock_emit.assert_called_once()
        event_name, payload = mock_emit.call_args.args
        assert event_name == "game_pause_state"
        assert payload == {"gameID": game_id, "roomID": room_id, "paused": True}

    def test_missing_room_id_is_rejected(self, conn):
        result = webhook_pause_state(conn, {"id": 1}, paused=False)
        assert result["success"] is False
