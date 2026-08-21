import sqlite3
from pathlib import Path


DB_FILE = Path(__file__).resolve().parents[1] / "data" / "platform.db"


def connect():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


def initialize_db():
    with connect() as connection:
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS scripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            version TEXT NOT NULL,
            entrypoint TEXT NOT NULL,
            package_path TEXT NOT NULL,
            version_path TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            script_id INTEGER NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 0,
            schedule TEXT,
            timeout_seconds INTEGER NOT NULL DEFAULT 600,
            network_enabled INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(script_id) REFERENCES scripts(id)
        );
        CREATE TABLE IF NOT EXISTS executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            exit_code INTEGER,
            log_path TEXT,
            error TEXT,
            FOREIGN KEY(task_id) REFERENCES tasks(id)
        );
        """)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(tasks)")}
        if "network_enabled" not in columns:
            connection.execute("ALTER TABLE tasks ADD COLUMN network_enabled INTEGER NOT NULL DEFAULT 0")
