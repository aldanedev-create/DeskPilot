"""Small SQLite store; each operation uses its own connection."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, directory: Path):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.database = directory / "deskpilot.sqlite3"
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS roots (
                    id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL);
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY, root_id INTEGER NOT NULL,
                    path TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '', expiry TEXT NOT NULL DEFAULT '');
                CREATE TABLE IF NOT EXISTS moves (
                    id INTEGER PRIMARY KEY, batch TEXT NOT NULL,
                    source TEXT NOT NULL, destination TEXT NOT NULL,
                    digest TEXT NOT NULL, status TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS guides (
                    id INTEGER PRIMARY KEY, title TEXT NOT NULL, steps TEXT NOT NULL);
            """)

        # Additive migrations preserve records from the first release.
        columns = {
            "size": "INTEGER NOT NULL DEFAULT 0",
            "modified": "REAL NOT NULL DEFAULT 0",
            "extension": "TEXT NOT NULL DEFAULT ''",
            "content": "TEXT NOT NULL DEFAULT ''",
            "search_text": "TEXT NOT NULL DEFAULT ''",
            "favorite": "INTEGER NOT NULL DEFAULT 0",
            "notes": "TEXT NOT NULL DEFAULT ''",
            "available": "INTEGER NOT NULL DEFAULT 1",
            "file_identity": "TEXT NOT NULL DEFAULT ''",
        }
        with self.connect() as connection:
            existing = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(documents)")
            }
            for name, definition in columns.items():
                if name not in existing:
                    connection.execute(
                        f"ALTER TABLE documents ADD COLUMN {name} {definition}"
                    )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS documents_root ON documents(root_id)"
            )
            connection.execute(
                "UPDATE documents SET search_text=lower(name || ' ' || path || ' ' || tags) WHERE search_text=''"
            )

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def rows(self, query, parameters=()):
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(query, parameters)]
