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
