"""Launch one local Flaxon server, then open the Windows WebView2 shell."""

import argparse
import json
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

    def open_document(self, identifier):
        rows = self.app.store.rows(
            "SELECT path,root_id FROM documents WHERE id=?", (int(identifier),)
        )
        if not rows:
            raise ValueError("Document not found")
        root = self.app.workspace.root(rows[0]["root_id"])
        path = self.app.workspace.safe_file(Path(rows[0]["path"]), root)
        if path.suffix.lower() not in {
            ".pdf",
            ".txt",
            ".md",
            ".docx",
            ".xlsx",
            ".csv",
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        }:
            raise ValueError("Use Show in folder to open this file type")
        if os.name == "nt":
            os.startfile(str(path))
        return str(path)

    def export_image(self, identifier):
        import webview

        source = self.app.guides.image_path(str(identifier))
        selected = self.window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename="screenshot.png",
            file_types=("PNG images (*.png)",),
        )
        if not selected:
            return None
        destination = Path(selected[0]).with_suffix(".png")
        shutil.copyfile(source, destination)
        return f"Exported to {destination}"

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
    parser = argparse.ArgumentParser(description="DeskHELP local desktop workspace")
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Open a browser instead of the native shell",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Readable frontend output and source maps"
    )
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument(
        "--smoke-result", type=Path, help="Test native startup and write a JSON result"
    )
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
                raise RuntimeError("DeskHELP could not start its local backend")
            time.sleep(0.05)
        url = f"http://127.0.0.1:{port}/"
        if arguments.browser:
            import webbrowser

            webbrowser.open(url)
            print(f"DeskHELP is running at {url}. Press Ctrl+C to stop.")
            while thread.is_alive():
                time.sleep(0.5)
        else:
            import webview

            actions = DesktopActions(app)
            actions.window = webview.create_window(
                "DeskHELP",
                url,
                js_api=actions,
                width=1280,
                height=880,
                min_size=(800, 600),
            )
            smoke = {
                "ok": False,
                "error": "Window closed before the interface was ready",
            }

            def check_native_window():
                try:
                    if not actions.window.events.loaded.wait(timeout=30):
                        raise RuntimeError("WebView2 page did not load")
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline:
                        ready = actions.window.evaluate_js(
                            "Boolean(document.querySelector('h1') && document.querySelector('.ocean') && document.body.innerText.includes('DeskHELP') && !document.body.innerText.includes('{{'))"
                        )
                        if ready:
                            smoke.update(ok=True, error=None)
                            break
                        time.sleep(0.2)
                    if not smoke["ok"]:
                        raise RuntimeError("DeskHELP interface did not mount")
                except Exception as error:  # noqa: BLE001 - record native startup failures for CI
                    smoke.update(ok=False, error=str(error))
                finally:
                    arguments.smoke_result.parent.mkdir(parents=True, exist_ok=True)
                    arguments.smoke_result.write_text(
                        json.dumps(smoke), encoding="utf-8"
                    )
                    actions.window.destroy()

            webview.start(
                func=check_native_window if arguments.smoke_result else None,
                gui="edgechromium" if os.name == "nt" else None,
                debug=arguments.debug,
                storage_path=str(data / "webview"),
            )
            if arguments.smoke_result and not smoke["ok"]:
                raise RuntimeError(smoke["error"])
    except Exception as error:
        if arguments.smoke_result:
            arguments.smoke_result.parent.mkdir(parents=True, exist_ok=True)
            arguments.smoke_result.write_text(
                json.dumps({"ok": False, "error": str(error)}), encoding="utf-8"
            )
        raise
    except KeyboardInterrupt:
        pass
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        shutil.rmtree(app.runtime_directory, ignore_errors=True)


if __name__ == "__main__":
    main()
