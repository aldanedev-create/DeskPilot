# DeskHELP privacy policy

Effective October 6, 2026. Publisher: Happy Recorder 3D.

DeskHELP is a local desktop utility. It requires no account and includes no
advertising, analytics, tracking SDK or cloud storage. The app does not transmit
connected files, imported images or its database to the publisher.

## Information accessed and stored

Only folders you connect are indexed. DeskHELP stores file names, paths, tags,
expiry dates, sorting history, imported screenshots and screenshot guides.
Duplicate comparison reads file contents to calculate hashes. Sorting changes
file paths only after you review and confirm a preview. Duplicate results do
not cause automatic deletion. Exports are written where you choose.

The app keeps metadata, images and guides in a local SQLite database and files
under `%LOCALAPPDATA%/DeskPilot`, or the folder selected using `--data-dir`.
Windows may redirect the location for MSIX installations. Original files stay
in their own folders. Data is not encrypted by DeskHELP; Windows account and
filesystem permissions protect access. A loopback server serves the interface
on your computer with a random port and a per-session API token.

## Sharing and external services

DeskHELP does not upload user data. Opening support or privacy links uses your
browser and GitHub; GitHub's privacy terms apply there. Windows, WebView2 and
Microsoft Store may process their own diagnostic or installation information
under Microsoft's policies. You control sharing exported PDFs yourself.

## Control, retention and deletion

Data stays locally until you remove it. To delete app records, close DeskHELP,
back up anything needed, and delete its data folder. This erases library tags,
expiry dates, guides, imported images and undo history. It does not undo previous
moves or remove original files or exported PDFs. Back up originals separately.
Uninstall via Windows Settings → Apps. Do not assume uninstalling removes every
previous export or locally retained record.

## Contact and changes

For privacy questions, contact the publisher through
https://github.com/aldanedev-create/DeskPilot/issues. Do not include personal
files, screenshots or sensitive paths in public issues. This policy will be
updated when data handling changes.
