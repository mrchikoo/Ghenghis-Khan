<div align="center">

# Ghenghis Khan

**A fully local PDF & document toolkit for macOS.**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/UI-PyQt6-41CD52?logo=qt&logoColor=white)
![Platform](https://img.shields.io/badge/platform-macOS-lightgrey?logo=apple)

</div>

## Overview

Ghenghis Khan is a desktop app that converts, merges, edits and compresses PDFs without sending anything off your machine. No accounts, no uploads, no telemetry.

## Features

- **To PDF**: Word, Excel, PowerPoint, ODF, RTF, text, CSV, HTML and images (PNG, JPEG, TIFF, BMP, GIF) to PDF
- **From PDF**: PDF to Word (.docx), plain text, or one PNG/JPEG image per page
- **Merge**: combine any number of PDFs, drag to reorder
- **Remove pages**: delete pages by range (e.g. `1,3,5-8`)
- **Insert**: splice one PDF into another after any page
- **Compress**: Ghostscript-based, four quality tiers (Screen, eBook, Printer, Prepress); eBook is the recommended default
- Drag-and-drop on every panel; operations run on a background worker so the UI stays responsive
- If a required tool is missing, the sidebar footer says which one and the rest of the app keeps working

## Tech stack

| Component | Used for |
| --- | --- |
| Python 3 + PyQt6 | The app and its UI |
| pypdf | Merge, remove pages, insert |
| pdf2docx | PDF to Word |
| Pillow | Image handling and icon generation |
| LibreOffice (headless) | Office/ODF/HTML to PDF conversion |
| Ghostscript | Compression and PDF to image |

## Install

Requires macOS and [Homebrew](https://brew.sh) (the installer will install Homebrew if it is missing).

```bash
./install.sh
```

This installs Python 3, LibreOffice and Ghostscript via Homebrew (only if not already present) and creates a local `.venv` with the packages from `requirements.txt` (`PyQt6`, `pypdf`, `pdf2docx`, `Pillow`).

## Run

```bash
./run.sh
```

Drag files onto any panel and pick the operation from the sidebar.

### Build a standalone .app (optional)

```bash
./build_app.sh
```

Creates `Ghenghis Khan.app` with its own bundled Python environment and a generated icon. LibreOffice and Ghostscript are still installed separately with `./install.sh`. The `.app` is git-ignored.

## Project structure

```
.
├── ghenghis_khan.py   # the whole app (conversion helpers, worker, UI pages)
├── make_icon.py       # generates AppIcon.icns for the bundle
├── install.sh         # Homebrew deps + local .venv
├── run.sh             # launch from source
├── build_app.sh       # build "Ghenghis Khan.app"
└── requirements.txt
```

## Notes

- PDF to Word uses `pdf2docx`. It handles straightforward layouts well; heavily designed pages may need touch-ups afterwards.
- Compression and Office conversion need Ghostscript and LibreOffice respectively; everything else works without them.
- No license file is included in the repository.
