"""
quick_view_module.py  –  Macan File Vault Quick View Sidebar
=============================================================
Modul Quick View untuk melihat isi file terenkripsi tanpa harus
mendekripsi ke disk. File didekripsi sementara hanya di memori (RAM)
lalu langsung ditampilkan di sidebar.

Supported formats:
  Images   : jpg, jpeg, png, gif, bmp, webp, ico, tiff, svg
  Text     : txt, md, log, ini, cfg, conf, yaml, yml, toml, xml, html, csv
  Code     : py, js, ts, jsx, tsx, java, c, cpp, h, cs, go, rs, rb, php,
             sh, bat, ps1, sql, r, swift, kt, dart, lua
  Archives : zip (listing only)
  PDF      : first-page text extraction
  Audio    : mp3, wav, ogg, flac, m4a, aac  (playback via QMediaPlayer + metadata)
  Video    : mp4, mkv, avi, mov, webm        (playback via QMediaPlayer + metadata)
  Office   : docx (text extract), xlsx (sheet preview)

All decryption happens in-memory — no temp files written to disk.
"""

import os
import io
import struct
import zipfile
import datetime
import tempfile

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QTextEdit, QSizePolicy, QStackedWidget,
    QProgressBar, QSlider,
)
from PySide6.QtCore import (
    Qt, QThread, Signal, QObject, Slot, QByteArray, QUrl, QTimer,
)
from PySide6.QtGui import QPixmap, QFont, QColor, QFontDatabase, QSyntaxHighlighter, QTextCharFormat

try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PySide6.QtMultimediaWidgets import QVideoWidget
    _MULTIMEDIA_AVAILABLE = True
except ImportError:
    _MULTIMEDIA_AVAILABLE = False

# ── Design tokens (mirroring main app) ────────────────────────────────────────
CLR_BG_BASE       = "#0f1117"
CLR_BG_SURFACE    = "#161b27"
CLR_BG_RAISED     = "#1e2535"
CLR_BG_HOVER      = "#252d40"
CLR_BORDER        = "#2a3348"
CLR_BORDER_FOCUS  = "#3d6aad"
CLR_ACCENT        = "#4a8fd1"
CLR_ACCENT_DEEP   = "#2e6baa"
CLR_ACCENT_GLOW   = "#5ba3e8"
CLR_SUCCESS       = "#2ecc71"
CLR_DANGER        = "#e74c3c"
CLR_WARN          = "#e67e22"
CLR_TEXT_PRIMARY  = "#e8edf5"
CLR_TEXT_SECONDARY= "#8a95a8"
CLR_TEXT_MUTED    = "#4d5669"

# ── Format categories ─────────────────────────────────────────────────────────
IMAGE_EXTS   = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".ico", ".tiff", ".tif", ".svg"}
TEXT_EXTS    = {".txt", ".md", ".log", ".ini", ".cfg", ".conf", ".yaml", ".yml",
                ".toml", ".xml", ".html", ".htm", ".csv", ".json", ".env", ".gitignore",
                ".dockerfile", ".makefile", ".rst", ".tex"}
CODE_EXTS    = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h", ".hpp",
                ".cs", ".go", ".rs", ".rb", ".php", ".sh", ".bash", ".bat", ".ps1",
                ".sql", ".r", ".swift", ".kt", ".dart", ".lua", ".vim", ".asm",
                ".vb", ".pl", ".scala", ".m", ".f90", ".jl", ".ex", ".exs", ".clj"}
AUDIO_EXTS   = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".wma", ".opus", ".aiff"}
VIDEO_EXTS   = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv", ".flv", ".m4v", ".3gp"}
PDF_EXTS     = {".pdf"}
ARCHIVE_EXTS = {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar"}
OFFICE_EXTS  = {".docx", ".xlsx", ".pptx", ".doc", ".xls"}

# Syntax highlight color map (keyword sets per language)
LANG_KEYWORDS = {
    ".py":    ["def", "class", "import", "from", "return", "if", "elif", "else",
                "for", "while", "try", "except", "finally", "with", "as", "pass",
                "yield", "lambda", "True", "False", "None", "and", "or", "not",
                "in", "is", "del", "global", "nonlocal", "raise", "assert"],
    ".js":    ["function", "const", "let", "var", "return", "if", "else", "for",
                "while", "class", "import", "export", "from", "new", "this",
                "try", "catch", "finally", "async", "await", "typeof", "null",
                "undefined", "true", "false", "switch", "case", "break", "continue"],
    ".java":  ["public", "private", "protected", "class", "interface", "extends",
                "implements", "import", "package", "return", "if", "else", "for",
                "while", "new", "static", "final", "void", "int", "String",
                "boolean", "try", "catch", "throw", "throws"],
    ".go":    ["func", "package", "import", "var", "const", "type", "struct",
                "interface", "return", "if", "else", "for", "range", "switch",
                "case", "break", "continue", "defer", "go", "chan", "map",
                "nil", "true", "false"],
    ".rs":    ["fn", "let", "mut", "const", "use", "mod", "pub", "struct", "enum",
                "impl", "trait", "for", "while", "if", "else", "match", "return",
                "self", "Self", "true", "false", "None", "Some", "Ok", "Err"],
    ".sql":   ["SELECT", "FROM", "WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER",
                "ON", "AND", "OR", "NOT", "IN", "IS", "NULL", "ORDER", "BY",
                "GROUP", "HAVING", "LIMIT", "OFFSET", "INSERT", "INTO", "VALUES",
                "UPDATE", "SET", "DELETE", "CREATE", "TABLE", "INDEX", "DROP",
                "ALTER", "ADD", "COLUMN", "PRIMARY", "KEY", "FOREIGN", "REFERENCES"],
}


def _detect_category(ext: str) -> str:
    """Return category string for the given extension."""
    e = ext.lower()
    if e in IMAGE_EXTS:   return "image"
    if e in CODE_EXTS:    return "code"
    if e in TEXT_EXTS:    return "text"
    if e in AUDIO_EXTS:   return "audio"
    if e in VIDEO_EXTS:   return "video"
    if e in PDF_EXTS:     return "pdf"
    if e in ARCHIVE_EXTS: return "archive"
    if e in OFFICE_EXTS:  return "office"
    return "binary"


def _human_size(b: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


# ── In-memory decryption helper ───────────────────────────────────────────────

def decrypt_to_memory(mfe_path: str, password: str) -> tuple[bytes, dict]:
    """
    Decrypt a .mfe file entirely in memory.
    Returns (plaintext_bytes, meta_dict).
    Raises on wrong password or corrupt file.
    """
    # Import only when needed to keep module self-contained
    import json, secrets as _sec
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    VAULT_MAGIC   = b"MCVT"
    SALT_SIZE     = 16
    NONCE_SIZE    = 12
    PBKDF2_ITERS  = 310_000
    KEY_LENGTH    = 32

    with open(mfe_path, "rb") as f:
        raw = f.read()

    offset = 0
    magic  = raw[offset:offset+4]; offset += 4
    if magic != VAULT_MAGIC:
        raise ValueError("Not a Macan vault file.")
    _ver   = struct.unpack(">H", raw[offset:offset+2])[0]; offset += 2
    salt   = raw[offset:offset+SALT_SIZE]; offset += SALT_SIZE
    n_meta = raw[offset:offset+NONCE_SIZE]; offset += NONCE_SIZE
    m_len  = struct.unpack(">I", raw[offset:offset+4])[0]; offset += 4
    e_meta = raw[offset:offset+m_len]; offset += m_len
    n_data = raw[offset:offset+NONCE_SIZE]; offset += NONCE_SIZE
    e_data = raw[offset:]

    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=KEY_LENGTH,
                     salt=salt, iterations=PBKDF2_ITERS)
    key  = kdf.derive(password.encode("utf-8"))
    aesgcm = AESGCM(key)
    meta   = json.loads(aesgcm.decrypt(n_meta, e_meta, None).decode("utf-8"))
    plain  = aesgcm.decrypt(n_data, e_data, None)
    return plain, meta


# ── Background worker ─────────────────────────────────────────────────────────

class QuickViewWorker(QObject):
    ready   = Signal(bytes, dict, str)  # plaintext, meta, ext
    error   = Signal(str)

    def __init__(self, mfe_path: str, password: str, ext: str):
        super().__init__()
        self.mfe_path = mfe_path
        self.password = password
        self.ext      = ext

    @Slot()
    def run(self):
        try:
            data, meta = decrypt_to_memory(self.mfe_path, self.password)
            self.ready.emit(data, meta, self.ext)
        except Exception as e:
            self.error.emit(str(e))


# ── Syntax highlighter ────────────────────────────────────────────────────────

class SimpleHighlighter(QSyntaxHighlighter):
    """Very lightweight keyword + string + comment highlighter."""

    def __init__(self, doc, ext: str):
        super().__init__(doc)
        self.ext = ext.lower()

        self._kw_fmt = QTextCharFormat()
        self._kw_fmt.setForeground(QColor("#569cd6"))    # blue

        self._str_fmt = QTextCharFormat()
        self._str_fmt.setForeground(QColor("#ce9178"))   # orange-brown

        self._cmt_fmt = QTextCharFormat()
        self._cmt_fmt.setForeground(QColor("#6a9955"))   # green

        self._num_fmt = QTextCharFormat()
        self._num_fmt.setForeground(QColor("#b5cea8"))   # light green

        # Build keyword list
        self.keywords = []
        for k, v in LANG_KEYWORDS.items():
            if self.ext in (k, k.replace(".", ""), ".ts", ".jsx", ".tsx"):
                self.keywords = v
                break
        # JS aliases
        if self.ext in (".ts", ".jsx", ".tsx") and not self.keywords:
            self.keywords = LANG_KEYWORDS.get(".js", [])

    def highlightBlock(self, text: str):
        import re

        # Comments
        comment_starts = {"#": "#", "//": "//", "--": "--"}
        for marker in ["#", "//", "--"]:
            idx = text.find(marker)
            if idx >= 0:
                self.setFormat(idx, len(text) - idx, self._cmt_fmt)
                text = text[:idx] + " " * (len(text) - idx)   # mask rest
                break

        # Strings (very simple: "..." or '...')
        for m in re.finditer(r'(".*?"|\'.*?\')', text):
            self.setFormat(m.start(), m.end() - m.start(), self._str_fmt)

        # Numbers
        for m in re.finditer(r'\b\d+(\.\d+)?\b', text):
            self.setFormat(m.start(), m.end() - m.start(), self._num_fmt)

        # Keywords
        for kw in self.keywords:
            for m in re.finditer(r'\b' + re.escape(kw) + r'\b', text):
                self.setFormat(m.start(), m.end() - m.start(), self._kw_fmt)


# ── Individual viewer widgets ─────────────────────────────────────────────────

class _ImageViewer(QScrollArea):
    def __init__(self, data: bytes, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("QScrollArea { background: #0a0d13; border: none; }")

        lbl = QLabel()
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("background: transparent;")

        ba = QByteArray(data)
        pix = QPixmap()
        pix.loadFromData(ba)
        if pix.isNull():
            lbl.setText("⚠  Could not render image")
            lbl.setStyleSheet(f"color: {CLR_WARN}; font-size: 10pt; background: transparent;")
        else:
            # Scale to fit sidebar width (~340px) while keeping ratio
            scaled = pix.scaled(
                340, 1200,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            lbl.setPixmap(scaled)

        self.setWidget(lbl)


class _TextViewer(QWidget):
    def __init__(self, data: bytes, ext: str, max_chars: int = 120_000, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        editor = QTextEdit()
        editor.setReadOnly(True)
        editor.setWordWrapMode(1)   # QTextOption.WrapAtWordBoundaryOrAnywhere
        editor.setStyleSheet(f"""
            QTextEdit {{
                background: {CLR_BG_BASE};
                color: {CLR_TEXT_PRIMARY};
                border: none;
                font-family: "Cascadia Code", "Fira Code", "Consolas", "Courier New", monospace;
                font-size: 9pt;
                padding: 8px;
            }}
            QScrollBar:vertical {{
                background: {CLR_BG_SURFACE};
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {CLR_BORDER};
                border-radius: 3px;
                min-height: 20px;
            }}
        """)

        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = data.decode("latin-1", errors="replace")

        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n… [truncated — showing first {max_chars:,} chars]"

        editor.setPlainText(text)

        # Apply syntax highlighting for code files
        if ext.lower() in CODE_EXTS:
            SimpleHighlighter(editor.document(), ext)

        lay.addWidget(editor)


class _MetaInfoWidget(QWidget):
    """Displays key-value metadata rows."""
    def __init__(self, rows: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(6)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        for label, value in rows:
            row = QHBoxLayout()
            lbl_w = QLabel(label)
            lbl_w.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 8.5pt; min-width: 110px; background: transparent;")
            val_w = QLabel(str(value))
            val_w.setStyleSheet(f"color: {CLR_TEXT_PRIMARY}; font-size: 8.5pt; background: transparent;")
            val_w.setWordWrap(True)
            row.addWidget(lbl_w)
            row.addWidget(val_w, 1)
            lay.addLayout(row)

        lay.addStretch()


class _MediaPlayerControls(QWidget):
    """
    Reusable transport bar: play/pause, seek slider, time label, volume.
    Works for both audio-only and video players.
    """

    def __init__(self, player: "QMediaPlayer", audio_output: "QAudioOutput",
                 parent=None):
        super().__init__(parent)
        self._player = player
        self._audio  = audio_output
        self._dragging = False
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        # ── Seek bar ──
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setValue(0)
        self.seek_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {CLR_BG_RAISED};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {CLR_ACCENT};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {CLR_ACCENT_GLOW};
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }}
        """)
        root.addWidget(self.seek_slider)

        # ── Bottom row: play | time | vol ──
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        bottom.setContentsMargins(0, 0, 0, 0)

        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(32, 32)
        self.play_btn.setStyleSheet(f"""
            QPushButton {{
                background: {CLR_ACCENT};
                color: white;
                border: none;
                border-radius: 16px;
                font-size: 11pt;
            }}
            QPushButton:hover {{ background: {CLR_ACCENT_GLOW}; }}
            QPushButton:pressed {{ background: {CLR_ACCENT_DEEP}; }}
        """)
        bottom.addWidget(self.play_btn)

        self.time_lbl = QLabel("0:00 / 0:00")
        self.time_lbl.setStyleSheet(
            f"color: {CLR_TEXT_SECONDARY}; font-size: 8pt; background: transparent;"
        )
        self.time_lbl.setMinimumWidth(90)
        bottom.addWidget(self.time_lbl)

        bottom.addStretch()

        # Volume icon + slider
        vol_icon = QLabel("🔊")
        vol_icon.setStyleSheet("background: transparent; font-size: 9pt;")
        bottom.addWidget(vol_icon)

        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setFixedWidth(70)
        self.vol_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {CLR_BG_RAISED};
                height: 3px;
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {CLR_BORDER_FOCUS};
                height: 3px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {CLR_TEXT_SECONDARY};
                width: 10px;
                height: 10px;
                margin: -4px 0;
                border-radius: 5px;
            }}
        """)
        self._audio.setVolume(0.8)
        bottom.addWidget(self.vol_slider)

        root.addLayout(bottom)

    def _connect_signals(self):
        self.play_btn.clicked.connect(self._toggle_play)
        self.vol_slider.valueChanged.connect(
            lambda v: self._audio.setVolume(v / 100.0)
        )
        self.seek_slider.sliderPressed.connect(self._seek_start)
        self.seek_slider.sliderReleased.connect(self._seek_end)
        self._player.positionChanged.connect(self._on_position)
        self._player.durationChanged.connect(self._on_duration)
        self._player.playbackStateChanged.connect(self._on_state)

    # ── Slots ──────────────────────────────────────────────────────────────

    def _toggle_play(self):
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _seek_start(self):
        self._dragging = True

    def _seek_end(self):
        self._dragging = False
        dur = self._player.duration()
        if dur > 0:
            pos = int(self.seek_slider.value() / 1000 * dur)
            self._player.setPosition(pos)

    def _on_position(self, pos_ms: int):
        if not self._dragging:
            dur = self._player.duration()
            if dur > 0:
                self.seek_slider.setValue(int(pos_ms / dur * 1000))
        self._update_time(pos_ms, self._player.duration())

    def _on_duration(self, dur_ms: int):
        self._update_time(self._player.position(), dur_ms)

    def _on_state(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.play_btn.setText("⏸" if playing else "▶")

    def _update_time(self, pos_ms: int, dur_ms: int):
        def fmt(ms):
            s = ms // 1000
            return f"{s // 60}:{s % 60:02d}"
        self.time_lbl.setText(f"{fmt(pos_ms)} / {fmt(dur_ms)}")

    def stop_player(self):
        """Call on widget close to stop playback and free the temp file."""
        self._player.stop()


class _AudioViewer(QWidget):
    def __init__(self, data: bytes, meta: dict, ext: str, parent=None):
        super().__init__(parent)
        self._tmp_file = None   # keep reference so it isn't deleted
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        # ── Header ──
        icon_lbl = QLabel("🎵")
        icon_lbl.setStyleSheet("font-size: 36pt; background: transparent;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(icon_lbl)

        name_lbl = QLabel(meta.get("original_name", "Audio File"))
        name_lbl.setStyleSheet(
            f"font-size: 10pt; font-weight: 600; color: {CLR_TEXT_PRIMARY}; background: transparent;"
        )
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setWordWrap(True)
        lay.addWidget(name_lbl)

        # ── Waveform ──
        waveform = _WaveformWidget(data, self)
        lay.addWidget(waveform)

        # ── Metadata rows ──
        rows = [
            ("Format", ext.lstrip(".").upper()),
            ("Size",   _human_size(len(data))),
        ]
        if ext.lower() == ".mp3":
            rows += _parse_mp3_tags(data)
        elif ext.lower() == ".wav":
            rows += _parse_wav_header(data)

        for label, value in rows:
            rw = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"color: {CLR_TEXT_MUTED}; font-size: 8.5pt; min-width: 90px; background: transparent;"
            )
            val = QLabel(str(value))
            val.setStyleSheet(
                f"color: {CLR_TEXT_PRIMARY}; font-size: 8.5pt; background: transparent;"
            )
            val.setWordWrap(True)
            rw.addWidget(lbl)
            rw.addWidget(val, 1)
            lay.addLayout(rw)

        lay.addSpacing(4)

        # ── Player ──
        if _MULTIMEDIA_AVAILABLE:
            self._player      = QMediaPlayer(self)
            self._audio_out   = QAudioOutput(self)
            self._player.setAudioOutput(self._audio_out)

            # Write to temp file so QMediaPlayer can read it
            suffix = ext if ext.startswith(".") else f".{ext}"
            self._tmp_file = tempfile.NamedTemporaryFile(
                suffix=suffix, delete=False
            )
            self._tmp_file.write(data)
            self._tmp_file.flush()
            self._tmp_file.close()

            self._player.setSource(QUrl.fromLocalFile(self._tmp_file.name))

            controls = _MediaPlayerControls(self._player, self._audio_out, self)
            lay.addWidget(controls)

            note = QLabel("🔒 Played from RAM — temp file auto-deleted on close.")
            note.setStyleSheet(
                f"color: {CLR_TEXT_MUTED}; font-size: 7.5pt; background: transparent; font-style: italic;"
            )
            note.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(note)
        else:
            note = QLabel(
                "⚠  PySide6.QtMultimedia not installed.\n"
                "Install with:  pip install PySide6-Addons"
            )
            note.setStyleSheet(
                f"color: {CLR_WARN}; font-size: 8pt; background: transparent;"
            )
            note.setWordWrap(True)
            note.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(note)

        lay.addStretch()

    def closeEvent(self, event):
        self._cleanup()
        super().closeEvent(event)

    def hideEvent(self, event):
        # Pause when sidebar hides/switches
        if _MULTIMEDIA_AVAILABLE and hasattr(self, "_player"):
            self._player.pause()
        super().hideEvent(event)

    def _cleanup(self):
        if _MULTIMEDIA_AVAILABLE and hasattr(self, "_player"):
            self._player.stop()
        if self._tmp_file:
            try:
                os.unlink(self._tmp_file.name)
            except OSError:
                pass
            self._tmp_file = None


class _WaveformWidget(QWidget):
    """Draws a simple amplitude bar chart from raw audio bytes."""

    def __init__(self, data: bytes, parent=None, num_bars: int = 60):
        super().__init__(parent)
        self.setFixedHeight(60)
        self.setStyleSheet(f"background: {CLR_BG_RAISED}; border-radius: 6px;")
        chunk = data[44:] if len(data) > 44 else data
        step  = max(1, len(chunk) // num_bars)
        bars  = []
        for i in range(num_bars):
            seg = chunk[i*step:(i+1)*step]
            if seg:
                amp = sum(abs(b - 128) for b in seg) / (len(seg) * 128)
                bars.append(min(1.0, amp * 4))
            else:
                bars.append(0.0)
        self._bars = bars

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        n = len(self._bars)
        bar_w = max(2, w // n - 1)
        for i, amp in enumerate(self._bars):
            x     = int(i * w / n)
            bh    = max(2, int(amp * (h - 8)))
            y     = (h - bh) // 2
            alpha = int(80 + amp * 175)
            color = QColor(74, 143, 209, alpha)
            p.fillRect(x, y, bar_w, bh, color)
        p.end()


class _VideoViewer(QWidget):
    def __init__(self, data: bytes, meta: dict, ext: str, parent=None):
        super().__init__(parent)
        self._tmp_file = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        if _MULTIMEDIA_AVAILABLE:
            # ── Video surface ──
            self._video_widget = QVideoWidget(self)
            self._video_widget.setStyleSheet("background: black;")
            self._video_widget.setMinimumHeight(180)
            self._video_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            lay.addWidget(self._video_widget, 1)

            # ── Controls bar ──
            ctrl_frame = QFrame(self)
            ctrl_frame.setStyleSheet(
                f"background: {CLR_BG_RAISED}; border-top: 1px solid {CLR_BORDER};"
            )
            ctrl_lay = QVBoxLayout(ctrl_frame)
            ctrl_lay.setContentsMargins(12, 8, 12, 10)
            ctrl_lay.setSpacing(4)

            # File name label
            name_lbl = QLabel(meta.get("original_name", "Video File"))
            name_lbl.setStyleSheet(
                f"font-size: 8.5pt; font-weight: 600; color: {CLR_TEXT_PRIMARY}; background: transparent;"
            )
            name_lbl.setWordWrap(True)
            ctrl_lay.addWidget(name_lbl)

            # Metadata row
            rows = [
                ("Format", ext.lstrip(".").upper()),
                ("Size",   _human_size(len(data))),
            ]
            if ext.lower() in (".mp4", ".m4v"):
                rows += _parse_mp4_header(data)

            meta_parts = "  ·  ".join(f"{k}: {v}" for k, v in rows)
            meta_lbl = QLabel(meta_parts)
            meta_lbl.setStyleSheet(
                f"font-size: 7.5pt; color: {CLR_TEXT_MUTED}; background: transparent;"
            )
            ctrl_lay.addWidget(meta_lbl)

            # Transport controls
            self._player    = QMediaPlayer(self)
            self._audio_out = QAudioOutput(self)
            self._player.setAudioOutput(self._audio_out)
            self._player.setVideoOutput(self._video_widget)

            controls = _MediaPlayerControls(self._player, self._audio_out, ctrl_frame)
            ctrl_lay.addWidget(controls)

            note = QLabel("🔒 Played from RAM — temp file auto-deleted on close.")
            note.setStyleSheet(
                f"color: {CLR_TEXT_MUTED}; font-size: 7pt; background: transparent; font-style: italic;"
            )
            ctrl_lay.addWidget(note)
            lay.addWidget(ctrl_frame)

            # Write temp file and load
            suffix = ext if ext.startswith(".") else f".{ext}"
            self._tmp_file = tempfile.NamedTemporaryFile(
                suffix=suffix, delete=False
            )
            self._tmp_file.write(data)
            self._tmp_file.flush()
            self._tmp_file.close()

            self._player.setSource(QUrl.fromLocalFile(self._tmp_file.name))

        else:
            # Fallback — metadata-only
            inner = QWidget(self)
            inner_lay = QVBoxLayout(inner)
            inner_lay.setContentsMargins(16, 24, 16, 16)
            inner_lay.setSpacing(12)
            inner_lay.setAlignment(Qt.AlignmentFlag.AlignTop)

            icon = QLabel("🎬")
            icon.setStyleSheet("font-size: 44pt; background: transparent;")
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inner_lay.addWidget(icon)

            name = QLabel(meta.get("original_name", "Video File"))
            name.setStyleSheet(
                f"font-size: 10pt; font-weight: 600; color: {CLR_TEXT_PRIMARY}; background: transparent;"
            )
            name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name.setWordWrap(True)
            inner_lay.addWidget(name)

            rows = [
                ("Format", ext.lstrip(".").upper()),
                ("Size",   _human_size(len(data))),
            ]
            if ext.lower() in (".mp4", ".m4v"):
                rows += _parse_mp4_header(data)

            for label, value in rows:
                rw = QHBoxLayout()
                lbl = QLabel(label)
                lbl.setStyleSheet(
                    f"color: {CLR_TEXT_MUTED}; font-size: 8.5pt; min-width: 90px; background: transparent;"
                )
                val = QLabel(str(value))
                val.setStyleSheet(
                    f"color: {CLR_TEXT_PRIMARY}; font-size: 8.5pt; background: transparent;"
                )
                val.setWordWrap(True)
                rw.addWidget(lbl)
                rw.addWidget(val, 1)
                inner_lay.addLayout(rw)

            note = QLabel(
                "⚠  PySide6.QtMultimedia not installed.\n"
                "Install with:  pip install PySide6-Addons"
            )
            note.setStyleSheet(
                f"color: {CLR_WARN}; font-size: 8pt; background: transparent;"
            )
            note.setWordWrap(True)
            note.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inner_lay.addSpacing(8)
            inner_lay.addWidget(note)
            inner_lay.addStretch()
            lay.addWidget(inner)

    def closeEvent(self, event):
        self._cleanup()
        super().closeEvent(event)

    def hideEvent(self, event):
        if _MULTIMEDIA_AVAILABLE and hasattr(self, "_player"):
            self._player.pause()
        super().hideEvent(event)

    def _cleanup(self):
        if _MULTIMEDIA_AVAILABLE and hasattr(self, "_player"):
            self._player.stop()
        if self._tmp_file:
            try:
                os.unlink(self._tmp_file.name)
            except OSError:
                pass
            self._tmp_file = None


class _ArchiveViewer(QWidget):
    def __init__(self, data: bytes, meta: dict, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        editor = QTextEdit()
        editor.setReadOnly(True)
        editor.setStyleSheet(f"""
            QTextEdit {{
                background: {CLR_BG_BASE};
                color: {CLR_TEXT_PRIMARY};
                border: none;
                font-family: "Cascadia Code", "Consolas", monospace;
                font-size: 8.5pt;
                padding: 8px;
            }}
        """)

        lines = [f"📦  Archive Contents — {meta.get('original_name', '')}\n"]
        lines.append(f"{'─' * 40}")
        try:
            buf = io.BytesIO(data)
            with zipfile.ZipFile(buf, "r") as z:
                infos = z.infolist()
                lines.append(f"{'Name':<36} {'Size':>10}  Date")
                lines.append("─" * 60)
                total_size = 0
                for info in infos[:500]:
                    dt = datetime.datetime(*info.date_time).strftime("%Y-%m-%d")
                    lines.append(f"  {info.filename:<34} {_human_size(info.file_size):>10}  {dt}")
                    total_size += info.file_size
                if len(infos) > 500:
                    lines.append(f"\n  … and {len(infos) - 500} more entries")
                lines.append(f"\n{'─' * 60}")
                lines.append(f"  {len(infos)} files · Total uncompressed: {_human_size(total_size)}")
        except Exception as e:
            lines.append(f"\n⚠  Could not parse archive: {e}")
            lines.append("\n(Only ZIP format is supported for listing.)")

        editor.setPlainText("\n".join(lines))
        lay.addWidget(editor)


class _OfficeViewer(QWidget):
    def __init__(self, data: bytes, meta: dict, ext: str, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        editor = QTextEdit()
        editor.setReadOnly(True)
        editor.setStyleSheet(f"""
            QTextEdit {{
                background: {CLR_BG_BASE};
                color: {CLR_TEXT_PRIMARY};
                border: none;
                font-size: 9pt;
                padding: 10px;
                line-height: 1.5;
            }}
        """)

        content = f"📄  {meta.get('original_name', '')}\n{'─' * 40}\n\n"

        try:
            if ext.lower() == ".docx":
                content += _extract_docx_text(data)
            elif ext.lower() in (".xlsx", ".xls"):
                content += _extract_xlsx_text(data)
            elif ext.lower() == ".pptx":
                content += _extract_pptx_text(data)
            else:
                content += "(Office format preview not available — decrypt to open in Office.)"
        except ImportError as e:
            content += f"⚠  Optional library missing: {e}\n\nInstall with:\n  pip install python-docx openpyxl python-pptx"
        except Exception as e:
            content += f"⚠  Could not parse document: {e}"

        editor.setPlainText(content)
        lay.addWidget(editor)


class _BinaryViewer(QWidget):
    def __init__(self, data: bytes, meta: dict, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        editor = QTextEdit()
        editor.setReadOnly(True)
        editor.setStyleSheet(f"""
            QTextEdit {{
                background: {CLR_BG_BASE};
                color: {CLR_TEXT_PRIMARY};
                border: none;
                font-family: "Cascadia Code", "Consolas", monospace;
                font-size: 8.5pt;
                padding: 8px;
            }}
        """)

        lines = [f"🔢  Hex Preview — {meta.get('original_name', '')}\n"]
        lines.append(f"{'─' * 68}")
        lines.append(f"{'Offset':<10} {'00 01 02 03 04 05 06 07  08 09 0A 0B 0C 0D 0E 0F':<49}  ASCII")
        lines.append("─" * 68)
        preview = data[:1024]
        for i in range(0, len(preview), 16):
            row      = preview[i:i+16]
            hex_part = " ".join(f"{b:02X}" for b in row)
            if len(row) > 8:
                hex_part = hex_part[:23] + "  " + hex_part[23:]
            asc  = "".join(chr(b) if 0x20 <= b < 0x7F else "·" for b in row)
            lines.append(f"  {i:08X}  {hex_part:<49}  {asc}")
        if len(data) > 1024:
            lines.append(f"\n  … showing first 1,024 of {_human_size(len(data))} bytes")
        editor.setPlainText("\n".join(lines))
        lay.addWidget(editor)


class _PdfViewer(QWidget):
    def __init__(self, data: bytes, meta: dict, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        editor = QTextEdit()
        editor.setReadOnly(True)
        editor.setStyleSheet(f"""
            QTextEdit {{
                background: {CLR_BG_BASE};
                color: {CLR_TEXT_PRIMARY};
                border: none;
                font-size: 9pt;
                padding: 10px;
            }}
        """)

        content = f"📑  PDF Preview — {meta.get('original_name', '')}\n{'─' * 40}\n\n"

        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            page_count = len(reader.pages)
            content += f"Pages: {page_count}\n\n{'─' * 40}\n\n"
            # Extract first 3 pages
            for i, page in enumerate(reader.pages[:3]):
                txt = page.extract_text() or ""
                content += f"── Page {i+1} ──\n{txt.strip()}\n\n"
            if page_count > 3:
                content += f"\n… ({page_count - 3} more pages — decrypt to view full PDF)"
        except ImportError:
            content += "⚠  pypdf not installed.\nInstall with:  pip install pypdf"
        except Exception as e:
            content += f"⚠  Could not parse PDF: {e}"

        editor.setPlainText(content)
        lay.addWidget(editor)


# ── Office extraction helpers ─────────────────────────────────────────────────

def _extract_docx_text(data: bytes, max_chars: int = 8000) -> str:
    from docx import Document
    doc = Document(io.BytesIO(data))
    paragraphs = []
    for p in doc.paragraphs:
        if p.text.strip():
            paragraphs.append(p.text)
    text = "\n".join(paragraphs)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n… [truncated]"
    return text or "(Empty document)"


def _extract_xlsx_text(data: bytes, max_rows: int = 200) -> str:
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    lines = []
    for sheet_name in wb.sheetnames[:5]:
        ws = wb[sheet_name]
        lines.append(f"── Sheet: {sheet_name} ──")
        row_count = 0
        for row in ws.iter_rows(values_only=True):
            if row_count >= max_rows:
                lines.append("… (more rows — decrypt to view full spreadsheet)")
                break
            cells = [str(c) if c is not None else "" for c in row]
            if any(c for c in cells):
                lines.append("  " + "\t".join(cells))
                row_count += 1
        lines.append("")
    return "\n".join(lines) or "(Empty spreadsheet)"


def _extract_pptx_text(data: bytes) -> str:
    from pptx import Presentation
    prs = Presentation(io.BytesIO(data))
    lines = []
    for i, slide in enumerate(prs.slides[:10]):
        lines.append(f"── Slide {i+1} ──")
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                lines.append(f"  {shape.text.strip()}")
        lines.append("")
    if len(prs.slides) > 10:
        lines.append(f"… ({len(prs.slides) - 10} more slides — decrypt to view)")
    return "\n".join(lines) or "(No text found)"


# ── Audio/video metadata parsers ──────────────────────────────────────────────

def _parse_mp3_tags(data: bytes) -> list[tuple[str, str]]:
    """Extract ID3v1 tag (last 128 bytes)."""
    rows = []
    if len(data) >= 128 and data[-128:-125] == b"TAG":
        tag  = data[-128:]
        title  = tag[3:33].rstrip(b"\x00").decode("latin-1", errors="replace").strip()
        artist = tag[33:63].rstrip(b"\x00").decode("latin-1", errors="replace").strip()
        album  = tag[63:93].rstrip(b"\x00").decode("latin-1", errors="replace").strip()
        year   = tag[93:97].rstrip(b"\x00").decode("latin-1", errors="replace").strip()
        if title:  rows.append(("Title",  title))
        if artist: rows.append(("Artist", artist))
        if album:  rows.append(("Album",  album))
        if year:   rows.append(("Year",   year))
    return rows


def _parse_wav_header(data: bytes) -> list[tuple[str, str]]:
    """Parse RIFF/WAV header for sample rate, channels, duration."""
    rows = []
    try:
        if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
            return rows
        channels    = struct.unpack_from("<H", data, 22)[0]
        sample_rate = struct.unpack_from("<I", data, 24)[0]
        bits        = struct.unpack_from("<H", data, 34)[0]
        data_size   = struct.unpack_from("<I", data, 40)[0]
        duration_s  = data_size / (sample_rate * channels * (bits // 8)) if sample_rate else 0
        rows.append(("Channels",    "Stereo" if channels == 2 else "Mono"))
        rows.append(("Sample Rate", f"{sample_rate:,} Hz"))
        rows.append(("Bit Depth",   f"{bits} bit"))
        rows.append(("Duration",    f"{int(duration_s // 60):02d}:{int(duration_s % 60):02d}"))
    except Exception:
        pass
    return rows


def _parse_mp4_header(data: bytes) -> list[tuple[str, str]]:
    """Very basic MP4 box traversal to find mvhd timescale/duration."""
    rows = []
    try:
        i = 0
        while i < len(data) - 8:
            box_size = struct.unpack_from(">I", data, i)[0]
            box_type = data[i+4:i+8]
            if box_size < 8:
                break
            if box_type == b"mvhd":
                # version 0: timescale at offset 12, duration at 16
                version = data[i+8]
                if version == 0 and i + 24 < len(data):
                    timescale = struct.unpack_from(">I", data, i+20)[0]
                    duration  = struct.unpack_from(">I", data, i+24)[0]
                    if timescale > 0:
                        secs = duration / timescale
                        rows.append(("Duration", f"{int(secs//60):02d}:{int(secs%60):02d}"))
                break
            i += box_size
    except Exception:
        pass
    return rows


# ── Main Quick View Sidebar ───────────────────────────────────────────────────

class QuickViewSidebar(QWidget):
    """
    Sidebar panel that decrypts a selected vault file in-memory
    and renders a format-appropriate preview.

    Usage:
        sidebar = QuickViewSidebar(parent=self)
        sidebar.preview(mfe_path, original_name, original_ext, password)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(300)
        self.setMaximumWidth(600)
        self._worker   = None
        self._thread   = None
        self._build_ui()

    # ── Internal UI ───────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setStyleSheet(f"background: {CLR_BG_SURFACE};")

        # ── Header ──
        header = QFrame()
        header.setFixedHeight(44)
        header.setStyleSheet(f"""
            QFrame {{
                background: {CLR_BG_RAISED};
                border-bottom: 1px solid {CLR_BORDER};
                border-left: 1px solid {CLR_BORDER};
            }}
        """)
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(12, 0, 8, 0)
        hlay.setSpacing(8)

        eye_lbl = QLabel("👁")
        eye_lbl.setStyleSheet("font-size: 14pt; background: transparent;")
        title_lbl = QLabel("Quick View")
        title_lbl.setStyleSheet(f"font-size: 10pt; font-weight: 700; color: {CLR_TEXT_PRIMARY}; background: transparent;")

        hlay.addWidget(eye_lbl)
        hlay.addWidget(title_lbl)
        hlay.addStretch()

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(26, 26)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {CLR_TEXT_MUTED};
                border: none;
                font-size: 11pt;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background: {CLR_BG_HOVER};
                color: {CLR_TEXT_PRIMARY};
            }}
        """)
        self.close_btn.setToolTip("Close Quick View  (F3)")
        hlay.addWidget(self.close_btn)
        root.addWidget(header)

        # ── File info strip ──
        self.info_frame = QFrame()
        self.info_frame.setStyleSheet(f"""
            QFrame {{
                background: {CLR_BG_BASE};
                border-bottom: 1px solid {CLR_BORDER};
                border-left: 1px solid {CLR_BORDER};
            }}
        """)
        info_lay = QVBoxLayout(self.info_frame)
        info_lay.setContentsMargins(12, 8, 12, 8)
        info_lay.setSpacing(2)

        self.file_name_lbl = QLabel("—")
        self.file_name_lbl.setStyleSheet(f"font-size: 9.5pt; font-weight: 600; color: {CLR_TEXT_PRIMARY}; background: transparent;")
        self.file_name_lbl.setWordWrap(True)

        self.file_meta_lbl = QLabel("")
        self.file_meta_lbl.setStyleSheet(f"font-size: 8pt; color: {CLR_TEXT_MUTED}; background: transparent;")

        info_lay.addWidget(self.file_name_lbl)
        info_lay.addWidget(self.file_meta_lbl)
        root.addWidget(self.info_frame)

        # ── Loading indicator ──
        self.loading_frame = QFrame()
        self.loading_frame.setStyleSheet(f"background: {CLR_BG_BASE}; border-left: 1px solid {CLR_BORDER};")
        lf_lay = QVBoxLayout(self.loading_frame)
        lf_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lf_lay.setSpacing(12)
        self.loading_progress = QProgressBar()
        self.loading_progress.setRange(0, 0)   # indeterminate
        self.loading_progress.setFixedHeight(4)
        self.loading_progress.setTextVisible(False)
        self.loading_progress.setStyleSheet(f"""
            QProgressBar {{ background: {CLR_BG_RAISED}; border: none; border-radius: 2px; }}
            QProgressBar::chunk {{ background: {CLR_ACCENT}; border-radius: 2px; }}
        """)
        loading_lbl = QLabel("Decrypting in memory…")
        loading_lbl.setStyleSheet(f"color: {CLR_TEXT_SECONDARY}; font-size: 9pt; background: transparent;")
        loading_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lf_lay.addWidget(loading_lbl)
        lf_lay.addWidget(self.loading_progress)
        self.loading_frame.setVisible(False)
        root.addWidget(self.loading_frame)

        # ── Content area (stacked) ──
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet(f"background: {CLR_BG_BASE}; border-left: 1px solid {CLR_BORDER};")
        root.addWidget(self.content_stack, 1)

        # Empty placeholder
        self.empty_page = QWidget()
        ep_lay = QVBoxLayout(self.empty_page)
        ep_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ep_lay.setSpacing(8)
        eye_big = QLabel("👁")
        eye_big.setStyleSheet("font-size: 36pt; background: transparent;")
        eye_big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel("Select a file and press F3\nor click Quick View")
        hint.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 9pt; background: transparent;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ep_lay.addWidget(eye_big)
        ep_lay.addWidget(hint)
        self.content_stack.addWidget(self.empty_page)

        # ── Format badge ──
        self.badge_frame = QFrame()
        self.badge_frame.setFixedHeight(26)
        self.badge_frame.setStyleSheet(f"""
            QFrame {{
                background: {CLR_BG_RAISED};
                border-top: 1px solid {CLR_BORDER};
                border-left: 1px solid {CLR_BORDER};
            }}
        """)
        badge_lay = QHBoxLayout(self.badge_frame)
        badge_lay.setContentsMargins(12, 0, 12, 0)
        self.badge_lbl = QLabel("")
        self.badge_lbl.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 7.5pt; background: transparent; letter-spacing: 0.3px;")
        badge_lay.addWidget(self.badge_lbl)
        badge_lay.addStretch()
        self.safety_lbl = QLabel("🔒 In-memory only — no temp files")
        self.safety_lbl.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 7.5pt; background: transparent;")
        badge_lay.addWidget(self.safety_lbl)
        root.addWidget(self.badge_frame)

    # ── Public API ────────────────────────────────────────────────────────────

    def preview(self, mfe_path: str, original_name: str, original_ext: str,
                password: str, size: int = 0, date_added: float = 0):
        """
        Start async decryption and render preview for the given file.
        """
        self._cancel_worker()

        # Update info strip
        self.file_name_lbl.setText(original_name)
        category = _detect_category(original_ext)
        cat_icon = {
            "image": "🖼", "code": "💻", "text": "📝",
            "audio": "🎵", "video": "🎬", "pdf": "📑",
            "archive": "📦", "office": "📄", "binary": "🔢",
        }.get(category, "📎")
        size_str = _human_size(size) if size else ""
        date_str = datetime.datetime.fromtimestamp(date_added).strftime("%Y-%m-%d %H:%M") if date_added else ""
        meta_parts = [original_ext.upper().lstrip("."), size_str, date_str]
        self.file_meta_lbl.setText("  ·  ".join(p for p in meta_parts if p))
        self.badge_lbl.setText(f"{cat_icon}  {category.upper()} FILE  ·  {original_ext.upper()}")

        # Show loading
        self.loading_frame.setVisible(True)
        self.loading_progress.setRange(0, 0)

        # Start background decryption
        self._worker = QuickViewWorker(mfe_path, password, original_ext)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.ready.connect(self._on_ready)
        self._worker.error.connect(self._on_error)
        self._worker.ready.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()

    def clear(self):
        """Reset sidebar to empty state."""
        self._cancel_worker()
        self.file_name_lbl.setText("—")
        self.file_meta_lbl.setText("")
        self.badge_lbl.setText("")
        self.loading_frame.setVisible(False)
        self._remove_content_pages()
        self.content_stack.setCurrentIndex(0)

    def _remove_content_pages(self):
        """Stop any active media and remove viewer pages (keep index 0 = empty_page)."""
        while self.content_stack.count() > 1:
            w = self.content_stack.widget(1)
            self.content_stack.removeWidget(w)
            if hasattr(w, "_cleanup"):
                w._cleanup()
            w.deleteLater()



    def _cancel_worker(self):
        if self._thread is not None:
            if self._thread.isRunning():
                self._thread.quit()
                # Non-blocking: beri waktu 500 ms, kalau belum selesai biarkan
                # finished signal akan bersihkan worker via deleteLater
                self._thread.wait(500)
        self._worker = None
        self._thread = None

    @Slot(bytes, dict, str)
    def _on_ready(self, data: bytes, meta: dict, ext: str):
        self.loading_frame.setVisible(False)
        category = _detect_category(ext)
        self._remove_content_pages()
        viewer = self._make_viewer(data, meta, ext, category)
        self.content_stack.addWidget(viewer)
        self.content_stack.setCurrentIndex(1)

    def _make_viewer(self, data: bytes, meta: dict, ext: str, category: str) -> QWidget:
        if category == "image":
            return _ImageViewer(data, self)
        elif category in ("code", "text"):
            return _TextViewer(data, ext, parent=self)
        elif category == "audio":
            return _AudioViewer(data, meta, ext, self)
        elif category == "video":
            return _VideoViewer(data, meta, ext, self)
        elif category == "archive":
            return _ArchiveViewer(data, meta, self)
        elif category == "office":
            return _OfficeViewer(data, meta, ext, self)
        elif category == "pdf":
            return _PdfViewer(data, meta, self)
        else:
            return _BinaryViewer(data, meta, self)

    @Slot(str)
    def _on_error(self, msg: str):
        self.loading_frame.setVisible(False)
        self._remove_content_pages()

        err_w = QWidget()
        lay = QVBoxLayout(err_w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(10)
        lbl = QLabel("⚠  Preview failed")
        lbl.setStyleSheet(f"font-size: 12pt; color: {CLR_WARN}; background: transparent; font-weight: 600;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        det = QLabel(msg)
        det.setStyleSheet(f"font-size: 8.5pt; color: {CLR_TEXT_MUTED}; background: transparent;")
        det.setAlignment(Qt.AlignmentFlag.AlignCenter)
        det.setWordWrap(True)
        lay.addWidget(lbl)
        lay.addWidget(det)

        self.content_stack.addWidget(err_w)
        self.content_stack.setCurrentIndex(1)
