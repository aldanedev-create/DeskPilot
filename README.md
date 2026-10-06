# DeskHELP

**Organize your files. Find what matters. Create clear step-by-step guides.**

A local desktop workspace built with readable Python, Flaxon, Teloce components,
and published MinifyJS **0.1.3**. No account or cloud upload is required.

## First release

- **Organize:** connect folders, preview extension-based sorting, refuse overwrites,
  find exact duplicates, and undo completed moves without overwriting edited files.
- **Library:** index existing files, search names/paths/tags, save tags and expiry dates.
  Filter folders/types/expiry/favorites/size, search supported document text,
  edit notes, and page through results. Due-date reminders appear while open.
- **Guides:** import screenshots, draw boxes/arrows/text, reorder steps, save guides,
  crop/rotate/flip, adjust colors, erase annotations, undo/redo and export PDFs.
- **Desktop:** folder selection, show a document in Explorer, and PDF save dialog.

## Read the code

| File | Responsibility |
| --- | --- |
| `deskpilot/storage.py` | SQLite schema and transaction helpers |
| `deskpilot/files.py` | Folder boundaries, sorting, duplicates and undo |
| `deskpilot/guides.py` | Screenshot validation, guide persistence and PDF export |
| `deskpilot/app.py` | Flaxon API and session authorization |
| `deskpilot/ui/app.html` | Application shell and workspace navigation |
| `deskpilot/ui/components/` | Organize, library and guide components with scoped styles |
| `deskpilot/launcher.py` | Local server lifecycle and native desktop actions |
| `packaging/build_msix.ps1` | Freeze Python and validate/package MSIX |

Source code is formatted for people. Only generated production JavaScript is
minified. Teloce compiles components; MinifyJS optimizes the result. Flaxon serves
the local API and compiled interface. The desktop shell uses WebView2 on Windows.

## Develop with editable Flaxon and Teloce

Use Python 3.12. In PowerShell, from the DeskPilot project:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

git clone --branch fix/teloce-integration https://github.com/aldanedev-create/flaxon.git vendor/flaxon
git clone https://github.com/aldanedev-create/teloce-py.git vendor/teloce

python -m pip install minifyjs==0.1.3 pyyaml "tree-sitter>=0.25,<0.27" "tree-sitter-javascript>=0.23,<0.26" "tree-sitter-typescript>=0.23,<0.24" "uvicorn>=0.30,<1" "Pillow>=11,<13" "reportlab>=4,<5" "pypdf>=6,<7" "pywebview>=6,<7" "pytest>=8,<10"
python -m pip install -e vendor/teloce -e vendor/flaxon -e . --no-deps
python -m deskpilot.launcher --debug
```

Use Flaxon `main` after its integration fix is merged. Existing local checkouts
can replace the two clones. Editable installation means edits to those checkouts
are used directly. The explicit dependency installation and `--no-deps` support
unreleased source checkouts whose version metadata may lag Flaxon's declared
Teloce requirement; published packages must satisfy their normal constraints.

Default launch is **production mode**, even from editable sources:

```powershell
python -m deskpilot.launcher
```

For a browser preview on any OS:

```bash
python -m deskpilot.launcher --browser --data-dir ./local-data
```

Stop the browser preview with Ctrl+C. Native dialogs/Explorer actions are only
available in the desktop shell. Windows requires Microsoft Edge WebView2 Runtime.
No Node installation is needed to run or compile the application.

## Tests

```bash
python -m pytest -q
```

The default suite covers file operations, changed-file and collision protection,
symlink rejection, SQLite persistence, PDF generation and production integration.
A Chromium test is opt-in:

```powershell
python -m pip install playwright==1.58.0
python -m playwright install chromium
$env:DESKPILOT_BROWSER_TESTS = "1"
python -m pytest tests/test_browser.py -q
```

## GitHub Actions and MSIX

Create a repository and upload the contents of this project, including `.github`.
Run **Test and build Windows MSIX**. The workflow uses editable framework
checkouts and PyPI MinifyJS 0.1.3, runs tests/Chromium, and creates an artifact
containing the executable directory, MSIX, and dependency version record.

Set repository variables `MSIX_IDENTITY_NAME` and `MSIX_PUBLISHER` to the exact
identity and publisher provided by your Microsoft Partner Center application.
The defaults now use the supplied DeskHELP Store identity: `HappyRecorder3D.DeskHELP`, publisher `CN=50CA2AC2-0155-44AC-B2B0-47100A3FB6E2`, and publisher display name `Happy Recorder 3D`. Repository variables can override the first two values.

The MSIX is **unsigned**. Microsoft Store signs accepted submissions. To install
an MSIX directly for local testing, sign it with a certificate matching the
manifest publisher and trust that certificate. Alternatively run the unpackaged
`DeskPilot/DeskPilot.exe` artifact. No certificate or token is committed.

The manifest declares `runFullTrust` because this app reads and moves user files.
Review the capability and Store requirements before submission. A successful
package build alone does not establish Store approval or correct installation.

## Data and file behavior

Windows data lives in `%LOCALAPPDATA%/DeskPilot`; `--data-dir` overrides it.
Back up this whole folder for library metadata, screenshots and guides. Indexed
original files remain in their own folders and must be backed up separately.
The app binds only to loopback on a random port and requires a per-launch token
for API operations. This is a single-user desktop app, not a public server.

Sorting affects selected top-level files, grouped by type or modified month,
with extension and age filters. Destinations are reserved without overwriting,
using hard links where possible and exclusive verified copies otherwise. Original content is not intentionally
deleted: moving unlinks its old name after the new link exists. Duplicate
results are advisory and never deleted automatically. Hidden files and symlinks
are skipped; indexing stops at 50,000 files per folder and reports a warning. Missing records
retain metadata; disconnecting a folder removes its library records, not files.

## Current limits

This is a working first-release candidate, not a Store-certified release.
Windows native UI, installed MSIX behavior and the added Chromium test must be
validated on Windows before publishing. Local validation used editable Flaxon
and updated Teloce source plus the published MinifyJS 0.1.3 wheel.

Screenshot import and pointer annotations are implemented; OS screen capture,
OCR, background expiry notifications, encryption,
automatic filesystem watching and cloud sync are not included. Re-index to see
external changes. PDF text uses the standard Latin font; complex-script font
support needs a separate addition. Guide images persist locally, including
unused intermediate annotation images. Large folders may pause the UI while
hashing. Do not organize a folder another program is actively modifying.

Interrupted moves are journaled in SQLite. On restart, intact completed moves
are recovered into history and can be undone, including a crash between creating
the new hard link and removing the old one. Ambiguous changed files are retained
for manual review; DeskPilot never guesses which copy to remove. The
program refuses symlinks and verifies content but is not designed to defeat
malicious concurrent filesystem changes by another local process.

## MinifyJS measurement

With identical production settings and asset hashing disabled for comparison,
the nine emitted JavaScript files totaled **151,008 B** with minification off
and **114,330 B** with MinifyJS enabled: **24.29% smaller**. Summed per-file gzip
size fell from **35,875 B** to **29,599 B** (**17.49%**). This measures emitted
JavaScript, not the whole MSIX or embedded Python/native dependencies.

## Optimized production bundle

Production uses MinifyJS 0.1.3 bundling, tree shaking, compression, identifier
mangling and hashed entry naming. Flaxon imports the stable `ui/app.js` shim,
which re-exports the hashed bundle. Development remains unbundled and readable.
Code splitting is enabled, but the current static component imports emit one
bundle; this does not make components lazy-loaded automatically.

Comparable local JS measurements (hashing disabled for comparison):

| Mode | JS artifacts measured | JavaScript | Summed gzip |
| --- | ---: | ---: | ---: |
| Unminified generated modules | 9 | 151,008 B | 35,875 B |
| Minified separate modules | 9 | 114,330 B | 29,599 B |
| Optimized bundle | 1 | 76,290 B | 19,273 B |

The bundle is **49.48% smaller** than unminified modules and **33.27% smaller**
than the previous minified modules. Measurements exclude the small entry shim,
CSS and backend/native files. Teloce retains intermediate modules on disk; these
figures describe the bundle used by the browser, not the whole build directory
or MSIX package. Gzip is a comparison metric, not local transport compression.

## Store preparation

The user-facing name is DeskHELP; the repository, Python module and existing
data directory remain `DeskPilot` for compatibility. Read [Store submission](STORE_SUBMISSION.md)
and [Privacy](PRIVACY.md). The ocean loops while the app is open, pauses when
the page is hidden and respects reduced motion. It is decorative, not a service
running when the app is closed.

If the downloaded Windows ZIP reports a Python.Runtime loader error, unblock
the trusted GitHub ZIP in Properties before extracting it into a new folder.
Do not disable Windows security.

## DeskHELP 0.2 tools

Image editing uses a separate annotation layer. Eraser removes new annotations,
not the imported screenshot. Undo/redo, ellipse, freehand pen, highlighter, solid
redaction, text size/color, crop, rotation, horizontal flip and brightness/contrast/
saturation and PNG export are available. Save guide automatically keeps active edits; switching
images asks before discarding edits. Images are fitted to 4 megapixels for editing,
with at most 60 undoable actions before keeping. Originals remain in local app
data even after redaction; exported PNG-in-PDF contains flattened edits.

Library search combines all words, with quoted phrases, across names, paths,
tags, notes and extracted text. Text extraction handles UTF-8 text, DOCX and
text-based PDFs (first 30 pages), up to 10 MB and 100,000 characters. It skips
encrypted/scanned PDFs and unsupported formats. Results paginate at 50 records.
Refreshing reads connected folders again; external unique file renames preserve
metadata when the filesystem reports stable identities. Missing files keep their
records. There is no OCR or background filesystem watcher.

Undo preflights the full batch before moving files. Moves and undo are journaled
for crash recovery, with ambiguous cases retained for manual review. Copy fallback
retains the original until copied contents verify. Unexpected mid-batch filesystem
failures can still leave completed moves in history; these can be undone.
