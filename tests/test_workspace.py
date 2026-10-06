import base64
from io import BytesIO

import pytest
from flaxon.testing import TestClient
from PIL import Image

from deskpilot.app import create_app
from deskpilot.files import FileWorkspace
from deskpilot.guides import Guides
from deskpilot.storage import Store


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "Downloads"
    root.mkdir()
    store = Store(tmp_path / "data")
    files = FileWorkspace(store)
    registered = files.register(str(root))
    return files, root, registered["id"]


def test_sort_and_undo_preserve_contents_and_metadata(workspace):
    files, root, identifier = workspace
    (root / "invoice.pdf").write_bytes(b"important invoice")
    files.index(identifier)
    preview = files.preview(identifier)
    assert not (root / "Documents").exists()
    applied = files.apply(preview["token"])
    assert (root / "Documents/invoice.pdf").read_bytes() == b"important invoice"
    assert not (root / "invoice.pdf").exists()
    assert files.undo(applied["batch"])["restored"] == 1
    assert (root / "invoice.pdf").read_bytes() == b"important invoice"
    assert files.store.rows("SELECT path FROM documents")[0]["path"] == str(
        root / "invoice.pdf"
    )


def test_conflicting_destinations_and_changed_files_are_rejected(workspace):
    files, root, identifier = workspace
    (root / "note.txt").write_text("old")
    preview = files.preview(identifier)
    (root / "note.txt").write_text("changed")
    with pytest.raises(ValueError):
        files.apply(preview["token"])
    (root / "Documents").mkdir()
    (root / "Documents/note.txt").write_text("do not overwrite")
    with pytest.raises(ValueError):
        files.apply(files.preview(identifier)["token"])
    assert (root / "Documents/note.txt").read_text() == "do not overwrite"


def test_undo_rejects_modified_destination(workspace):
    files, root, identifier = workspace
    (root / "note.txt").write_text("original")
    applied = files.apply(files.preview(identifier)["token"])
    (root / "Documents/note.txt").write_text("edited")
    with pytest.raises(ValueError):
        files.undo(applied["batch"])
    assert not (root / "note.txt").exists()


def test_duplicates_use_contents_not_names(workspace):
    files, root, identifier = workspace
    (root / "a.txt").write_text("same")
    (root / "b.txt").write_text("same")
    (root / "c.txt").write_text("diff")
    assert files.duplicates(identifier) == [["a.txt", "b.txt"]]


def test_symlink_destination_cannot_escape(workspace, tmp_path):
    files, root, identifier = workspace
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (root / "Documents").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks unavailable")
    (root / "a.txt").write_text("private")
    with pytest.raises(ValueError):
        files.preview(identifier)


def test_guide_persistence_and_pdf(tmp_path):
    store = Store(tmp_path / "data")
    guides = Guides(store)
    image = BytesIO()
    Image.new("RGB", (400, 200), "#265b48").save(image, format="PNG")
    screenshot = guides.import_image(
        "data:image/png;base64," + base64.b64encode(image.getvalue()).decode()
    )
    guide = guides.save(
        {
            "title": "My guide",
            "steps": [
                {
                    "image": screenshot["image"],
                    "title": "Start",
                    "description": "First step",
                }
            ],
        }
    )
    assert Guides(Store(tmp_path / "data")).list()[0]["title"] == "My guide"
    assert guides.export(guide["id"]).read_bytes().startswith(b"%PDF")
    with pytest.raises(ValueError):
        guides.image_path("../outside")


def test_api_session_and_production_component(tmp_path):
    app = create_app(tmp_path / "data")
    app.teloce.build()
    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/api/state").status_code == 400
    response = client.get(
        "/api/state", headers={"x-deskpilot-token": app.session_token}
    )
    assert response.status_code == 200
    assert app.teloce.build_result["minifier"] == "minifyjs"
    assert (app.teloce.build_dir / "ui/app.js").exists()


def test_interrupted_hard_link_move_can_be_undone(workspace):
    import os

    from deskpilot.files import digest

    files, root, _identifier = workspace
    source = root / "note.txt"
    source.write_text("keep me")
    destination = root / "Documents/note.txt"
    destination.parent.mkdir()
    os.link(source, destination)
    with files.store.connect() as connection:
        connection.execute(
            "INSERT INTO moves(batch,source,destination,digest,status) VALUES (?,?,?,?,?)",
            ("interrupted", str(source), str(destination), digest(source), "pending"),
        )
    reopened = FileWorkspace(files.store)
    assert reopened.undo("interrupted")["restored"] == 1
    assert source.read_text() == "keep me"
    assert not destination.exists()


def test_library_searches_words_phrases_content_and_filters(workspace):
    from deskpilot.library import search_documents

    files, root, identifier = workspace
    (root / "policy.txt").write_text(
        "Renew the coastal insurance policy in June", encoding="utf-8"
    )
    (root / "other.txt").write_text("unrelated")
    files.index(identifier)
    row = files.store.rows("SELECT * FROM documents WHERE name='policy.txt'")[0]
    with files.store.connect() as connection:
        connection.execute(
            "UPDATE documents SET favorite=1,expiry='2000-01-01' WHERE id=?",
            (row["id"],),
        )
    results = search_documents(
        files.store,
        {
            "query": 'June "coastal insurance"',
            "favorite": True,
            "expiry": "expired",
            "extension": "txt",
            "root": identifier,
        },
    )
    assert results["total"] == 1
    assert "coastal insurance" in results["documents"][0]["snippet"]
    assert search_documents(files.store, {"query": "June unrelated"})["total"] == 0
    assert search_documents(files.store, {"query": "' OR 1=1 --"})["total"] == 0


def test_index_preserves_metadata_on_missing_files_and_external_rename(workspace):
    files, root, identifier = workspace
    path = root / "first.txt"
    path.write_text("same")
    files.index(identifier)
    with files.store.connect() as connection:
        connection.execute(
            "UPDATE documents SET tags='important',notes='Keep this',favorite=1"
        )
    path.rename(root / "renamed.txt")
    files.index(identifier)
    rows = files.store.rows("SELECT * FROM documents")
    assert len(rows) == 1 and rows[0]["tags"] == "important"
    (root / "renamed.txt").unlink()
    files.index(identifier)
    row = files.store.rows("SELECT * FROM documents")[0]
    assert row["available"] == 0 and row["notes"] == "Keep this"


def test_selected_sort_skips_conflicts_and_month_is_reversible(workspace):
    files, root, identifier = workspace
    (root / "a.txt").write_text("a")
    (root / "b.txt").write_text("b")
    (root / "Documents").mkdir()
    (root / "Documents/b.txt").write_text("occupied")
    preview = files.preview(identifier)
    result = files.apply(preview["token"], [str(root / "a.txt")])
    assert result["moved"] == 1 and (root / "b.txt").exists()
    files.undo(result["batch"])
    preview = files.preview(identifier, mode="month", extension="txt")
    result = files.apply(preview["token"], [str(root / "a.txt")])
    assert files.undo(result["batch"])["restored"] == 1


def test_undo_preflights_entire_batch(workspace):
    files, root, identifier = workspace
    (root / "a.txt").write_text("a")
    (root / "b.txt").write_text("b")
    result = files.apply(files.preview(identifier)["token"])
    (root / "Documents/a.txt").write_text("edited")
    with pytest.raises(ValueError):
        files.undo(result["batch"])
    # b would otherwise have been restored before discovering the a conflict.
    assert (root / "Documents/b.txt").exists() and not (root / "b.txt").exists()


def test_copy_fallback_preserves_files_and_refuses_collision(workspace, monkeypatch):
    import errno
    import os

    from deskpilot.files import digest

    files, root, _ = workspace
    source = root / "a.txt"
    source.write_text("original")
    destination = root / "b.txt"

    def unsupported(*args, **kwargs):
        raise OSError(errno.ENOTSUP, "Hard links unsupported")

    monkeypatch.setattr(os, "link", unsupported)
    files.move_without_overwrite(source, destination, digest(source))
    assert destination.read_text() == "original" and not source.exists()
    source.write_text("keep this")
    with pytest.raises(FileExistsError):
        files.move_without_overwrite(source, destination, digest(source))
    assert source.read_text() == "keep this" and destination.read_text() == "original"


def test_library_pagination_docx_and_pdf_extraction(workspace):
    import zipfile

    from reportlab.pdfgen import canvas

    from deskpilot.library import extract_text, search_documents

    files, root, identifier = workspace
    for index in range(55):
        (root / f"note-{index}.txt").write_text("sample")
    with zipfile.ZipFile(root / "word.docx", "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="word"><w:t>Unique document phrase</w:t></w:document>',
        )
    pdf = canvas.Canvas(str(root / "sample.pdf"))
    pdf.drawString(40, 700, "Searchable invoice reference")
    pdf.save()
    assert "Unique document phrase" in extract_text(root / "word.docx")
    assert "invoice reference" in extract_text(root / "sample.pdf")
    files.index(identifier)
    first = search_documents(files.store, {})
    second = search_documents(files.store, {"page": 2})
    assert (
        first["total"] == 57
        and len(first["documents"]) == 50
        and len(second["documents"]) == 7
    )
    assert not {row["id"] for row in first["documents"]} & {
        row["id"] for row in second["documents"]
    }


def test_overlapping_folders_are_rejected(workspace):
    files, root, _ = workspace
    child = root / "Child"
    child.mkdir()
    with pytest.raises(ValueError, match="overlaps"):
        files.register(str(child))


def test_api_search_updates_notes_and_favorites(tmp_path):
    app = create_app(tmp_path / "data")
    root = tmp_path / "documents"
    root.mkdir()
    (root / "receipt.txt").write_text("hardware purchase")
    identifier = app.workspace.register(str(root))["id"]
    app.workspace.index(identifier)
    row = app.store.rows("SELECT * FROM documents")[0]
    client = TestClient(app)
    headers = {"x-deskpilot-token": app.session_token}
    response = client.post(
        "/api/document",
        json_data={
            "id": row["id"],
            "notes": "Project Ocean",
            "favorite": True,
            "tags": "work",
            "expiry": "",
        },
        headers=headers,
    )
    assert response.status_code == 200
    result = client.post(
        "/api/search",
        json_data={"query": "Ocean hardware", "favorite": True},
        headers=headers,
    )
    assert result.json()["total"] == 1


def test_interrupted_undo_restores_journal_and_metadata(workspace):
    files, root, identifier = workspace
    (root / "note.txt").write_text("original")
    files.index(identifier)
    applied = files.apply(files.preview(identifier)["token"])
    (root / "Documents/note.txt").rename(root / "note.txt")
    with files.store.connect() as connection:
        connection.execute(
            "UPDATE moves SET status='undo_pending' WHERE batch=?", (applied["batch"],)
        )
    FileWorkspace(files.store)
    assert files.store.rows("SELECT status FROM moves")[0]["status"] == "undone"
    assert files.store.rows("SELECT path FROM documents")[0]["path"] == str(
        root / "note.txt"
    )
