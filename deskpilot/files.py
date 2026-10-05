"""Explicit folder access, reversible sorting, indexing and exact duplicates."""

import hashlib
import os
import uuid
from pathlib import Path

CATEGORIES = {
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".md", ".xlsx", ".csv"},
    "Images": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"},
    "Videos": {".mp4", ".mov", ".mkv", ".webm"},
    "Audio": {".mp3", ".wav", ".flac", ".m4a"},
    "Archives": {".zip", ".7z", ".rar", ".tar", ".gz"},
}


def digest(path: Path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


class FileWorkspace:
    def __init__(self, store):
        self.store = store
        self.previews = {}
        self.reconcile_pending_moves()

    def reconcile_pending_moves(self):
        """Recover journal status after a crash without deleting either file."""
        for row in self.store.rows("SELECT * FROM moves WHERE status='pending'"):
            source, destination = Path(row["source"]), Path(row["destination"])
            status = "review"
            try:
                if destination.is_file() and not destination.is_symlink():
                    self.safe_file(destination, source.parent.resolve())
                    same_original = source.exists() and os.path.samefile(
                        source, destination
                    )
                    if digest(destination) == row["digest"] and (
                        not source.exists() or same_original
                    ):
                        status = "moved"
                elif source.is_file() and not destination.exists():
                    status = "cancelled"
            except (OSError, ValueError):
                pass
            with self.store.connect() as connection:
                connection.execute(
                    "UPDATE moves SET status=? WHERE id=?", (status, row["id"])
                )
                if status == "moved":
                    connection.execute(
                        "UPDATE documents SET path=? WHERE path=?",
                        (str(destination), str(source)),
                    )

    def register(self, path: str):
        root = Path(path).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise ValueError("Choose a folder, not a file")
        # Never index or organize the application's own data.
        data = self.store.directory.resolve()
        if root == data or root in data.parents or data in root.parents:
            raise ValueError("Choose a folder outside DeskPilot's data directory")
        with self.store.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO roots(path) VALUES (?)", (str(root),)
            )
        return self.store.rows("SELECT * FROM roots WHERE path=?", (str(root),))[0]

    def root(self, identifier):
        rows = self.store.rows("SELECT * FROM roots WHERE id=?", (identifier,))
        if not rows:
            raise ValueError("Folder is not registered")
        path = Path(rows[0]["path"])
        if not path.is_dir() or path.is_symlink():
            raise ValueError("Folder is unavailable")
        return path.resolve()

    def safe_file(self, path: Path, root: Path):
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
            raise ValueError("Symbolic links are not supported")
        resolved = path.resolve(strict=True)
        if root not in resolved.parents or not resolved.is_file():
            raise ValueError("File must be inside the selected folder")
        return resolved

    def scan(self, identifier):
        root = self.root(identifier)
        files = []
        for directory, folders, names in os.walk(root, followlinks=False):
            folders[:] = [
                name
                for name in sorted(folders)
                if not name.startswith(".")
                and not (Path(directory) / name).is_symlink()
            ]
            for name in sorted(names):
                path = Path(directory) / name
                if name.startswith(".") or path.is_symlink():
                    continue
                self.safe_file(path, root)
                files.append(path)
                if len(files) > 5000:
                    raise ValueError(
                        "This release supports up to 5,000 files per folder"
                    )
        return root, files

    def index(self, identifier):
        _root, files = self.scan(identifier)
        with self.store.connect() as connection:
            for path in files:
                connection.execute(
                    """INSERT INTO documents(root_id,path,name) VALUES (?,?,?)
                    ON CONFLICT(path) DO UPDATE SET name=excluded.name""",
                    (identifier, str(path), path.name),
                )
            existing = connection.execute(
                "SELECT id,path FROM documents WHERE root_id=?", (identifier,)
            ).fetchall()
            current = {str(path) for path in files}
            for row in existing:
                if row["path"] not in current:
                    connection.execute("DELETE FROM documents WHERE id=?", (row["id"],))
        return {"indexed": len(files)}

    def duplicates(self, identifier):
        root, files = self.scan(identifier)
        by_size = {}
        for path in files:
            by_size.setdefault(path.stat().st_size, []).append(path)
        groups = {}
        for candidates in by_size.values():
            if len(candidates) > 1:
                for path in candidates:
                    groups.setdefault(digest(path), []).append(
                        str(path.relative_to(root))
                    )
        return [paths for paths in groups.values() if len(paths) > 1]

    def preview(self, identifier):
        root = self.root(identifier)
        moves = []
        for path in sorted(root.iterdir()):
            if not path.is_file() or path.is_symlink() or path.name.startswith("."):
                continue
            category = next(
                (
                    name
                    for name, extensions in CATEGORIES.items()
                    if path.suffix.lower() in extensions
                ),
                "Other",
            )
            destination = root / category / path.name
            if destination.parent.is_symlink():
                raise ValueError("Destination folder is a symbolic link")
            moves.append(
                {
                    "source": str(path),
                    "destination": str(destination),
                    "digest": digest(self.safe_file(path, root)),
                    "conflict": destination.exists(),
                }
            )
        token = uuid.uuid4().hex
        self.previews[token] = {"root": str(root), "moves": moves}
        return {"token": token, "moves": moves}

    def apply(self, token):
        if token not in self.previews:
            raise ValueError("Preview expired; preview again")
        preview = self.previews.pop(token)
        root = Path(preview["root"])
        batch = uuid.uuid4().hex
        completed = 0
        # Preflight every file before moving any file.
        for move in preview["moves"]:
            source = self.safe_file(Path(move["source"]), root)
            destination = Path(move["destination"])
            if (
                digest(source) != move["digest"]
                or destination.exists()
                or destination.parent.is_symlink()
            ):
                raise ValueError("Files changed or a destination exists; preview again")
        for move in preview["moves"]:
            source, destination = Path(move["source"]), Path(move["destination"])
            destination.parent.mkdir(exist_ok=True)
            with self.store.connect() as connection:
                cursor = connection.execute(
                    "INSERT INTO moves(batch,source,destination,digest,status) VALUES (?,?,?,?,?)",
                    (batch, str(source), str(destination), move["digest"], "pending"),
                )
                identifier = cursor.lastrowid
            # Hard-link reservation refuses an overwrite, even if another app races us.
            os.link(source, destination)
            source.unlink()
            with self.store.connect() as connection:
                connection.execute(
                    "UPDATE moves SET status='moved' WHERE id=?", (identifier,)
                )
                connection.execute(
                    "UPDATE documents SET path=? WHERE path=?",
                    (str(destination), str(source)),
                )
            completed += 1
        return {"batch": batch, "moved": completed}

    def undo(self, batch):
        rows = self.store.rows(
            "SELECT * FROM moves WHERE batch=? AND status='moved' ORDER BY id DESC",
            (batch,),
        )
        if not rows:
            raise ValueError("No completed moves in this batch")
        for row in rows:
            source, destination = Path(row["source"]), Path(row["destination"])
            root = source.parent.resolve()
            self.safe_file(destination, root)
            same_original = source.exists() and os.path.samefile(source, destination)
            if (source.exists() and not same_original) or digest(destination) != row[
                "digest"
            ]:
                raise ValueError(
                    "Undo stopped: a file changed or its original name is occupied"
                )
            if not same_original:
                os.link(destination, source)
            destination.unlink()
            with self.store.connect() as connection:
                connection.execute(
                    "UPDATE moves SET status='undone' WHERE id=?", (row["id"],)
                )
                connection.execute(
                    "UPDATE documents SET path=? WHERE path=?",
                    (str(source), str(destination)),
                )
        return {"restored": len(rows)}
