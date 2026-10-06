"""Bounded local text extraction and paginated, parameterized library search."""

import shlex
import zipfile
from datetime import UTC, datetime, timedelta
from xml.etree import ElementTree

TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".log",
    ".rst",
    ".html",
    ".css",
    ".js",
    ".py",
}
MAX_CONTENT = 100_000


def extract_text(path):
    """Never execute files or follow links; skip large and unsupported documents."""
    if path.stat().st_size > 10 * 1024 * 1024:
        return ""
    try:
        suffix = path.suffix.lower()
        if suffix in TEXT_EXTENSIONS:
            with path.open("rb") as stream:
                return stream.read(400_000).decode("utf-8", errors="replace")[
                    :MAX_CONTENT
                ]
        if suffix == ".docx":
            with zipfile.ZipFile(path) as archive:
                entry = archive.getinfo("word/document.xml")
                if entry.file_size > 2_000_000:
                    return ""
                xml = archive.read(entry)
                if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
                    return ""
                tree = ElementTree.fromstring(xml)
                return " ".join(
                    node.text or "" for node in tree.iter() if node.tag.endswith("}t")
                )[:MAX_CONTENT]
        if suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(path, strict=False)
            if reader.is_encrypted:
                return ""
            parts = []
            total = 0
            for page in reader.pages[:30]:
                # Huge content streams can allocate excessive memory in extract_text.
                contents = page.get_contents()
                if contents is not None and len(contents.get_data()) > 2_000_000:
                    continue
                text = page.extract_text() or ""
                parts.append(text[: MAX_CONTENT - total])
                total += len(parts[-1])
                if total >= MAX_CONTENT:
                    break
            return "\n".join(parts)[:MAX_CONTENT]
    except Exception:  # noqa: BLE001 - malformed third-party documents must not abort indexing
        # An unreadable document still appears in filename/tag search.
        return ""
    return ""


def search_text(row):
    return " ".join(
        str(row.get(key, "")) for key in ("name", "path", "tags", "notes", "content")
    ).casefold()


def search_documents(store, payload):
    query = str(payload.get("query", ""))[:500].strip()
    try:
        terms = shlex.split(query)
    except ValueError:
        terms = query.split()
    clauses, parameters = ["1=1"], []
    for term in terms[:20]:
        clauses.append("instr(search_text, ?) > 0")
        parameters.append(term.casefold())
    root = payload.get("root")
    if root:
        clauses.append("root_id=?")
        parameters.append(int(root))
    extension = str(payload.get("extension", "")).strip().lower()
    if extension:
        clauses.append("extension=?")
        parameters.append(extension if extension.startswith(".") else "." + extension)
    if payload.get("favorite"):
        clauses.append("favorite=1")
    status = payload.get("status", "available")
    if status in ("available", "missing"):
        clauses.append("available=?")
        parameters.append(int(status == "available"))
    expiry = payload.get("expiry", "")
    local_today = datetime.now(UTC).astimezone().date()
    today = local_today.isoformat()
    if expiry == "expired":
        clauses.append("expiry<>'' AND expiry < ?")
        parameters.append(today)
    elif expiry == "soon":
        clauses.append("expiry<>'' AND expiry >= ? AND expiry <= ?")
        parameters.extend([today, (local_today + timedelta(days=30)).isoformat()])
    minimum = max(0, int(payload.get("min_size", 0) or 0))
    if minimum:
        clauses.append("size>=?")
        parameters.append(minimum)
    sorting = {
        "name": "name COLLATE NOCASE,id",
        "recent": "modified DESC,id",
        "size": "size DESC,id",
        "expiry": "CASE WHEN expiry='' THEN 1 ELSE 0 END,expiry,id",
    }
    order = sorting.get(payload.get("sort"), sorting["name"])
    where = " AND ".join(clauses)
    total = store.rows(
        f"SELECT count(*) AS total FROM documents WHERE {where}", parameters
    )[0]["total"]
    page = max(1, int(payload.get("page", 1)))
    page_size = 50
    page = min(page, max(1, (total + page_size - 1) // page_size))
    rows = store.rows(
        f"SELECT id,root_id,path,name,tags,expiry,size,modified,extension,favorite,notes,available,content FROM documents WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?",
        parameters + [page_size, (page - 1) * page_size],
    )
    for row in rows:
        content = row.pop("content")
        offset = content.casefold().find(terms[0].casefold()) if terms else 0
        row["snippet"] = (
            content[max(0, offset - 50) : max(0, offset - 50) + 220] if content else ""
        )
    return {
        "documents": rows,
        "total": total,
        "page": page,
        "pages": max(1, (total + page_size - 1) // page_size),
    }
