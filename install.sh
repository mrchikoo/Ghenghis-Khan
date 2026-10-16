#!/usr/bin/env bash
# Ghenghis Khan installer — sets up everything locally on macOS.
set -e

cd "$(dirname "$0")"

echo "──────────────────────────────────────"
echo "  Ghenghis Khan — install"
echo "──────────────────────────────────────"

# 1. Homebrew
if ! command -v brew >/dev/null 2>&1; then
  echo "▶ Homebrew not found. Installing…"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# 2. Python 3
if ! command -v python3 >/dev/null 2>&1; then
  echo "▶ Installing Python 3…"
  brew install python@3.12
fi

# 3. LibreOffice — for Word / Excel / PPT ↔ PDF
if [ ! -x "/Applications/LibreOffice.app/Contents/MacOS/soffice" ] && ! command -v soffice >/dev/null 2>&1; then
  echo "▶ Installing LibreOffice (needed for Office conversions)…"
  brew install --cask libreoffice
else
  echo "✓ LibreOffice already installed."
fi

# 4. Ghostscript — for compression + PDF→image
if ! command -v gs >/dev/null 2>&1; then
  echo "▶ Installing Ghostscript (needed for compression)…"
  brew install ghostscript
else
  echo "✓ Ghostscript already installed."
fi

# 5. Python virtual-env + deps
if [ ! -d ".venv" ]; then
  echo "▶ Creating Python virtual environment…"
  python3 -m venv .venv
fi

echo "▶ Installing Python packages…"
./.venv/bin/pip install --upgrade pip >/dev/null
./.venv/bin/pip install -r requirements.txt

echo ""
echo "──────────────────────────────────────"
echo "  ✓ Done. Launch with:  ./run.sh"
echo "──────────────────────────────────────"
