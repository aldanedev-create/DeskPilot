# Validation record

## Completed locally

- Published PyPI `minifyjs==0.1.3` was installed and its version verified.
- Editable Flaxon and Teloce source checkouts were used.
- Eight automated tests passed; the opt-in Chromium test was skipped.
- Production Teloce build selected MinifyJS and emitted the application module.
- Generated production UI mounted and switched between all three workspaces in a DOM environment.
- A live Flaxon/production-UI smoke test passed folder connection, indexing,
  sorting preview, moves, undo and library display.
- Tests cover changed files, conflicting names, symbolic-link destinations,
  exact duplicates, interrupted move recovery, guide persistence and PDF output.
- Python lint/format checks passed. Workflow YAML and manifest XML parsed.

## Not yet validated

- Actual Windows WebView2 launch, file dialogs and Explorer integration.
- Real Chromium canvas annotation and browser regression test.
- PyInstaller executable, MakeAppx manifest validation and MSIX installation.
- Microsoft Store submission, signing, capability review and certification.

The Windows workflow includes Chromium validation before packaging, but this
source bundle has not been pushed to a new repository or run through that workflow.
Test against disposable folders before using it on important documents.
