from flask import current_app, g
import sqlite3

def get_db():
    if "db" not in g:
        db_path = current_app.config["DB_PATH"]  # Get DB path from Flask config
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row  # Enables dictionary-like access
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()
