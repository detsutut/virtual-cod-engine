import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "sessions.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id                  INTEGER PRIMARY KEY,
                call_sid            TEXT    UNIQUE NOT NULL,
                caller_number       TEXT,
                created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                no_input_count      INTEGER DEFAULT 0,
                conversation_history TEXT   DEFAULT '[]',
                anagrafica          TEXT    DEFAULT NULL,
                email               TEXT    DEFAULT NULL,
                status              TEXT    DEFAULT 'active'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS anagrafiche (
                id          INTEGER PRIMARY KEY,
                call_sid    TEXT    NOT NULL,
                nome        TEXT,
                cognome     TEXT,
                file_path   TEXT,
                data        TEXT    NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (call_sid) REFERENCES sessions(call_sid)
            )
        """)
