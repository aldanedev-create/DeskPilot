"""Validate screenshot uploads and export readable, paginated PDF guides."""

import base64
import json
import uuid
from io import BytesIO

from PIL import Image, ImageOps
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


class Guides:
    def __init__(self, store):
        self.store = store
        self.images = store.directory / "images"
        self.exports = store.directory / "exports"
        self.images.mkdir(exist_ok=True)
        self.exports.mkdir(exist_ok=True)

    def import_image(self, data_url):
        if not isinstance(data_url, str) or len(data_url) > 24_000_000:
            raise ValueError("Image data exceeds the 18 MB storage limit")
        try:
            data = base64.b64decode(data_url.split(",", 1)[1], validate=True)
            with Image.open(BytesIO(data)) as image:
                if image.format not in {"PNG", "JPEG", "WEBP"}:
                    raise ValueError("Unsupported screenshot format")
                if image.width * image.height > 20_000_000:
                    raise ValueError("Screenshot exceeds 20 megapixels")
                image.load()
                identifier = uuid.uuid4().hex
                ImageOps.exif_transpose(image).convert("RGB").save(
                    self.images / f"{identifier}.png"
                )
        except (IndexError, OSError, ValueError) as error:
            raise ValueError("Choose a valid PNG, JPEG or WebP screenshot") from error
        return {"image": identifier}

    def image_path(self, identifier):
        if len(identifier) != 32 or any(
            character not in "0123456789abcdef" for character in identifier
        ):
            raise ValueError("Invalid image identifier")
        path = self.images / f"{identifier}.png"
        if not path.is_file():
            raise ValueError("Screenshot no longer exists")
        return path

    def save(self, payload):
        title = str(payload.get("title", "")).strip()
        steps = payload.get("steps", [])
        if (
            not title
            or len(title) > 150
            or not isinstance(steps, list)
            or not 1 <= len(steps) <= 30
        ):
            raise ValueError("Give the guide a title and 1–30 steps")
        cleaned = []
        for step in steps:
            self.image_path(step["image"])
            cleaned.append(
                {
                    "image": step["image"],
                    "title": str(step.get("title", ""))[:150],
                    "description": str(step.get("description", ""))[:2000],
                }
            )
        with self.store.connect() as connection:
            identifier = payload.get("id")
            if identifier:
                cursor = connection.execute(
                    "UPDATE guides SET title=?,steps=? WHERE id=?",
                    (title, json.dumps(cleaned), identifier),
                )
                if cursor.rowcount != 1:
                    raise ValueError("Guide not found")
            else:
                identifier = connection.execute(
                    "INSERT INTO guides(title,steps) VALUES (?,?)",
                    (title, json.dumps(cleaned)),
                ).lastrowid
        return {"id": identifier, "title": title, "steps": cleaned}

    def list(self):
        rows = self.store.rows("SELECT * FROM guides ORDER BY id DESC")
        for row in rows:
            row["steps"] = json.loads(row["steps"])
        return rows

    def export(self, identifier):
        rows = self.store.rows("SELECT * FROM guides WHERE id=?", (identifier,))
        if not rows:
            raise ValueError("Guide not found")
        guide = rows[0]
        output = self.exports / f"guide-{int(identifier)}.pdf"
        pdf = canvas.Canvas(str(output), pagesize=(595, 842))
        pdf.setTitle(guide["title"])
        for number, step in enumerate(json.loads(guide["steps"]), 1):
            pdf.setFont("Helvetica-Bold", 16)
            pdf.drawString(40, 795, guide["title"][:65])
            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(40, 763, f"{number}. {step['title']}"[:80])
            reader = ImageReader(str(self.image_path(step["image"])))
            width, height = reader.getSize()
            scale = min(515 / width, 500 / height)
            pdf.drawImage(
                reader,
                40,
                735 - height * scale,
                width=width * scale,
                height=height * scale,
            )
            text = pdf.beginText(40, 210)
            text.setFont("Helvetica", 10)
            import textwrap

            lines = []
            for paragraph in step["description"].splitlines():
                lines.extend(textwrap.wrap(paragraph, width=95) or [""])
            for index, line in enumerate(lines):
                if index and index % 12 == 0:
                    pdf.drawText(text)
                    pdf.showPage()
                    text = pdf.beginText(40, 790)
                    text.setFont("Helvetica", 10)
                text.textLine(line)
            pdf.drawText(text)
            pdf.showPage()
        pdf.save()
        return output
