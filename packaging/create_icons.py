"""Create simple, reproducible DeskPilot package icons."""

from pathlib import Path

from PIL import Image, ImageDraw

output = Path(__file__).parent / "Assets"
output.mkdir(exist_ok=True)
for name, size in [
    ("StoreLogo", 50),
    ("Square44x44Logo", 44),
    ("Square150x150Logo", 150),
]:
    image = Image.new("RGB", (size, size), "#265b48")
    draw = ImageDraw.Draw(image)
    # A folder outline: vector-like geometry rendered at the requested tile size.
    draw.rounded_rectangle(
        (size * 0.17, size * 0.30, size * 0.83, size * 0.76),
        radius=size * 0.05,
        outline="#edf1e9",
        width=max(2, int(size * 0.045)),
    )
    draw.line(
        (
            size * 0.17,
            size * 0.3,
            size * 0.17,
            size * 0.22,
            size * 0.43,
            size * 0.22,
            size * 0.51,
            size * 0.3,
        ),
        fill="#edf1e9",
        width=max(2, int(size * 0.045)),
    )
    image.save(output / f"{name}.png")
