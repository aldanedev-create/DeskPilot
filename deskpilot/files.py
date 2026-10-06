"""Explicit folder access, reversible sorting, indexing and exact duplicates."""

import errno
import hashlib
import os
import shutil
import threading
import time
import uuid
from datetime import UTC, datetime
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
        self.lock = threading.RLock()
        self.reconcile_pending_moves()

    def reconcile_pending_moves(self):
        """Recover journal status after a crash without deleting either file."""
        for row in self.store.rows("SELECT * FROM moves WHERE status='undo_pending'"):
            source, destination = Path(row["source"]), Path(row["destination"])
            status = "review"
            try:
                if (
                    source.is_file()
                    and not source.is_symlink()
                    and not destination.exists()
                    and digest(source) == row["digest"]
                ):
                    status = "undone"
                elif (
                    destination.is_file()
                    and not destination.is_symlink()
                    and digest(destination) == row["digest"]
                    and (not source.exists() or os.path.samefile(source, destination))
                ):
                    status = "moved"
            except (OSError, ValueError):
                pass
            with self.store.connect() as connection:
                connection.execute(
                    "UPDATE moves SET status=? WHERE id=?", (status, row["id"])
                )
                if status == "undone":
                    connection.execute(
                        "UPDATE documents SET path=?,search_text=replace(search_text,?,?) WHERE path=?",
                        (
                            str(source),
                            str(destination).casefold(),
                            str(source).casefold(),
                            str(destination),
                        ),
                    )
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
        candidate = Path(path).expanduser().absolute()
        if any(
            item.is_symlink() or getattr(item, "is_junction", lambda: False)()
            for item in (candidate, *candidate.parents)
        ):
            raise ValueError("Symbolic links and junctions are not supported")
        root = candidate.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("Choose a folder, not a file")
        # Never index or organize the application's own data.
        data = self.store.directory.resolve()
        if root == data or root in data.parents or data in root.parents:
            raise ValueError("Choose a folder outside DeskPilot's data directory")
        for registered in self.store.rows("SELECT path FROM roots"):
            other = Path(registered["path"])
            if root != other and (root in other.parents or other in root.parents):
                raise ValueError(
                    "This folder overlaps another connected folder; connect separate folders"
                )
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
        if any(
            item.is_symlink() or getattr(item, "is_junction", lambda: False)()
            for item in (path, *path.parents)
        ):
            raise ValueError("Symbolic links are not supported")
        resolved = path.resolve(strict=True)
        if root not in resolved.parents or not resolved.is_file():
            raise ValueError("File must be inside the selected folder")
        return resolved

    def scan(self, identifier):
        root = self.root(identifier)
        files = []
        warnings = []
        self.scan_warnings = warnings
        for directory, folders, names in os.walk(
            root, followlinks=False, onerror=lambda error: warnings.append(str(error))
        ):
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
                try:
                    self.safe_file(path, root)
                except (OSError, ValueError) as error:
                    warnings.append(str(error))
                    continue
                files.append(path)
                if len(files) >= 50000:
                    warnings.append(
                        "Index stopped at 50,000 files; connect smaller separate folders for the rest"
                    )
                    return root, files
        return root, files

    def index(self, identifier):
        from .library import extract_text, search_text

        with self.lock:
            _root, files = self.scan(identifier)
            warnings = list(self.scan_warnings)
            current = set()
            with self.store.connect() as connection:
                existing = {
                    row["path"]: dict(row)
                    for row in connection.execute(
                        "SELECT * FROM documents WHERE root_id=?", (identifier,)
                    )
                }
                identities = {}
                for row in existing.values():
                    identities.setdefault(row["file_identity"], []).append(row)
                for path in files:
                    try:
                        stat = path.stat()
                        identity = f"{stat.st_dev}:{stat.st_ino}" if stat.st_ino else ""
                        old = existing.get(str(path))
                        # Preserve tags on an external rename only when identity is unambiguous.
                        candidates = identities.get(identity, [])
                        if (
                            not old
                            and identity
                            and len(candidates) == 1
                            and not Path(candidates[0]["path"]).exists()
                        ):
                            old = candidates[0]
                            connection.execute(
                                "UPDATE documents SET path=?,name=? WHERE id=?",
                                (str(path), path.name, old["id"]),
                            )
                        content = (
                            old["content"]
                            if old
                            and old["size"] == stat.st_size
                            and old["modified"] == stat.st_mtime
                            else extract_text(path)
                        )
                        connection.execute(
                            """INSERT INTO documents(root_id,path,name,size,modified,extension,content,file_identity)
                            VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET
                            name=excluded.name,size=excluded.size,modified=excluded.modified,
                            extension=excluded.extension,content=excluded.content,available=1,file_identity=excluded.file_identity""",
                            (
                                identifier,
                                str(path),
                                path.name,
                                stat.st_size,
                                stat.st_mtime,
                                path.suffix.lower(),
                                content,
                                identity,
                            ),
                        )
                        row = dict(
                            connection.execute(
                                "SELECT * FROM documents WHERE path=?", (str(path),)
                            ).fetchone()
                        )
                        connection.execute(
                            "UPDATE documents SET search_text=? WHERE id=?",
                            (search_text(row), row["id"]),
                        )
                        current.add(str(path))
                    except (OSError, ValueError) as error:
                        warnings.append(f"{path.name}: {error}")
                if not warnings:
                    for row in connection.execute(
                        "SELECT id,path FROM documents WHERE root_id=?", (identifier,)
                    ).fetchall():
                        if row["path"] not in current:
                            connection.execute(
                                "UPDATE documents SET available=0 WHERE id=?",
                                (row["id"],),
                            )
            return {"indexed": len(current), "warnings": warnings[:20]}

    def disconnect(self, identifier):
        if not self.store.rows("SELECT id FROM roots WHERE id=?", (identifier,)):
            raise ValueError("Folder is not registered")
        with self.lock, self.store.connect() as connection:
            connection.execute("DELETE FROM documents WHERE root_id=?", (identifier,))
            connection.execute("DELETE FROM roots WHERE id=?", (identifier,))
        self.previews.clear()
        return {"disconnected": True}

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

    def preview(self, identifier, *, mode="type", extension="", older_days=0):
        root = self.root(identifier)
        if mode not in ("type", "month"):
            raise ValueError("Choose sorting by type or month")
        older_days = int(older_days)
        if not 0 <= older_days <= 36500:
            raise ValueError("Age must be between 0 and 36,500 days")
        extension = str(extension).strip().lower()
        if extension and not extension.startswith("."):
            extension = "." + extension
        moves = []
        for path in sorted(root.iterdir()):
            if not path.is_file() or path.is_symlink() or path.name.startswith("."):
                continue
            if extension and path.suffix.lower() != extension:
                continue
            if older_days and path.stat().st_mtime > time.time() - older_days * 86400:
                continue
            category = next(
                (
                    name
                    for name, extensions in CATEGORIES.items()
                    if path.suffix.lower() in extensions
                ),
                "Other",
            )
            if mode == "month":
                category = (
                    datetime.fromtimestamp(path.stat().st_mtime, UTC)
                    .astimezone()
                    .strftime("%Y-%m")
                )
            destination = root / category / path.name
            if destination.parent.is_symlink() or (
                destination.parent.exists() and not destination.parent.is_dir()
            ):
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
        self.previews = {
            key: value
            for key, value in self.previews.items()
            if time.monotonic() - value["created"] < 900
        }
        while len(self.previews) >= 10:
            self.previews.pop(next(iter(self.previews)))
        self.previews[token] = {
            "root": str(root),
            "moves": moves,
            "created": time.monotonic(),
        }
        return {"token": token, "moves": moves}

    def apply(self, token, selected=None):
        with self.lock:
            return self._apply(token, selected)

    def _apply(self, token, selected=None):
        if token not in self.previews:
            raise ValueError("Preview expired; preview again")
        preview = self.previews.pop(token)
        if time.monotonic() - preview["created"] >= 900:
            raise ValueError("Preview expired; preview again")
        if selected is not None:
            if (
                not isinstance(selected, list)
                or not selected
                or not set(selected).issubset(
                    {move["source"] for move in preview["moves"]}
                )
            ):
                raise ValueError("Choose files from this preview")
            preview["moves"] = [
                move for move in preview["moves"] if move["source"] in selected
            ]
        if not preview["moves"]:
            raise ValueError("No files selected")
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
            try:
                self.move_without_overwrite(source, destination, move["digest"])
            except (OSError, ValueError) as error:
                self.reconcile_pending_moves()
                raise ValueError(
                    f"Stopped after {completed} moves. Completed files are in undo history. {error}"
                ) from error
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

    @staticmethod
    def move_without_overwrite(source, destination, expected_digest):
        if digest(source) != expected_digest:
            raise ValueError("Source changed; preview again")
        try:
            os.link(source, destination)
        except OSError as error:
            if error.errno not in (
                errno.EXDEV,
                errno.EPERM,
                errno.ENOTSUP,
                errno.EINVAL,
            ):
                raise
            # Exclusive creation supports FAT/exFAT too; a collision can never overwrite.
            created = False
            try:
                with destination.open("xb") as output:
                    created = True
                    with source.open("rb") as original:
                        shutil.copyfileobj(original, output, 1024 * 1024)
                    output.flush()
                    os.fsync(output.fileno())
                shutil.copystat(source, destination)
                if (
                    digest(destination) != expected_digest
                    or digest(source) != expected_digest
                ):
                    raise ValueError("Source changed during copy; original retained")
            except Exception:
                if created:
                    destination.unlink(missing_ok=True)
                raise
        if digest(source) != expected_digest:
            destination.unlink()
            raise ValueError("Source changed during move; original retained")
        source.unlink()

    def undo(self, batch):
        with self.lock:
            return self._undo(batch)

    def _undo(self, batch):
        rows = self.store.rows(
            "SELECT * FROM moves WHERE batch=? AND status='moved' ORDER BY id DESC",
            (batch,),
        )
        if not rows:
            raise ValueError("No completed moves in this batch")
        for row in rows:
            source, destination = Path(row["source"]), Path(row["destination"])
            self.safe_file(destination, source.parent.resolve())
            same_original = source.exists() and os.path.samefile(source, destination)
            if (source.exists() and not same_original) or digest(destination) != row[
                "digest"
            ]:
                raise ValueError(
                    "Undo stopped before moving files: a file changed or its original name is occupied"
                )
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
            with self.store.connect() as connection:
                connection.execute(
                    "UPDATE moves SET status='undo_pending' WHERE id=?", (row["id"],)
                )
            if not same_original:
                self.move_without_overwrite(destination, source, row["digest"])
            else:
                destination.unlink()
            with self.store.connect() as connection:
                connection.execute(
                    "UPDATE moves SET status='undone' WHERE id=?", (row["id"],)
                )
                connection.execute(
                    "UPDATE documents SET path=?,search_text=replace(search_text,?,?) WHERE path=?",
                    (
                        str(source),
                        str(destination).casefold(),
                        str(source).casefold(),
                        str(destination),
                    ),
                )
        return {"restored": len(rows)}
