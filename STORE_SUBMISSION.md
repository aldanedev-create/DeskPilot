# DeskHELP Store submission

## Identity

- Reserved display name: DeskHELP (also window title, HTML title and app branding).
- Package name: HappyRecorder3D.DeskHELP
- Publisher: CN=50CA2AC2-0155-44AC-B2B0-47100A3FB6E2
- Publisher display name: Happy Recorder 3D
- Internal repository/module/executable: DeskPilot (compatibility; not Store branding).

## Listing draft

DeskHELP requires Microsoft Edge WebView2 Runtime. It helps you organize local
files, find documents and create screenshot guides on Windows 10 (build 19041)
or later, on x64 devices. No account or cloud upload is required.

Preview file sorting before moving anything, detect identical files without
automatic deletion, and undo unchanged moves. Search connected folders by words or phrases in names,
paths, tags, notes and supported text, with folder/type/expiry/size/favorite filters.
Import screenshots, erase annotations, crop/rotate/flip, adjust colors and export PDF guides. A looping ocean with fish offers a calm
visual accent, with pause and reduced-motion support.

Sorting supports hard links or verified exclusive copies. Indexing stops at
50,000 files per folder with a warning.
DeskHELP does not capture screens, perform OCR, encrypt documents, or provide
background reminders. Text search covers bounded UTF-8, DOCX and text-based PDF
content; scanned PDFs need OCR. Image editing is capped at 4 megapixels. PDF text currently supports standard Latin characters.

Suggested category: Productivity. Use real screenshots of this release, not
mockups. Complete the age-rating questionnaire accurately in Partner Center.
Privacy URL: https://github.com/aldanedev-create/DeskPilot/blob/main/PRIVACY.md
Support URL: https://github.com/aldanedev-create/DeskPilot/issues

## Certification notes draft

No login, remote server or payment is required. The local backend starts with
the app. The runFullTrust capability supports the Python desktop shell, local
SQLite/files, user-selected folders, explicit file moves/undo, Explorer reveal,
and PDF export. No elevated privileges, Windows setting changes, background
service or startup registration are required by the application.

Create a small folder with two identical .txt files. Connect it in Organize,
find duplicates, preview sorting, confirm moves, and undo. Open Document library,
search and save tags/expiry. Import a PNG into Screenshot guides, add a title,
annotate and save/export. Open Tutorial & privacy; pause/resume the ocean.

## Release gates before submission

1. Check the successful Actions artifact matches this commit and exact identity.
2. The build must pass frozen WinForms/WebView2 startup, source tests and Chromium.
3. Sign a local test copy with a trusted matching certificate; install as a normal
   user on clean Windows, launch from Start, exercise native dialogs, save/reopen,
   test keyboard navigation, resize, reduced motion and uninstall.
4. Run Windows App Certification Kit against the installed package and review
   its report. Native CI startup does not replace installed-MSIX testing.
5. Verify WebView2 availability on supported Windows; disclose the dependency.
6. Review dependency licenses and redistribute required notices for every bundled
   dependency. Do not submit until this and clean-machine tests are complete.
7. Upload the original unsigned Store artifact, not your local test-signed copy.
   Complete listing, real screenshots, privacy URL, ratings and capability notes.

Policy references: https://learn.microsoft.com/en-us/windows/apps/publish/store-policies
https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/app-capability-declarations
The published 7.20 policy page is effective October 22, 2026; check the applicable
version at actual submission. These preparations do not guarantee acceptance.
