"""Launch one local Flaxon server, then open the Windows WebView2 shell."""

import argparse
import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

from .app import create_app


class DesktopActions:
    def __init__(self, app):
        self.app = app
        self.window = None

    def choose_folder(self):
        import webview

        selected = self.window.create_file_dialog(webview.FileDialog.FOLDER)
        return selected[0] if selected else None

    def reveal_document(self, identifier):
        rows = self.app.store.rows(
            "SELECT path,root_id FROM documents WHERE id=?", (int(identifier),)
        )
        if not rows:
            raise ValueError("Document not found")
        root = self.app.workspace.root(rows[0]["root_id"])
        path = self.app.workspace.safe_file(Path(rows[0]["path"]), root)
        if os.name == "nt":
            subprocess.Popen(["explorer.exe", "/select,", str(path)])
        return str(path)

    def export_guide(self, identifier):
        import webview

        source = self.app.guides.export(int(identifier))
        selected = self.window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=source.name,
            file_types=("PDF files (*.pdf)",),
        )
        if not selected:
            return None
        destination = Path(selected[0])
        if destination.suffix.lower() != ".pdf":
            destination = destination.with_suffix(".pdf")
        shutil.copyfile(source, destination)
        return f"Exported to {destination}"


def main():
    parser = argparse.ArgumentParser(description="DeskPilot local desktop workspace")
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Open a browser instead of the native shell",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Readable frontend output and source maps"
    )
    parser.add_argument("--data-dir", type=Path)
    arguments = parser.parse_args()
    data = (
        arguments.data_dir
        or Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share"))
        / "DeskPilot"
    )
    app = create_app(data, debug=arguments.debug)
    import uvicorn

    # Reserve the port before starting the server; never expose it to the LAN.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(app, log_level="warning", lifespan="on", log_config=None)
    )
    thread = threading.Thread(
        target=server.run, kwargs={"sockets": [listener]}, daemon=True
    )
    thread.start()
    try:
        deadline = time.monotonic() + 20
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("DeskPilot could not start its local backend")
            time.sleep(0.05)
        url = f"http://127.0.0.1:{port}/"
        if arguments.browser:
            import webbrowser

            webbrowser.open(url)
            print(f"DeskPilot is running at {url}. Press Ctrl+C to stop.")
            while thread.is_alive():
                time.sleep(0.5)
        else:
            import webview

            actions = DesktopActions(app)
            actions.window = webview.create_window(
                "DeskPilot",
                url,
                js_api=actions,
                width=1280,
                height=880,
                min_size=(800, 600),
            )
            webview.start(
                gui="edgechromium" if os.name == "nt" else None,
                debug=arguments.debug,
                storage_path=str(data / "webview"),
            )
    except KeyboardInterrupt:
        pass
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        shutil.rmtree(app.runtime_directory, ignore_errors=True)


if __name__ == "__main__":
    main()
