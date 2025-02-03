import sqlite3
import os

MODEL_VERSION = 1

def init_db(db_path):
    try:
        if not os.path.exists(os.path.dirname(db_path)):
            os.makedirs(os.path.dirname(db_path))
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create db_version table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS db_version (
                id INTEGER PRIMARY KEY,
                version INTEGER NOT NULL
            )
        """)

        # Insert initial version and setup additional tables and demo values
        cursor.execute("SELECT COUNT(*) FROM db_version")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO db_version (version) VALUES (?)", (MODEL_VERSION,))

            # Highscores table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS highscores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id INTEGER NOT NULL,
                    game_id INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    event TEXT DEFAULT '',
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    room_id INTEGER NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Games table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_name TEXT NOT NULL,
                    room_id INTEGER NOT NULL,
                    css_score_cards TEXT,
                    css_initials TEXT,
                    css_scores TEXT,
                    css_box TEXT,
                    css_title TEXT,
                    score_type TEXT,
                    sort_ascending TEXT,
                    game_sort INTEGER,
                    game_image TEXT,
                    game_background TEXT,
                    tags TEXT,
                    hidden TEXT,
                    game_color TEXT
                );
            """)

            # Settings table
            cursor.execute("""
                CREATE TABLE "settings" (
                    "id"	INTEGER,
                    "user"	TEXT NOT NULL UNIQUE,
                    "room_name"	TEXT NOT NULL,
                    "public_scores_enabled"	TEXT,
                    "public_score_entry_enabled"	TEXT,
                    "api_read_access"	TEXT,
                    "api_write_access"	TEXT,
                    "admin_approval_email_list"	TEXT,
                    "admin_approval"	TEXT,
                    "long_names_enabled"	TEXT,
                    "idle_scroll"	TEXT,
                    "idle_scroll_method"	TEXT,
                    "show_qr"	TEXT,
                    "tournament_limit"	TEXT,
                    "auto_refresh_enabled"	TEXT,
                    "secure"	TEXT DEFAULT NULL,
                    "room_background"	TEXT DEFAULT '#f9f9f9',
                    "dateformat"	TEXT DEFAULT 'MM/DD/YYYY',
                    "show_wins_losses"	TEXT DEFAULT 'FALSE',
                    "default_preset"	INTEGER DEFAULT NULL,
                    "css_body"	TEXT DEFAULT 'display: flex;gap: 0px;padding: 0px;box-sizing: border-box;height: calc(100vh);background-color: #373737;',
                    "css_card"	TEXT DEFAULT 'flex: 0 0 300px;border-radius: 0px;box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);display: flex;flex-direction: column;position: relative;',
                    "auto_refresh_interval"	INTEGER DEFAULT 30,
                    "horizontal_scroll_enabled"	TEXT DEFAULT 'FALSE',
                    "horizontal_scroll_speed"	INTEGER DEFAULT 3,
                    "horizontal_scroll_delay"	INTEGER DEFAULT 2000,
                    "vertical_scroll_enabled"	TEXT DEFAULT 'FALSE',
                    "vertical_scroll_speed"	INTEGER DEFAULT 3,
                    "vertical_scroll_delay"	INTEGER DEFAULT 2000,
                    "fullscreen_enabled"	TEXT DEFAULT 'FALSE',
                    "text_autofit_enabled"	TEXT DEFAULT 'TRUE',
                    PRIMARY KEY("id" AUTOINCREMENT)
                );
            """)

            # Presets table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS presets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    css_body TEXT,
                    css_card TEXT,
                    css_score_cards TEXT,
                    css_initials TEXT,
                    css_scores TEXT,
                    css_box TEXT,
                    css_title TEXT
                );
            """)

            # Players table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    icon TEXT DEFAULT NULL,
                    css_initials TEXT DEFAULT NULL,
                    long_names_enabled TEXT DEFAULT 'FALSE',
                    default_alias TEXT NOT NULL
                );
            """)

            # Aliases table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id INTEGER NOT NULL,
                    alias TEXT NOT NULL,
                    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
                );
            """)

            cursor.execute("SELECT COUNT(*) FROM settings;")
            if cursor.fetchone()[0] == 0:  # No settings exist
                # Insert placeholder data for settings
                cursor.execute("""
                    INSERT OR IGNORE INTO settings (
                        user, room_name, public_scores_enabled, public_score_entry_enabled, 
                        api_read_access, api_write_access, admin_approval_email_list, admin_approval, 
                        long_names_enabled, idle_scroll, idle_scroll_method, show_qr, tournament_limit, auto_refresh_enabled,
                        secure, room_background, dateformat, show_wins_losses, default_preset,
                        css_body, 
                        css_card
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    "default", "My Game Room", "TRUE", "TRUE", 
                    "TRUE", "TRUE", "", "FALSE", 
                    "FALSE", "TRUE", "JustInTime", "FALSE", "10", "TRUE",
                    None, "#000000", "MM/DD/YYYY", "FALSE", 1,
                    "display: flex;gap: 0px;padding: 0px;box-sizing: border-box;height: calc(100vh);background-color: #373737;", 
                    r"flex: 0 0 300px;border-radius: 0px;box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);display: flex;flex-direction: column;position: relative;background-color: {GameColor};background-image: url('{GameBackground}');background-size: 100% auto;background-repeat: repeat-y;background-position: top 180px center;"
                ))

            # Check if placeholder data is needed
            cursor.execute("SELECT COUNT(*) FROM games;")
            if cursor.fetchone()[0] == 0:  # No games exist
                # Insert placeholder data for games
                cursor.execute("""
                    INSERT OR IGNORE INTO games (
                            game_name, 
                            room_id, 
                            css_score_cards, 
                            css_initials, 
                            css_scores, 
                            css_box, 
                            css_title, 
                            score_type, 
                            sort_ascending, 
                            game_sort, 
                            game_image, 
                            game_background, 
                            tags, 
                            hidden, 
                            game_color
                        )
                    VALUES 
                        (
                            "Black Rose (Bally 1992)", 
                            1, 
                            "background-color: rgba(255, 255, 255, 0.8);border-radius: 6px;padding: 10px;border: 1px solid #ccc;font-size: 1.2rem;margin-bottom: 10px;", 
                            "font-size: 60px; font-family:'Federation'", 
                            "font-size: 30px; color: black;", 
                            "height: 180px;object-fit: cover;object-position: top;position: absolute;width: 100%;border-bottom: 2px solid white;", 
                            "width: calc(100% - 20px);height: 160px;font-size: clamp(10px, 2.5rem, 38px);font-weight: bold;color: white;-webkit-text-stroke: 2px black;font-family: sans-serif;line-height: 1.1;white-space: normal;word-wrap: break-word;display: flex;align-items: center;text-align: center;justify-content: center;z-index: 100;padding: 10px;flex: 0 0 160px;overflow: hidden;", 
                            "hideBoth",
                            "FALSE", 
                            1, 
                            "/static/images/gameImage/0Htk9ITwd6_1722849149532.webp", 
                            "/static/images/gameBackground/2123d45ce5d7887bb786a1e59d771110_table_1638093698100.webp", 
                            "https://virtualpinballspreadsheet.github.io/?game=qQNywC8u&fileType=table#zUJ07JKe", 
                            "FALSE", 
                            "#9d0303"
                        ),
                        (
                            "Breakshot (Capcom 1996)", 
                            1, 
                            "background-color: rgba(255, 255, 255, 0.8);border-radius: 6px;padding: 10px;border: 1px solid #ccc;font-size: 1.2rem;margin-bottom: 10px;", 
                            "font-size: 60px; font-family:'Federation'", 
                            "font-size: 30px; color: black;", 
                            "height: 180px;object-fit: cover;object-position: top;position: absolute;width: 100%;border-bottom: 2px solid white;", 
                            "width: calc(100% - 20px);height: 160px;font-size: clamp(10px, 2.5rem, 38px);font-weight: bold;color: white;-webkit-text-stroke: 2px black;font-family: sans-serif;line-height: 1.1;white-space: normal;word-wrap: break-word;display: flex;align-items: center;text-align: center;justify-content: center;z-index: 100;padding: 10px;flex: 0 0 160px;overflow: hidden;", 
                            "hideBoth",
                            "FALSE", 
                            2, 
                            "/static/images/gameImage/DBuBjPTMPx_1718197325142.webp", 
                            "/static/images/gameBackground/5QKRlioCxO_1717972165641.webp", 
                            "https://virtualpinballspreadsheet.github.io/?game=BQbsQc3p&fileType=table#5QKRlioCxO", 
                            "FALSE", 
                            "#000000"
                        );
                """)

            cursor.execute("SELECT COUNT(*) FROM presets;")
            if cursor.fetchone()[0] == 0:  # No presets exist
                # Insert placeholder data for presets
                cursor.execute("""
                    INSERT OR IGNORE INTO presets (
                            name, 
                            css_body, 
                            css_card, 
                            css_score_cards, 
                            css_initials, 
                            css_scores, 
                            css_box, 
                            css_title
                            )
                    VALUES 
                        (
                            "Default", 
                            "display: flex;gap: 0px;padding: 0px;box-sizing: border-box;height: calc(100vh);background-color: #373737;", 
                            "flex: 0 0 300px;border-radius: 0px;box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);display: flex;flex-direction: column;position: relative;", 
                            "background-color: rgba(255, 255, 255, 0.8);border-radius: 6px;padding: 10px;border: 1px solid #ccc;font-size: 1.2rem;margin-bottom: 10px;", 
                            "font-size: 60px;font-family:'Federation';", 
                            "font-size: 30px; color: black;", 
                            "height: 180px;object-fit: cover;object-position: top;position: absolute;width: 100%;border-bottom: 2px solid white;", 
                            "width: calc(100% - 20px);height: 160px;font-size: clamp(10px, 2.5rem, 38px);font-weight: bold;color: white;-webkit-text-stroke: 2px black;font-family: sans-serif;line-height: 1.1;white-space: normal;word-wrap: break-word;display: flex;align-items: center;text-align: center;justify-content: center;z-index: 100;padding: 10px;flex: 0 0 160px;overflow: hidden;"
                        );
                """)

        conn.commit()
        conn.close()
        print(f"Database initialized successfully at {db_path}")
    except Exception as e:
        print(f"Error initializing database: {e}")

def migrate_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Fetch the current version
    cursor.execute("SELECT version FROM db_version")
    current_version = cursor.fetchone()[0]

    # Perform migrations as necessary
    # if current_version < 2:
    #     cursor.execute("""
    #         
    #     """)
    #     cursor.execute("UPDATE db_version SET version = 2")
    #     print("Database migrated to version 2")
    
    # if current_version < 3:
    #     cursor.execute("""
    #         
    #     """)
    #     cursor.execute("UPDATE db_version SET version = 3")
    #     print("Database migrated to version 3")
    
    # if current_version < 4:
    #     cursor.execute("""
    #         
    #     """)
    #     cursor.execute("UPDATE db_version SET version = 4")
    #     print("Database migrated to version 4")

    # if current_version < 5:
    #     cursor.execute("""
    #         
    #     """)
    #     cursor.execute("UPDATE db_version SET version = 5")
    #     print("Database migrated to version 5")
    
    # if current_version < 6:
    #     cursor.execute("""
    #         
    #     """)
    #     cursor.execute("UPDATE db_version SET version = 6")
    #     print("Database migrated to version 6")

    conn.commit()
    conn.close()