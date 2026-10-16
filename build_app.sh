#!/usr/bin/env bash
# Build "Ghenghis Khan.app" — a self-contained macOS application bundle.
# Bundles Python + all Python packages + icon inside the .app.
# System tools (LibreOffice, Ghostscript) are installed separately via install.sh.
set -e

cd "$(dirname "$0")"
BUILD_DIR="$(pwd)"
APP_NAME="Ghenghis Khan"
APP="${BUILD_DIR}/${APP_NAME}.app"

echo "──────────────────────────────────────"
echo "  Building ${APP_NAME}.app"
echo "──────────────────────────────────────"

# Find a Python ≥3.10
PYTHON=""
for cand in python3.12 python3.11 python3.13 python3.10 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    PYTHON="$(command -v "$cand")"
    break
  fi
done
if [ -z "$PYTHON" ]; then
  echo "✗ Python 3 not found. Install with:  brew install python@3.12"
  exit 1
fi
echo "▶ Using ${PYTHON}"

# ── Fresh bundle skeleton ─────────────────────────────────
echo "▶ Creating bundle skeleton…"
rm -rf "${APP}"
mkdir -p "${APP}/Contents/MacOS"
mkdir -p "${APP}/Contents/Resources"

# ── Internal venv with all Python deps ────────────────────
echo "▶ Creating internal virtual-env…"
VENV="${APP}/Contents/Resources/venv"
"${PYTHON}" -m venv "${VENV}"
"${VENV}/bin/pip" install --upgrade pip >/dev/null
echo "▶ Installing Python packages (this takes a minute)…"
"${VENV}/bin/pip" install -r requirements.txt

# ── App source ────────────────────────────────────────────
cp ghenghis_khan.py "${APP}/Contents/Resources/"

# ── Icon ──────────────────────────────────────────────────
echo "▶ Generating icon…"
"${VENV}/bin/python" make_icon.py
mv AppIcon.icns "${APP}/Contents/Resources/AppIcon.icns"

# ── Launcher shim ─────────────────────────────────────────
cat > "${APP}/Contents/MacOS/GhenghisKhan" <<'LAUNCHER'
#!/usr/bin/env bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../Resources" && pwd )"
exec "${DIR}/venv/bin/python" "${DIR}/ghenghis_khan.py" "$@"
LAUNCHER
chmod +x "${APP}/Contents/MacOS/GhenghisKhan"

# ── Info.plist ────────────────────────────────────────────
cat > "${APP}/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>                 <string>Ghenghis Khan</string>
    <key>CFBundleDisplayName</key>          <string>Ghenghis Khan</string>
    <key>CFBundleExecutable</key>           <string>GhenghisKhan</string>
    <key>CFBundleIdentifier</key>           <string>com.local.ghenghiskhan</string>
    <key>CFBundleVersion</key>              <string>1.0</string>
    <key>CFBundleShortVersionString</key>   <string>1.0</string>
    <key>CFBundlePackageType</key>          <string>APPL</string>
    <key>CFBundleIconFile</key>             <string>AppIcon</string>
    <key>LSMinimumSystemVersion</key>       <string>11.0</string>
    <key>NSHighResolutionCapable</key>      <true/>
    <key>NSRequiresAquaSystemAppearance</key> <false/>
    <key>LSApplicationCategoryType</key>    <string>public.app-category.productivity</string>
</dict>
</plist>
PLIST

# ── De-quarantine so Gatekeeper is quiet ──────────────────
xattr -dr com.apple.quarantine "${APP}" 2>/dev/null || true

SIZE=$(du -sh "${APP}" | cut -f1)
echo ""
echo "──────────────────────────────────────"
echo "  ✓ Built: ${APP}   (${SIZE})"
echo ""
echo "  ▸ Double-click to launch, or drag into /Applications."
echo "  ▸ For Office (Word/Excel/PPT) conversion & PDF compression,"
echo "    run:   ./install.sh    (installs LibreOffice + Ghostscript)"
echo "──────────────────────────────────────"
