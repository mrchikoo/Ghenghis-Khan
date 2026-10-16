# Ghenghis Khan

A fully local PDF & document toolkit for macOS.

## What it does

- **To PDF** — Word, Excel, PowerPoint, ODF, text, HTML, images → PDF
- **From PDF** — PDF → Word (.docx), plain text, or one image per page
- **Merge** — Combine any number of PDFs, drag to reorder
- **Remove pages** — Delete pages by range (e.g. `1,3,5-8`)
- **Insert** — Splice one PDF into another after any page
- **Compress** — Ghostscript-based, four quality tiers, keeps text sharp

Nothing leaves your Mac. No accounts, no upload, no telemetry.

## Install (one time)

```bash
./install.sh
```

This installs (via Homebrew, if you don't already have them):

| Tool | Why |
| --- | --- |
| Python 3 | The app itself |
| LibreOffice | Office document ↔ PDF conversion (headless) |
| Ghostscript | PDF compression, PDF → images |
| PyQt6, pypdf, pdf2docx, Pillow | Python packages, in a local `.venv` |

## Launch

```bash
./run.sh
```

Drag files onto any panel. Sidebar picks the operation.

## Notes

- **PDF → Word** uses `pdf2docx`. It handles most straightforward layouts well; heavily-designed pages may need touch-ups after conversion — that's a limitation of the format, not the tool.
- **Compression** offers four Ghostscript presets. *eBook* is the sweet spot for most PDFs.
- If a required tool is missing the sidebar footer tells you which one; the rest of the app keeps working.
