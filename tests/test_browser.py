"""Run DESKPILOT_BROWSER_TESTS=1 with Playwright Chromium installed."""

import os
import socket
import threading
import time

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("DESKPILOT_BROWSER_TESTS") != "1", reason="Opt-in Chromium check"
)


def test_production_workspace_interactions(tmp_path):
    import uvicorn
    from playwright.sync_api import expect, sync_playwright

    from deskpilot.app import create_app

    folder = tmp_path / "Downloads"
    folder.mkdir()
    (folder / "invoice.txt").write_text("Important document")
    (folder / "invoice-copy.txt").write_text("Important document")
    app = create_app(tmp_path / "data")
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    worker = threading.Thread(
        target=server.run, kwargs={"sockets": [listener]}, daemon=True
    )
    worker.start()
    try:
        deadline = time.monotonic() + 15
        while not server.started:
            assert worker.is_alive() and time.monotonic() < deadline
            time.sleep(0.05)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            javascript_requests = []
            page.on(
                "request",
                lambda request: (
                    javascript_requests.append(request.url)
                    if request.url.split("?")[0].endswith(".js")
                    else None
                ),
            )
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{listener.getsockname()[1]}/")
            page.get_by_label("Folder path").fill(str(folder))
            page.get_by_role("button", name="Connect folder", exact=True).click()
            page.get_by_text("Folder connected and indexed.").wait_for()
            page.get_by_role("button", name="Find exact duplicates").click()
            page.get_by_role("heading", name="Identical content").wait_for()
            page.get_by_role("button", name="Preview sorting").click()
            page.get_by_role("heading", name="Review before moving").wait_for()
            page.get_by_role("button", name="Move these files").click()
            page.get_by_text("2 files moved. Undo is available below.").wait_for()
            assert (folder / "Documents/invoice.txt").exists()
            page.get_by_role("button", name="Undo moves").click()
            page.get_by_text("2 files restored.").wait_for()
            assert (folder / "invoice.txt").exists()
            page.get_by_role("button", name="Document library").click()
            page.get_by_label("Search documents").fill("invoice-copy")
            expect(page.locator(".document")).to_have_count(1)
            page.get_by_role("button", name="Screenshot guides").click()
            page.get_by_label("Guide title").fill("My first guide")
            from PIL import Image

            screenshot = tmp_path / "screenshot.png"
            Image.new("RGB", (400, 200), "#265b48").save(screenshot)
            page.locator("input[type=file]").set_input_files(screenshot)
            page.get_by_label("Step title").wait_for()
            page.get_by_label("Step title").fill("Start here")
            canvas = page.locator("#annotation-canvas")
            page.wait_for_function(
                "document.querySelector('#annotation-canvas').width === 400"
            )

            def draw(x1, y1, x2, y2):
                bounds = canvas.bounding_box()
                width = canvas.evaluate("node => node.width")
                height = canvas.evaluate("node => node.height")
                page.mouse.move(
                    bounds["x"] + x1 * bounds["width"] / width,
                    bounds["y"] + y1 * bounds["height"] / height,
                )
                page.mouse.down()
                page.mouse.move(
                    bounds["x"] + x2 * bounds["width"] / width,
                    bounds["y"] + y2 * bounds["height"] / height,
                    steps=5,
                )
                page.mouse.up()

            def pixel(x, y):
                return canvas.evaluate(
                    "(node, p) => Array.from(node.getContext('2d').getImageData(p[0], p[1], 1, 1).data)",
                    [x, y],
                )

            original = pixel(80, 40)
            draw(50, 40, 200, 100)
            assert pixel(80, 40)[0] > 200
            page.get_by_role("button", name="Undo edit", exact=True).click()
            assert pixel(80, 40) == original
            page.get_by_role("button", name="Redo edit", exact=True).click()
            assert pixel(80, 40)[0] > 200
            page.get_by_role("combobox", name="Annotation tool").select_option("eraser")
            page.get_by_role("spinbutton", name="Stroke / eraser size").fill("20")
            draw(70, 40, 90, 40)
            assert pixel(80, 40) == original
            page.get_by_role("combobox", name="Annotation tool").select_option("crop")
            draw(10, 10, 310, 160)
            assert 299 <= canvas.evaluate("node => node.width") <= 301
            page.get_by_role("button", name="Rotate 90°", exact=True).click()
            assert 149 <= canvas.evaluate("node => node.width") <= 151
            # Save automatically persists the active image without Keep annotations.

            page.get_by_label("Step description").fill("This is the first step.")
            page.get_by_role("button", name="Save guide", exact=True).click()
            page.get_by_text("Guide saved.").wait_for()
            assert len(app.guides.list()) == 1
            image_path = app.guides.image_path(
                app.guides.list()[0]["steps"][0]["image"]
            )
            with Image.open(image_path) as saved:
                assert 149 <= saved.width <= 151 and 299 <= saved.height <= 301
            page.reload()
            page.get_by_role("button", name="Screenshot guides").click()
            page.get_by_role("button", name="My first guide").wait_for()
            page.get_by_role("button", name="Tutorial & privacy").click()
            page.get_by_role("heading", name="Your data and privacy").wait_for()
            page.get_by_role("button", name="Pause ocean").click()
            assert page.locator(".ocean.paused").count() == 1
            page.get_by_role("button", name="Resume ocean").click()
            page.emulate_media(reduced_motion="reduce")
            assert (
                page.locator(".swimmer").first.evaluate(
                    "node => getComputedStyle(node).animationName"
                )
                == "none"
            )
            assert page.title() == "DeskHELP"
            assert app.teloce.build_result["bundler"] == "minifyjs"
            assert any("deskhelp-" in url for url in javascript_requests)
            assert not any("/components/" in url for url in javascript_requests)
            assert not errors, errors
            browser.close()
    finally:
        server.should_exit = True
        worker.join(timeout=5)
        listener.close()
