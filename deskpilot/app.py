"""Flaxon endpoints. File operations are available only to this local session."""

import secrets
import shutil
import tempfile
from datetime import date
from pathlib import Path

from flaxon import Flaxon, Request
from flaxon.http import JSONResponse, Response

from .files import FileWorkspace
from .guides import Guides
from .storage import Store


def create_app(data_directory: Path, *, debug=False):
    store = Store(data_directory)
    workspace = FileWorkspace(store)
    guides = Guides(store)
    token = secrets.token_urlsafe(32)
    app = Flaxon("DeskPilot", debug=debug)
    # Installed package files may be read-only under MSIX. Build in a temporary tree.
    runtime = Path(tempfile.mkdtemp(prefix="deskpilot-ui-"))
    shutil.copytree(Path(__file__).parent / "ui", runtime / "ui")
    app.use_teloce(
        project_root=runtime,
        ui_dir="ui",
        title="DeskPilot",
        options={
            "source_maps": debug,
            "spa": False,
            "minifier": "teloce" if debug else "minifyjs",
        },
    )
    app.workspace, app.guides, app.store = workspace, guides, store
    app.session_token, app.runtime_directory = token, runtime

    def authorize(request):
        host = request.headers.get("host", "").split(":")[0]
        if host not in ("127.0.0.1", "localhost", "testserver"):
            raise ValueError("Only local requests are allowed")
        if not secrets.compare_digest(
            request.headers.get("x-deskpilot-token", ""), token
        ):
            raise ValueError("Invalid local session; reopen DeskPilot")

    def endpoint(function):
        async def handler(request: Request):
            try:
                authorize(request)
                result = function(
                    request, await request.json() if request.method == "POST" else {}
                )
                return result if isinstance(result, Response) else JSONResponse(result)
            except (ValueError, KeyError, OSError, TypeError) as error:
                return JSONResponse({"error": str(error)}, status_code=400)

        handler.__name__ = function.__name__
        return handler

    @app.get("/api/state")
    @endpoint
    def state(request, payload):
        return {
            "roots": store.rows("SELECT * FROM roots ORDER BY id"),
            "documents": store.rows("SELECT * FROM documents ORDER BY name"),
            "guides": guides.list(),
            "batches": store.rows(
                "SELECT batch,COUNT(*) AS count FROM moves WHERE status='moved' GROUP BY batch"
            ),
            "recovery": store.rows(
                "SELECT source,destination FROM moves WHERE status='review'"
            ),
            "version": "0.1.0",
        }

    @app.post("/api/roots")
    @endpoint
    def roots(request, payload):
        root = workspace.register(payload["path"])
        workspace.index(root["id"])
        return root

    @app.post("/api/index")
    @endpoint
    def index(request, payload):
        return workspace.index(payload["root"])

    @app.post("/api/preview")
    @endpoint
    def preview(request, payload):
        return workspace.preview(payload["root"])

    @app.post("/api/apply")
    @endpoint
    def apply(request, payload):
        return workspace.apply(payload["token"])

    @app.post("/api/undo")
    @endpoint
    def undo(request, payload):
        return workspace.undo(payload["batch"])

    @app.post("/api/duplicates")
    @endpoint
    def duplicates(request, payload):
        return {"groups": workspace.duplicates(payload["root"])}

    @app.post("/api/document")
    @endpoint
    def document(request, payload):
        expiry = str(payload.get("expiry", ""))
        if expiry:
            date.fromisoformat(expiry)
        with store.connect() as connection:
            cursor = connection.execute(
                "UPDATE documents SET tags=?,expiry=? WHERE id=?",
                (str(payload.get("tags", ""))[:500], expiry, payload["id"]),
            )
            if cursor.rowcount != 1:
                raise ValueError("Document not found")
        return {"saved": True}

    @app.post("/api/images")
    @endpoint
    def images(request, payload):
        return guides.import_image(payload["data"])

    @app.post("/api/guide")
    @endpoint
    def guide(request, payload):
        return guides.save(payload)

    @app.post("/api/export")
    @endpoint
    def export(request, payload):
        return {"filename": guides.export(payload["id"]).name}

    @app.get("/image/<identifier>")
    async def image(request: Request, identifier: str):
        # Image elements cannot set a custom header; use the session token in the URL.
        try:
            if not secrets.compare_digest(request.query.get("token", ""), token):
                raise ValueError("Invalid session")
            return Response(
                guides.image_path(identifier).read_bytes(),
                media_type="image/png",
                headers={"cache-control": "no-store"},
            )
        except ValueError:
            return Response("Not found", status_code=404)

    @app.get("/download/<identifier>")
    async def download(request: Request, identifier: str):
        if not secrets.compare_digest(request.query.get("token", ""), token):
            return Response("Forbidden", status_code=403)
        try:
            return Response(
                guides.export(int(identifier)).read_bytes(),
                media_type="application/pdf",
                headers={
                    "content-disposition": f'attachment; filename="guide-{int(identifier)}.pdf"'
                },
            )
        except (ValueError, OSError):
            return Response("Not found", status_code=404)

    @app.get("/")
    async def home(request: Request):
        if request.headers.get("host", "").split(":")[0] not in (
            "127.0.0.1",
            "localhost",
            "testserver",
        ):
            return Response("Forbidden", status_code=403)
        response = await request.compile("app.html", {"token": token})
        response.headers["referrer-policy"] = "no-referrer"
        return response

    return app
