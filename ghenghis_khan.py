#!/usr/bin/env python3
"""Ghenghis Khan — local PDF & document toolkit for macOS."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable

from PyQt6.QtCore import (
    QMimeData,
    QObject,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QIcon,
    QPainter,
    QPalette,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from pypdf import PdfReader, PdfWriter


APP_NAME = "Ghenghis Khan"

OFFICE_INPUT_EXTS = {
    ".doc", ".docx", ".odt", ".rtf", ".txt",
    ".xls", ".xlsx", ".ods", ".csv",
    ".ppt", ".pptx", ".odp",
    ".html", ".htm",
}
IMAGE_INPUT_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif"}
CONVERTIBLE_TO_PDF = OFFICE_INPUT_EXTS | IMAGE_INPUT_EXTS

PDF_OUT_FORMATS = {
    "Word (.docx)": "docx",
    "Plain text (.txt)": "txt",
    "PNG images (one per page)": "png",
    "JPEG images (one per page)": "jpg",
}


# ─────────────────────────────────────────────────────────────
# External tool discovery
# ─────────────────────────────────────────────────────────────

def find_soffice() -> str | None:
    candidates = [
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        shutil.which("soffice"),
        shutil.which("libreoffice"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def find_ghostscript() -> str | None:
    for name in ("gs", "gs-noX11"):
        p = shutil.which(name)
        if p:
            return p
    for path in ("/opt/homebrew/bin/gs", "/usr/local/bin/gs"):
        if Path(path).exists():
            return path
    return None


# ─────────────────────────────────────────────────────────────
# Conversion / manipulation primitives
# ─────────────────────────────────────────────────────────────

class ToolError(RuntimeError):
    pass


def _run(cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except FileNotFoundError as e:
        raise ToolError(f"Missing binary: {cmd[0]}") from e


def convert_to_pdf(src: Path, out_dir: Path) -> Path:
    """Convert any supported file into a PDF, written into out_dir."""
    ext = src.suffix.lower()
    out_dir.mkdir(parents=True, exist_ok=True)

    if ext == ".pdf":
        dest = out_dir / src.name
        if dest.resolve() != src.resolve():
            shutil.copy2(src, dest)
        return dest

    if ext in IMAGE_INPUT_EXTS:
        from PIL import Image
        img = Image.open(src)
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")
        dest = out_dir / f"{src.stem}.pdf"
        img.save(dest, "PDF", resolution=200.0)
        return dest

    if ext in OFFICE_INPUT_EXTS:
        soffice = find_soffice()
        if not soffice:
            raise ToolError(
                "LibreOffice is required for Office document conversion.\n"
                "Install it with:  brew install --cask libreoffice"
            )
        with tempfile.TemporaryDirectory() as tmp:
            proc = _run([
                soffice, "--headless", "--norestore", "--nologo",
                "--convert-to", "pdf", "--outdir", tmp, str(src),
            ], timeout=600)
            if proc.returncode != 0:
                raise ToolError(
                    f"LibreOffice failed on {src.name}:\n{proc.stderr or proc.stdout}"
                )
            produced = next(Path(tmp).glob("*.pdf"), None)
            if not produced:
                raise ToolError(f"LibreOffice produced no PDF for {src.name}")
            dest = out_dir / f"{src.stem}.pdf"
            shutil.move(str(produced), dest)
            return dest

    raise ToolError(f"Unsupported input format: {ext}")


def convert_from_pdf(src: Path, out_path: Path, target_fmt: str) -> Path:
    """PDF → docx / txt / png / jpg. Returns the primary output path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if target_fmt == "docx":
        try:
            from pdf2docx import Converter
        except ImportError as e:
            raise ToolError("pdf2docx not installed. Run install.sh.") from e
        cv = Converter(str(src))
        try:
            cv.convert(str(out_path))
        finally:
            cv.close()
        return out_path

    if target_fmt == "txt":
        reader = PdfReader(str(src))
        pieces = []
        for page in reader.pages:
            pieces.append(page.extract_text() or "")
        out_path.write_text("\n\n".join(pieces), encoding="utf-8")
        return out_path

    if target_fmt in ("png", "jpg"):
        gs = find_ghostscript()
        if not gs:
            raise ToolError(
                "Ghostscript is required for PDF → image.\n"
                "Install it with:  brew install ghostscript"
            )
        stem = out_path.with_suffix("")
        device = "png16m" if target_fmt == "png" else "jpeg"
        pattern = f"{stem}-%03d.{target_fmt}"
        proc = _run([
            gs, "-dNOPAUSE", "-dBATCH", "-dSAFER", "-dQUIET",
            f"-sDEVICE={device}", "-r200",
            f"-sOutputFile={pattern}", str(src),
        ], timeout=600)
        if proc.returncode != 0:
            raise ToolError(proc.stderr or proc.stdout or "Ghostscript failed")
        return Path(pattern.replace("%03d", "001"))

    raise ToolError(f"Unknown output format: {target_fmt}")


def merge_pdfs(sources: Iterable[Path], dest: Path) -> Path:
    writer = PdfWriter()
    for src in sources:
        reader = PdfReader(str(src))
        for page in reader.pages:
            writer.add_page(page)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        writer.write(f)
    return dest


def remove_pages(src: Path, pages_1based: set[int], dest: Path) -> Path:
    reader = PdfReader(str(src))
    writer = PdfWriter()
    for idx, page in enumerate(reader.pages, start=1):
        if idx not in pages_1based:
            writer.add_page(page)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        writer.write(f)
    return dest


def insert_pdf(base: Path, insert: Path, after_page_1based: int, dest: Path) -> Path:
    base_reader = PdfReader(str(base))
    ins_reader = PdfReader(str(insert))
    writer = PdfWriter()
    after = max(0, min(after_page_1based, len(base_reader.pages)))
    for i in range(after):
        writer.add_page(base_reader.pages[i])
    for p in ins_reader.pages:
        writer.add_page(p)
    for i in range(after, len(base_reader.pages)):
        writer.add_page(base_reader.pages[i])
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        writer.write(f)
    return dest


def compress_pdf(src: Path, dest: Path, quality: str) -> Path:
    """quality in {screen, ebook, printer, prepress} — ebook is a good default."""
    gs = find_ghostscript()
    if not gs:
        raise ToolError(
            "Ghostscript is required for compression.\n"
            "Install it with:  brew install ghostscript"
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = _run([
        gs, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.5",
        f"-dPDFSETTINGS=/{quality}",
        "-dNOPAUSE", "-dQUIET", "-dBATCH",
        f"-sOutputFile={dest}", str(src),
    ], timeout=600)
    if proc.returncode != 0:
        raise ToolError(proc.stderr or proc.stdout or "Ghostscript failed")
    return dest


# ─────────────────────────────────────────────────────────────
# Async worker
# ─────────────────────────────────────────────────────────────

class WorkerSignals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            self.signals.error.emit(str(e))
            return
        self.signals.finished.emit(result)


# ─────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────

STYLE = """
* { font-family: 'SF Pro Text', 'Helvetica Neue', Helvetica, Arial; }
QMainWindow, QWidget { background-color: #1c1c1e; color: #f2f2f7; }
QFrame#sidebar { background-color: #141416; border-right: 1px solid #2c2c2e; }
QPushButton#navBtn {
    background: transparent; color: #d1d1d6; border: none;
    padding: 10px 16px; text-align: left; font-size: 13px; border-radius: 8px;
}
QPushButton#navBtn:hover { background: #26262a; color: #ffffff; }
QPushButton#navBtn:checked { background: #b8322a; color: #ffffff; font-weight: 600; }
QLabel#title { font-size: 22px; font-weight: 700; color: #ffffff; }
QLabel#sub { color: #98989d; font-size: 12px; }
QLabel#brand { color: #ffffff; font-size: 15px; font-weight: 700; padding: 14px 16px 4px; }
QLabel#brandSub { color: #98989d; font-size: 11px; padding: 0 16px 12px; }
QFrame#dropZone {
    border: 2px dashed #48484a; border-radius: 12px;
    background-color: #242427; min-height: 130px;
}
QFrame#dropZone[dragActive="true"] { border-color: #b8322a; background-color: #2a1f1e; }
QLabel#dropText { color: #98989d; font-size: 13px; }
QPushButton {
    background-color: #b8322a; color: white; border: none;
    padding: 9px 18px; border-radius: 8px; font-size: 13px; font-weight: 600;
}
QPushButton:hover { background-color: #c93a31; }
QPushButton:disabled { background-color: #3a3a3d; color: #6a6a6d; }
QPushButton#secondary { background-color: #2c2c2e; color: #f2f2f7; }
QPushButton#secondary:hover { background-color: #3a3a3d; }
QListWidget {
    background-color: #242427; border: 1px solid #2c2c2e;
    border-radius: 8px; padding: 4px; color: #f2f2f7;
}
QListWidget::item { padding: 8px; border-radius: 6px; }
QListWidget::item:selected { background-color: #b8322a; color: white; }
QComboBox, QSpinBox {
    background-color: #242427; border: 1px solid #3a3a3d;
    border-radius: 6px; padding: 6px 10px; color: #f2f2f7;
}
QComboBox:hover, QSpinBox:hover { border-color: #b8322a; }
QComboBox QAbstractItemView {
    background-color: #242427; color: #f2f2f7;
    selection-background-color: #b8322a;
}
QProgressBar {
    background-color: #242427; border: none; border-radius: 4px;
    height: 6px; text-align: center;
}
QProgressBar::chunk { background-color: #b8322a; border-radius: 4px; }
QStatusBar { background-color: #141416; color: #98989d; border-top: 1px solid #2c2c2e; }
"""


class DropZone(QFrame):
    filesDropped = pyqtSignal(list)

    def __init__(self, hint: str, accept_exts: set[str] | None = None):
        super().__init__()
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.accept_exts = accept_exts
        self.setProperty("dragActive", False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("⬇")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 28px; color: #b8322a;")
        layout.addWidget(icon)

        self.hint = QLabel(hint)
        self.hint.setObjectName("dropText")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

    def _accepts(self, mime: QMimeData) -> bool:
        if not mime.hasUrls():
            return False
        if not self.accept_exts:
            return True
        for url in mime.urls():
            if Path(url.toLocalFile()).suffix.lower() in self.accept_exts:
                return True
        return False

    def dragEnterEvent(self, e: QDragEnterEvent):
        if self._accepts(e.mimeData()):
            e.acceptProposedAction()
            self.setProperty("dragActive", True)
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, e):
        self.setProperty("dragActive", False)
        self.style().unpolish(self); self.style().polish(self)

    def dropEvent(self, e: QDropEvent):
        paths = []
        for url in e.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.exists() and (not self.accept_exts or p.suffix.lower() in self.accept_exts):
                paths.append(p)
        self.setProperty("dragActive", False)
        self.style().unpolish(self); self.style().polish(self)
        if paths:
            self.filesDropped.emit(paths)


class Section(QWidget):
    """Base widget: title + subtitle at top."""
    def __init__(self, title: str, subtitle: str):
        super().__init__()
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(28, 24, 28, 24)
        self.root.setSpacing(14)

        t = QLabel(title); t.setObjectName("title")
        s = QLabel(subtitle); s.setObjectName("sub")
        self.root.addWidget(t)
        self.root.addWidget(s)


# ── Individual pages ────────────────────────────────────────

class ToPdfPage(Section):
    def __init__(self, main):
        super().__init__("Convert to PDF",
                         "Drop Word, Excel, PowerPoint, images, or text files. Each becomes its own PDF.")
        self.main = main
        self.files: list[Path] = []

        self.drop = DropZone("Drop .docx  .xlsx  .pptx  .png  .jpg  .txt  and more",
                             accept_exts=CONVERTIBLE_TO_PDF)
        self.drop.filesDropped.connect(self.add_files)
        self.root.addWidget(self.drop)

        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.root.addWidget(self.list, 1)

        row = QHBoxLayout()
        add = QPushButton("Add Files…"); add.setObjectName("secondary")
        add.clicked.connect(self.pick_files)
        clear = QPushButton("Clear"); clear.setObjectName("secondary")
        clear.clicked.connect(self.clear)
        convert = QPushButton("Convert →  PDF")
        convert.clicked.connect(self.convert)
        row.addWidget(add); row.addWidget(clear); row.addStretch(); row.addWidget(convert)
        self.root.addLayout(row)

    def add_files(self, paths):
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                self.list.addItem(QListWidgetItem(f"  {p.name}   ·   {p.parent}"))

    def pick_files(self):
        exts = " ".join(f"*{e}" for e in sorted(CONVERTIBLE_TO_PDF))
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select files", str(Path.home()),
            f"Convertible ({exts});;All Files (*)")
        if files:
            self.add_files([Path(f) for f in files])

    def clear(self):
        self.files.clear(); self.list.clear()

    def convert(self):
        if not self.files:
            self.main.warn("Add some files first."); return
        out_dir = QFileDialog.getExistingDirectory(self, "Save PDFs to", str(Path.home() / "Desktop"))
        if not out_dir:
            return
        out = Path(out_dir)
        srcs = list(self.files)

        def work():
            done = []
            for i, src in enumerate(srcs, 1):
                dest = convert_to_pdf(src, out)
                done.append(dest)
            return done

        self.main.run_job(work, f"Converted {len(srcs)} file(s) → PDF")


class FromPdfPage(Section):
    def __init__(self, main):
        super().__init__("Convert from PDF",
                         "Drop a PDF and pick a target format. Word, text, or one image per page.")
        self.main = main
        self.src: Path | None = None

        self.drop = DropZone("Drop a single PDF here", accept_exts={".pdf"})
        self.drop.filesDropped.connect(lambda p: self.set_src(p[0]))
        self.root.addWidget(self.drop)

        self.name_lbl = QLabel("No file selected")
        self.name_lbl.setObjectName("sub")
        self.root.addWidget(self.name_lbl)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Convert to:"))
        self.fmt = QComboBox()
        for label in PDF_OUT_FORMATS:
            self.fmt.addItem(label)
        fmt_row.addWidget(self.fmt); fmt_row.addStretch()
        self.root.addLayout(fmt_row)

        self.root.addStretch()

        row = QHBoxLayout()
        pick = QPushButton("Choose PDF…"); pick.setObjectName("secondary")
        pick.clicked.connect(self.pick)
        go = QPushButton("Convert")
        go.clicked.connect(self.convert)
        row.addWidget(pick); row.addStretch(); row.addWidget(go)
        self.root.addLayout(row)

    def set_src(self, p: Path):
        self.src = p
        self.name_lbl.setText(f"Selected: {p.name}")

    def pick(self):
        f, _ = QFileDialog.getOpenFileName(self, "Choose PDF", str(Path.home()), "PDF (*.pdf)")
        if f:
            self.set_src(Path(f))

    def convert(self):
        if not self.src:
            self.main.warn("Choose a PDF first."); return
        fmt = PDF_OUT_FORMATS[self.fmt.currentText()]
        default_name = self.src.with_suffix("." + ("docx" if fmt == "docx" else fmt)).name
        out, _ = QFileDialog.getSaveFileName(
            self, "Save as", str(Path.home() / "Desktop" / default_name))
        if not out:
            return
        out_path = Path(out)
        src = self.src

        def work():
            return convert_from_pdf(src, out_path, fmt)

        self.main.run_job(work, f"Converted → {out_path.name}")


class MergePage(Section):
    def __init__(self, main):
        super().__init__("Merge PDFs",
                         "Drop several PDFs, reorder them if you like, then merge into one.")
        self.main = main
        self.files: list[Path] = []

        self.drop = DropZone("Drop PDFs here", accept_exts={".pdf"})
        self.drop.filesDropped.connect(self.add)
        self.root.addWidget(self.drop)

        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.root.addWidget(self.list, 1)

        row = QHBoxLayout()
        addb = QPushButton("Add PDFs…"); addb.setObjectName("secondary"); addb.clicked.connect(self.pick)
        upb = QPushButton("↑"); upb.setObjectName("secondary"); upb.clicked.connect(lambda: self.move(-1))
        dnb = QPushButton("↓"); dnb.setObjectName("secondary"); dnb.clicked.connect(lambda: self.move(1))
        rmb = QPushButton("Remove"); rmb.setObjectName("secondary"); rmb.clicked.connect(self.remove_sel)
        merge = QPushButton("Merge")
        merge.clicked.connect(self.merge)
        for w in (addb, upb, dnb, rmb):
            row.addWidget(w)
        row.addStretch(); row.addWidget(merge)
        self.root.addLayout(row)

    def sync_from_list(self):
        # Rebuild self.files from list order (in case user dragged rows)
        by_name = {p.name: p for p in self.files}
        new_files = []
        for i in range(self.list.count()):
            name = self.list.item(i).data(Qt.ItemDataRole.UserRole)
            if name in by_name:
                new_files.append(by_name[name])
        self.files = new_files

    def add(self, paths):
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                item = QListWidgetItem(f"  {p.name}")
                item.setData(Qt.ItemDataRole.UserRole, p.name)
                self.list.addItem(item)

    def pick(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Choose PDFs", str(Path.home()), "PDF (*.pdf)")
        if files:
            self.add([Path(f) for f in files])

    def move(self, delta):
        row = self.list.currentRow()
        if row < 0: return
        new = row + delta
        if not (0 <= new < self.list.count()): return
        item = self.list.takeItem(row)
        self.list.insertItem(new, item)
        self.list.setCurrentRow(new)

    def remove_sel(self):
        for item in self.list.selectedItems():
            self.list.takeItem(self.list.row(item))
        self.sync_from_list()

    def merge(self):
        self.sync_from_list()
        if len(self.files) < 2:
            self.main.warn("Add at least two PDFs."); return
        out, _ = QFileDialog.getSaveFileName(
            self, "Save merged PDF", str(Path.home() / "Desktop" / "merged.pdf"), "PDF (*.pdf)")
        if not out: return
        srcs = list(self.files); dest = Path(out)

        def work():
            return merge_pdfs(srcs, dest)

        self.main.run_job(work, f"Merged {len(srcs)} PDFs → {dest.name}")


class RemovePagesPage(Section):
    def __init__(self, main):
        super().__init__("Remove pages",
                         "Drop a PDF, list the pages to delete (e.g. 1,3,5-8), save the result.")
        self.main = main
        self.src: Path | None = None
        self.page_count = 0

        self.drop = DropZone("Drop a single PDF here", accept_exts={".pdf"})
        self.drop.filesDropped.connect(lambda p: self.set_src(p[0]))
        self.root.addWidget(self.drop)

        self.info = QLabel("No file selected"); self.info.setObjectName("sub")
        self.root.addWidget(self.info)

        from PyQt6.QtWidgets import QLineEdit
        self.range_edit = QLineEdit()
        self.range_edit.setPlaceholderText("Pages to remove — e.g. 1,3,5-8")
        self.range_edit.setStyleSheet(
            "background:#242427; border:1px solid #3a3a3d; border-radius:6px; "
            "padding:8px; color:#f2f2f7;")
        self.root.addWidget(self.range_edit)
        self.root.addStretch()

        row = QHBoxLayout()
        pick = QPushButton("Choose PDF…"); pick.setObjectName("secondary"); pick.clicked.connect(self.pick)
        go = QPushButton("Remove & Save"); go.clicked.connect(self.go)
        row.addWidget(pick); row.addStretch(); row.addWidget(go)
        self.root.addLayout(row)

    def set_src(self, p: Path):
        self.src = p
        try:
            self.page_count = len(PdfReader(str(p)).pages)
        except Exception as e:
            self.main.warn(f"Couldn't read PDF: {e}"); return
        self.info.setText(f"Selected: {p.name}  ({self.page_count} pages)")

    def pick(self):
        f, _ = QFileDialog.getOpenFileName(self, "Choose PDF", str(Path.home()), "PDF (*.pdf)")
        if f: self.set_src(Path(f))

    def parse_ranges(self, text: str) -> set[int]:
        out: set[int] = set()
        for chunk in text.split(","):
            chunk = chunk.strip()
            if not chunk: continue
            if "-" in chunk:
                a, b = chunk.split("-", 1)
                out.update(range(int(a), int(b) + 1))
            else:
                out.add(int(chunk))
        return out

    def go(self):
        if not self.src:
            self.main.warn("Choose a PDF first."); return
        try:
            pages = self.parse_ranges(self.range_edit.text())
        except ValueError:
            self.main.warn("Page list should look like:  1,3,5-8"); return
        if not pages:
            self.main.warn("Type at least one page number."); return
        if any(p < 1 or p > self.page_count for p in pages):
            self.main.warn(f"Pages must be between 1 and {self.page_count}."); return
        if len(pages) >= self.page_count:
            self.main.warn("That would remove every page."); return

        default = self.src.with_stem(self.src.stem + "-trimmed").name
        out, _ = QFileDialog.getSaveFileName(
            self, "Save trimmed PDF", str(Path.home() / "Desktop" / default), "PDF (*.pdf)")
        if not out: return
        src = self.src; dest = Path(out)

        def work():
            return remove_pages(src, pages, dest)

        self.main.run_job(work, f"Removed {len(pages)} pages → {dest.name}")


class InsertPage(Section):
    def __init__(self, main):
        super().__init__("Insert PDF into another",
                         "Base PDF gets a second PDF spliced in after the page number you choose.")
        self.main = main
        self.base: Path | None = None
        self.insert: Path | None = None

        r1 = QHBoxLayout()
        self.base_drop = DropZone("Drop base PDF", accept_exts={".pdf"})
        self.base_drop.filesDropped.connect(lambda p: self.set_base(p[0]))
        self.ins_drop = DropZone("Drop PDF to insert", accept_exts={".pdf"})
        self.ins_drop.filesDropped.connect(lambda p: self.set_ins(p[0]))
        r1.addWidget(self.base_drop); r1.addWidget(self.ins_drop)
        self.root.addLayout(r1)

        self.base_lbl = QLabel("Base: —"); self.base_lbl.setObjectName("sub")
        self.ins_lbl = QLabel("Insert: —"); self.ins_lbl.setObjectName("sub")
        self.root.addWidget(self.base_lbl); self.root.addWidget(self.ins_lbl)

        pos_row = QHBoxLayout()
        pos_row.addWidget(QLabel("Insert after page:"))
        self.pos = QSpinBox(); self.pos.setMinimum(0); self.pos.setMaximum(1); self.pos.setValue(0)
        pos_row.addWidget(self.pos)
        self.help = QLabel("(0 = at the very beginning)")
        self.help.setObjectName("sub")
        pos_row.addWidget(self.help); pos_row.addStretch()
        self.root.addLayout(pos_row)

        self.root.addStretch()

        row = QHBoxLayout()
        go = QPushButton("Insert & Save"); go.clicked.connect(self.go)
        row.addStretch(); row.addWidget(go)
        self.root.addLayout(row)

    def set_base(self, p: Path):
        try:
            n = len(PdfReader(str(p)).pages)
        except Exception as e:
            self.main.warn(f"Couldn't read PDF: {e}"); return
        self.base = p
        self.base_lbl.setText(f"Base: {p.name}  ({n} pages)")
        self.pos.setMaximum(n)

    def set_ins(self, p: Path):
        try:
            n = len(PdfReader(str(p)).pages)
        except Exception as e:
            self.main.warn(f"Couldn't read PDF: {e}"); return
        self.insert = p
        self.ins_lbl.setText(f"Insert: {p.name}  ({n} pages)")

    def go(self):
        if not self.base or not self.insert:
            self.main.warn("Pick both a base and an insert PDF."); return
        default = self.base.with_stem(self.base.stem + "-with-insert").name
        out, _ = QFileDialog.getSaveFileName(
            self, "Save combined PDF", str(Path.home() / "Desktop" / default), "PDF (*.pdf)")
        if not out: return
        base = self.base; ins = self.insert; after = self.pos.value(); dest = Path(out)

        def work():
            return insert_pdf(base, ins, after, dest)

        self.main.run_job(work, f"Inserted → {dest.name}")


class CompressPage(Section):
    QUALITIES = [
        ("Screen — smallest (72 dpi)", "screen"),
        ("eBook — recommended (150 dpi)", "ebook"),
        ("Printer — high quality (300 dpi)", "printer"),
        ("Prepress — near-lossless (300 dpi, color-preserving)", "prepress"),
    ]

    def __init__(self, main):
        super().__init__("Compress PDF",
                         "Shrink a PDF using Ghostscript. eBook keeps text sharp and most images intact.")
        self.main = main
        self.src: Path | None = None

        self.drop = DropZone("Drop a PDF here", accept_exts={".pdf"})
        self.drop.filesDropped.connect(lambda p: self.set_src(p[0]))
        self.root.addWidget(self.drop)

        self.info = QLabel("No file selected"); self.info.setObjectName("sub")
        self.root.addWidget(self.info)

        row = QHBoxLayout()
        row.addWidget(QLabel("Quality:"))
        self.quality = QComboBox()
        for label, _ in self.QUALITIES:
            self.quality.addItem(label)
        self.quality.setCurrentIndex(1)
        row.addWidget(self.quality); row.addStretch()
        self.root.addLayout(row)

        self.root.addStretch()

        brow = QHBoxLayout()
        pick = QPushButton("Choose PDF…"); pick.setObjectName("secondary"); pick.clicked.connect(self.pick)
        go = QPushButton("Compress & Save"); go.clicked.connect(self.go)
        brow.addWidget(pick); brow.addStretch(); brow.addWidget(go)
        self.root.addLayout(brow)

    def set_src(self, p: Path):
        self.src = p
        size = p.stat().st_size / (1024 * 1024)
        self.info.setText(f"Selected: {p.name}  ({size:.2f} MB)")

    def pick(self):
        f, _ = QFileDialog.getOpenFileName(self, "Choose PDF", str(Path.home()), "PDF (*.pdf)")
        if f: self.set_src(Path(f))

    def go(self):
        if not self.src:
            self.main.warn("Choose a PDF first."); return
        preset = self.QUALITIES[self.quality.currentIndex()][1]
        default = self.src.with_stem(self.src.stem + "-compressed").name
        out, _ = QFileDialog.getSaveFileName(
            self, "Save compressed PDF", str(Path.home() / "Desktop" / default), "PDF (*.pdf)")
        if not out: return
        src = self.src; dest = Path(out)

        def work():
            result = compress_pdf(src, dest, preset)
            before = src.stat().st_size
            after = result.stat().st_size
            pct = (1 - after / before) * 100 if before else 0
            return (result, before, after, pct)

        def done(result):
            dest_path, before, after, pct = result
            self.main.info(
                f"Saved to {dest_path.name}\n"
                f"{before / 1024 / 1024:.2f} MB → {after / 1024 / 1024:.2f} MB "
                f"({pct:.1f}% smaller)")

        self.main.run_job(work, "Compression finished", on_done=done)


# ── Main window ─────────────────────────────────────────────

class MainWindow(QMainWindow):
    PAGES = [
        ("To PDF",       "▲",  ToPdfPage),
        ("From PDF",     "▼",  FromPdfPage),
        ("Merge",        "⧉",  MergePage),
        ("Remove pages", "✕",  RemovePagesPage),
        ("Insert",       "↳",  InsertPage),
        ("Compress",     "⇣",  CompressPage),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1000, 660)
        self.setMinimumSize(820, 540)
        self.pool = QThreadPool.globalInstance()

        central = QWidget(); self.setCentralWidget(central)
        h = QHBoxLayout(central); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(0)

        # Sidebar
        side = QFrame(); side.setObjectName("sidebar"); side.setFixedWidth(210)
        sv = QVBoxLayout(side); sv.setContentsMargins(8, 12, 8, 12); sv.setSpacing(2)

        brand = QLabel("Ghenghis Khan"); brand.setObjectName("brand")
        sub = QLabel("Local document toolkit"); sub.setObjectName("brandSub")
        sv.addWidget(brand); sv.addWidget(sub)

        self.stack = QStackedWidget()
        self.nav_buttons = []
        for i, (title, icon, cls) in enumerate(self.PAGES):
            page = cls(self)
            self.stack.addWidget(page)
            btn = QPushButton(f"  {icon}   {title}")
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, idx=i: self.select(idx))
            sv.addWidget(btn)
            self.nav_buttons.append(btn)
        sv.addStretch()

        # Health footer
        self.health = QLabel(""); self.health.setObjectName("sub")
        self.health.setWordWrap(True)
        self.health.setContentsMargins(10, 4, 10, 4)
        self.health.setStyleSheet("font-size:11px; color:#98989d;")
        sv.addWidget(self.health)

        h.addWidget(side)
        h.addWidget(self.stack, 1)

        # Status
        self.status = QStatusBar(); self.setStatusBar(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # busy
        self.progress.setFixedWidth(160); self.progress.setVisible(False)
        self.status.addPermanentWidget(self.progress)
        self.status.showMessage("Ready.")

        self.select(0)
        self.update_health()

    def select(self, idx):
        self.stack.setCurrentIndex(idx)
        for i, b in enumerate(self.nav_buttons):
            b.setChecked(i == idx)

    def update_health(self):
        parts = []
        if not find_soffice():
            parts.append("• LibreOffice missing — Office conversions disabled")
        if not find_ghostscript():
            parts.append("• Ghostscript missing — Compression / PDF→image disabled")
        if parts:
            self.health.setText("\n".join(parts) + "\n\nRun install.sh to fix.")
        else:
            self.health.setText("• All tools ready")

    # ── job plumbing ────────────────────────────────────────
    def run_job(self, fn, success_msg: str, on_done=None):
        self.progress.setVisible(True)
        self.status.showMessage("Working…")
        for b in self.nav_buttons: b.setEnabled(False)

        worker = Worker(fn)
        worker.signals.finished.connect(lambda r: self._finish(True, success_msg, r, on_done))
        worker.signals.error.connect(lambda e: self._finish(False, e, None, None))
        self.pool.start(worker)

    def _finish(self, ok: bool, msg: str, result, on_done):
        self.progress.setVisible(False)
        for b in self.nav_buttons: b.setEnabled(True)
        if ok:
            self.status.showMessage(msg, 8000)
            if on_done:
                on_done(result)
            else:
                self.info(msg)
        else:
            self.status.showMessage("Error.", 6000)
            self.warn(msg)

    def warn(self, text: str):
        m = QMessageBox(self)
        m.setIcon(QMessageBox.Icon.Warning)
        m.setWindowTitle(APP_NAME)
        m.setText(text)
        m.exec()

    def info(self, text: str):
        m = QMessageBox(self)
        m.setIcon(QMessageBox.Icon.Information)
        m.setWindowTitle(APP_NAME)
        m.setText(text)
        m.exec()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
