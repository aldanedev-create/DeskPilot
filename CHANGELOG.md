# Changelog

## 1.0.0 — First Microsoft Store release preparation

- Set the app version to 1.0.0 and MSIX identity version to 1.0.0.0.
- Keep the fourth MSIX version component at zero for Store submissions.

## 0.1.0 — first-release candidate

- Added local folder indexing, sorting previews, exact duplicate groups and undo.
- Added document search, tags and in-app expiry reminders.
- Added screenshot guides, annotations, step ordering, persistence and PDF export.
- Added Flaxon/Teloce production integration with PyPI MinifyJS 0.1.3.
- Added Windows desktop launcher and GitHub Actions MSIX workflow.
- Added file-operation, persistence and production integration tests, plus opt-in Chromium checks.

- Split the UI into workspace components with scoped styles, retaining unsaved guide state between tabs.

- Enabled MinifyJS optimized production bundling, hashed entry and tree shaking; development stays unbundled.

## Unreleased — DeskHELP Store preparation

- Match window, page and interface branding to reserved DeskHELP name.
- Add a short tutorial, local data/privacy information and support links.
- Add a continuous ocean scene with fish, kelp, waves and bubbles; pause,
  reduced-motion and hidden-page suspension keep it controllable.
- Gate MSIX packaging on frozen WinForms/WebView2 startup and UI mount.
- Add privacy policy, listing draft and certification instructions.

## 0.2.0 — Workspace improvements

- Image editing: eraser, pen, highlighter, ellipse, solid redaction, colors, sizes,
  crop, rotate, flip, brightness/contrast/saturation, PNG export and undo/redo.
- Save guide keeps active image edits; duplicate steps and protect unkept edits.
- Library: word/phrase text search, notes, favorites, type/folder/expiry/size
  filters, sorting, pagination, snippets, original-file opening and refresh.
- Preserve metadata for missing files and unambiguous external renames; index
  up to 50,000 files and report skipped/incomplete scans.
- Organize by modified month or file type, filter age/extension, select moves,
  skip conflicts and disconnect folders without changing original files.
- Preflight the complete undo batch, journal interrupted undo, bound preview
  lifetimes, reject overlapping roots and support exclusive verified copy fallback.
- Run indexing/file work off the event loop; use SQLite WAL and preserve EXIF orientation.

- Keep app/window references private in the native JavaScript bridge to prevent
  recursive object traversal and unintended exposure of backend objects.
