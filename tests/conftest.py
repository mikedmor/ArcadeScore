"""Shared pytest fixtures.

Tests run against a real, throwaway SQLite file (not the dev/production
database) built the same way a fresh install is: app.modules.models.init_db()
+ migrate_db(), so the schema tests run against is exactly what a real
install ends up with, migration ladder included.

The webhook handlers under test (app.modules.webhooks) are plain functions
over (conn, data) - no Flask request/app context is needed to call them
directly. They do call socketio.emit() internally (via emit_message());
rather than standing up a real Socket.IO server, tests that care about what
got broadcast patch app.modules.webhooks.emit_message directly (see
tests/test_webhooks.py) and everything else just lets the real emit_message
run - flask_socketio.SocketIO.emit() is safe to call with no server attached
and no connected clients, it's just a no-op broadcast to nobody.
"""
import os
import sqlite3
import tempfile

import pytest
from flask import Flask

from app.modules.models import init_db, migrate_db
from app.modules.socketio import socketio


@pytest.fixture(scope="session", autouse=True)
def _init_socketio():
    """flask_socketio.SocketIO.emit() reads self.server, which stays None
    until init_app() has been called at least once - real code paths call
    emit_message()/emit_player_changes()/etc. unconditionally (not every
    call site is mocked per-test), so without this any handler that touches
    a socket event fails with "'NoneType' object has no attribute 'emit'"
    even though nothing about the emit itself is under test. A bare Flask
    app with no real transport attached is enough to make emit() a safe
    no-op broadcast to zero connected clients, matching what actually
    happens in production whenever nobody's viewing that room."""
    socketio.init_app(Flask(__name__), cors_allowed_origins="*")


@pytest.fixture
def conn():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        init_db(db_path)
        migrate_db(db_path)

        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()
    finally:
        os.remove(db_path)


def make_room(conn, user="testroom", room_name="Test Room", auto_hide_no_score_games="FALSE", default_preset=1):
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO settings (user, room_name, auto_hide_no_score_games, default_preset)
        VALUES (?, ?, ?, ?);
        """,
        (user, room_name, auto_hide_no_score_games, default_preset),
    )
    conn.commit()
    return cursor.lastrowid


def make_game(conn, room_id, game_name="Test Game", hidden="FALSE", game_color="#123456",
              css_score_cards=None, css_initials=None, css_scores=None, css_box=None, css_title=None):
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO games (game_name, room_id, hidden, game_color, game_sort,
                            css_score_cards, css_initials, css_scores, css_box, css_title)
        VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?);
        """,
        (game_name, room_id, hidden, game_color, css_score_cards, css_initials, css_scores, css_box, css_title),
    )
    conn.commit()
    return cursor.lastrowid


def make_webhook(conn, room_id, server_url="http://vpin.local:8089/", webhook_token="test-token"):
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO vpin_webhooks (room_id, server_url, webhook_uuid, webhook_name, webhook_token)
        VALUES (?, ?, ?, ?, ?);
        """,
        (room_id, server_url, f"uuid-{room_id}", "Test Webhook", webhook_token),
    )
    conn.commit()
    return cursor.lastrowid


def link_vpin_game(conn, room_id, arcadescore_game_id, vpin_game_id, server_url="http://vpin.local:8089/"):
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO vpin_games (server_url, arcadescore_game_id, vpin_game_id)
        VALUES (?, ?, ?);
        """,
        (server_url, arcadescore_game_id, vpin_game_id),
    )
    conn.commit()


def link_vpin_player(conn, arcadescore_player_id, vpin_player_id, server_url="http://vpin.local:8089/"):
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO vpin_players (server_url, arcadescore_player_id, vpin_player_id)
        VALUES (?, ?, ?);
        """,
        (server_url, arcadescore_player_id, vpin_player_id),
    )
    conn.commit()


def make_player(conn, full_name="Test Player", default_alias="TPL"):
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO players (full_name, default_alias) VALUES (?, ?);",
        (full_name, default_alias),
    )
    conn.commit()
    return cursor.lastrowid
