import base64
from io import BytesIO

import pytest
from deskpilot.app import create_app
from deskpilot.files import FileWorkspace
from deskpilot.guides import Guides
from deskpilot.storage import Store
from flaxon.testing import TestClient
from PIL import Image


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
