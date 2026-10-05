"""Fail packaging if the pinned native optimizer is unavailable or not selected."""

from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

from minifyjs import minify
from deskpilot.app import create_app

assert version("minifyjs") == "0.1.3", "Install the published minifyjs==0.1.3 wheel"
source = "export function answer() { const value = 20 + 22; return value; }"
result = minify(source, compress=True, mangle=True, format="esm")
assert result.code and len(result.code) < len(source), (
    "Native optimizer smoke check failed"
)
with TemporaryDirectory() as directory:
    app = create_app(Path(directory) / "data", debug=False)
    build = app.teloce.build()
    assert not build["failed"], build["errors"]
    assert build["minifier"] == "minifyjs", "Production must use MinifyJS"
    assert build["minifyjs_version"] == "0.1.3"
    assert (app.teloce.build_dir / "ui/app.js").is_file()
    print(
        "Verified: published MinifyJS 0.1.3, native optimization, production Teloce backend"
    )
