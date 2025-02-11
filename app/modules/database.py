from flask import current_app, g
import sqlite3

db_version = 1

def get_db(db_path=None):
    """Retrieve database connection, optionally using a different database file."""
    if db_path is None:
        db_path = current_app.config["DB_PATH"]  # Use default database path if none is provided

    if "db" not in g or getattr(g, "db_path", None) != db_path:
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row  # Enables dictionary-like access
        g.db_path = db_path  # Track which database file is open

    return g.db

def close_db(e=None):
    """Close the database connection if it exists."""
    db = g.pop("db", None)
    if db is not None:
        db.close()
