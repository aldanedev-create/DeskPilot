param(
    [string]$IdentityName = "HappyRecorder3D.DeskHELP",
    [string]$Publisher = "CN=50CA2AC2-0155-44AC-B2B0-47100A3FB6E2",
    [string]$Version = "0.1.0.0"
)
$ErrorActionPreference = "Stop"
python packaging/create_icons.py
if ($LASTEXITCODE -ne 0) { throw "Icon generation failed" }
python -m PyInstaller --clean --noconfirm --noconsole --onedir --name DeskPilot `
    --collect-all flaxon --collect-all teloce --collect-all minifyjs `
    --collect-all webview --collect-all tree_sitter --collect-all tree_sitter_javascript `
    --collect-all tree_sitter_typescript --collect-all PIL --collect-all reportlab `
    --add-data "deskpilot/ui;deskpilot/ui" run_desktop.py
if ($LASTEXITCODE -ne 0) { throw "Executable build failed" }
$stage = "build/msix-stage"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force $stage | Out-Null
Copy-Item dist/DeskPilot "$stage/DeskPilot" -Recurse -Force
Copy-Item packaging/Assets "$stage/Assets" -Recurse -Force
[xml]$manifest = Get-Content packaging/AppxManifest.xml
$manifest.Package.Identity.Name = $IdentityName
$manifest.Package.Identity.Publisher = $Publisher
$manifest.Package.Identity.Version = $Version
$manifest.Save((Join-Path (Resolve-Path $stage) "AppxManifest.xml"))
$makeappx = Get-ChildItem "${env:ProgramFiles(x86)}/Windows Kits/10/bin/*/x64/makeappx.exe" | Sort-Object FullName -Descending | Select-Object -First 1
if (-not $makeappx) { throw "Install the Windows SDK to get MakeAppx.exe" }
& $makeappx.FullName pack /d $stage /p dist/DeskPilot.msix /o
if ($LASTEXITCODE -ne 0) { throw "MSIX validation or packaging failed" }
Write-Host "Created dist/DeskPilot.msix. Set Partner Center identity before Store submission."
