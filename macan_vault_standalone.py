"""
macan_vault_standalone.py  –  Macan File Vault  (Standalone Edition)
======================================================================
Self-contained desktop application. Run directly:

    python macan_vault_standalone.py

Requirements:
    pip install PySide6 cryptography
"""

import os
import sys
import json
import time
import secrets
import struct
import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QListWidget,
    QListWidgetItem, QFrame, QDialog, QMessageBox, QProgressBar,
    QMenu, QInputDialog, QAbstractItemView, QSizePolicy, QStackedWidget,
    QStatusBar, QToolBar, QSplitter, QScrollArea, QGraphicsDropShadowEffect,
)
from PySide6.QtCore import (
    Qt, QTimer, QThread, Signal, QObject, Slot, QSettings, QSize,
    QMimeData, QPoint, QRect, QPropertyAnimation, QEasingCurve,
)
from PySide6.QtGui import (
    QIcon, QFont, QColor, QPalette, QPixmap, QAction, QKeySequence,
    QDragEnterEvent, QDropEvent, QFontDatabase, QPainter, QLinearGradient, 
)

try:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    PBKDF2HMAC = None
    AESGCM = None
    InvalidTag = Exception
    class _FakeHashes:
        @staticmethod
        def SHA256(): return None
    hashes = _FakeHashes()

# ─── Constants ────────────────────────────────────────────────────────────────
VAULT_MAGIC       = b"MCVT"
VAULT_VERSION     = 1
MFE_EXTENSION     = ".mfe"
MFK_EXTENSION     = ".mfk"
SALT_SIZE         = 16
NONCE_SIZE        = 12
PBKDF2_ITERATIONS = 310_000
KEY_LENGTH        = 32
MAX_ATTEMPTS      = 3
LOCKOUT_SECONDS   = 1800

APP_NAME          = "Macan File Vault"
APP_VERSION       = "1.2.0"
SETTINGS_ORG      = "MacanAngkasa"
SETTINGS_APP      = "MacanVault"

# ─── Design Tokens ────────────────────────────────────────────────────────────
# Refined dark enterprise palette — charcoal + steel blue accent
CLR_BG_BASE       = "#0f1117"   # near-black canvas
CLR_BG_SURFACE    = "#161b27"   # panel surface
CLR_BG_RAISED     = "#1e2535"   # elevated card / sidebar
CLR_BG_HOVER      = "#252d40"   # hover state
CLR_BORDER        = "#2a3348"   # subtle border
CLR_BORDER_FOCUS  = "#3d6aad"   # focused/accent border
CLR_ACCENT        = "#4a8fd1"   # primary blue accent
CLR_ACCENT_DEEP   = "#2e6baa"   # deeper blue
CLR_ACCENT_GLOW   = "#5ba3e8"   # highlight
CLR_SUCCESS       = "#2ecc71"
CLR_DANGER        = "#e74c3c"
CLR_WARN          = "#e67e22"
CLR_TEXT_PRIMARY  = "#e8edf5"
CLR_TEXT_SECONDARY= "#8a95a8"
CLR_TEXT_MUTED    = "#4d5669"
CLR_LOCKED        = "#e74c3c"
CLR_UNLOCKED      = "#2ecc71"

GLOBAL_STYLESHEET = f"""
/* ── Base ── */
QMainWindow, QWidget {{
    background: {CLR_BG_BASE};
    color: {CLR_TEXT_PRIMARY};
    font-family: "Segoe UI", "SF Pro Display", "Helvetica Neue", sans-serif;
    font-size: 10pt;
}}
QLabel {{ background: transparent; color: {CLR_TEXT_PRIMARY}; }}

/* ── Buttons ── */
QPushButton {{
    background: {CLR_BG_RAISED};
    color: {CLR_TEXT_PRIMARY};
    border: 1px solid {CLR_BORDER};
    border-radius: 6px;
    padding: 7px 18px;
    font-size: 9.5pt;
    font-weight: 500;
}}
QPushButton:hover {{
    background: {CLR_BG_HOVER};
    border-color: {CLR_BORDER_FOCUS};
}}
QPushButton:pressed {{
    background: {CLR_BG_BASE};
}}
QPushButton:disabled {{
    background: {CLR_BG_SURFACE};
    color: {CLR_TEXT_MUTED};
    border-color: {CLR_BORDER};
}}

/* ── Accent buttons ── */
QPushButton[accent="green"] {{
    background: #1a4a2e;
    border-color: #2e7d4f;
    color: #4cde8a;
}}
QPushButton[accent="green"]:hover {{
    background: #1f5a38;
    border-color: {CLR_SUCCESS};
}}
QPushButton[accent="blue"] {{
    background: #1a2f4a;
    border-color: {CLR_ACCENT_DEEP};
    color: {CLR_ACCENT_GLOW};
}}
QPushButton[accent="blue"]:hover {{
    background: #1f3a5a;
    border-color: {CLR_ACCENT};
}}
QPushButton[accent="red"] {{
    background: #3a1a1a;
    border-color: #7a3030;
    color: #e87070;
}}
QPushButton[accent="red"]:hover {{
    background: #4a2020;
    border-color: {CLR_DANGER};
}}
QPushButton[accent="orange"] {{
    background: #3a2810;
    border-color: #8a5820;
    color: #f0a050;
}}
QPushButton[accent="orange"]:hover {{
    background: #4a3218;
    border-color: {CLR_WARN};
}}

/* ── Inputs ── */
QLineEdit {{
    background: {CLR_BG_SURFACE};
    color: {CLR_TEXT_PRIMARY};
    border: 1px solid {CLR_BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 10pt;
    selection-background-color: {CLR_ACCENT_DEEP};
}}
QLineEdit:focus {{
    border-color: {CLR_BORDER_FOCUS};
    background: {CLR_BG_RAISED};
}}
QLineEdit::placeholder {{
    color: {CLR_TEXT_MUTED};
}}

/* ── List ── */
QListWidget {{
    background: {CLR_BG_SURFACE};
    border: 1px solid {CLR_BORDER};
    border-radius: 8px;
    color: {CLR_TEXT_PRIMARY};
    outline: none;
    font-size: 9.5pt;
}}
QListWidget::item {{
    padding: 10px 14px;
    border-bottom: 1px solid {CLR_BG_RAISED};
}}
QListWidget::item:hover {{
    background: {CLR_BG_HOVER};
}}
QListWidget::item:selected {{
    background: {CLR_ACCENT_DEEP};
    color: white;
    border-left: 3px solid {CLR_ACCENT};
}}

/* ── Scrollbar ── */
QScrollBar:vertical {{
    background: {CLR_BG_SURFACE};
    width: 8px;
    border-radius: 4px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {CLR_BORDER};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {CLR_TEXT_MUTED};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

/* ── Progress bar ── */
QProgressBar {{
    background: {CLR_BG_SURFACE};
    border: 1px solid {CLR_BORDER};
    border-radius: 4px;
    height: 6px;
    text-align: center;
    font-size: 8pt;
    color: {CLR_TEXT_SECONDARY};
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {CLR_ACCENT_DEEP}, stop:1 {CLR_ACCENT_GLOW});
    border-radius: 4px;
}}

/* ── Status bar ── */
QStatusBar {{
    background: {CLR_BG_SURFACE};
    border-top: 1px solid {CLR_BORDER};
    color: {CLR_TEXT_SECONDARY};
    font-size: 8.5pt;
    padding: 2px 8px;
}}
QStatusBar::item {{ border: none; }}

/* ── Toolbar ── */
QToolBar {{
    background: {CLR_BG_SURFACE};
    border-bottom: 1px solid {CLR_BORDER};
    spacing: 6px;
    padding: 4px 8px;
}}
QToolBar::separator {{
    background: {CLR_BORDER};
    width: 1px;
    margin: 6px 4px;
}}

/* ── Menu ── */
QMenu {{
    background: {CLR_BG_RAISED};
    border: 1px solid {CLR_BORDER};
    border-radius: 8px;
    padding: 4px 0;
    color: {CLR_TEXT_PRIMARY};
}}
QMenu::item {{
    padding: 8px 20px;
    font-size: 9.5pt;
}}
QMenu::item:selected {{
    background: {CLR_ACCENT_DEEP};
    color: white;
}}
QMenu::separator {{
    height: 1px;
    background: {CLR_BORDER};
    margin: 4px 0;
}}

/* ── Tooltip ── */
QToolTip {{
    background: {CLR_BG_RAISED};
    border: 1px solid {CLR_BORDER_FOCUS};
    color: {CLR_TEXT_PRIMARY};
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 9pt;
}}

/* ── Dialog ── */
QDialog {{
    background: {CLR_BG_SURFACE};
    color: {CLR_TEXT_PRIMARY};
}}

/* ── Message box ── */
QMessageBox {{
    background: {CLR_BG_SURFACE};
}}
QMessageBox QLabel {{
    color: {CLR_TEXT_PRIMARY};
    font-size: 10pt;
}}
QMessageBox QPushButton {{
    min-width: 80px;
}}

/* ── Splitter ── */
QSplitter::handle {{
    background: {CLR_BORDER};
}}
QSplitter::handle:hover {{
    background: {CLR_BORDER_FOCUS};
}}
"""


# ─── Crypto Utilities ─────────────────────────────────────────────────────────

def _derive_key(password: str, salt: bytes) -> bytes:
    if not CRYPTO_AVAILABLE or PBKDF2HMAC is None:
        raise RuntimeError("Library 'cryptography' not found. Install: pip install cryptography")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_LENGTH,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))

def _encrypt_data(key: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
    nonce = secrets.token_bytes(NONCE_SIZE)
    return nonce, AESGCM(key).encrypt(nonce, plaintext, None)

def _decrypt_data(key: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    return AESGCM(key).decrypt(nonce, ciphertext, None)


# ─── Vault Engine ─────────────────────────────────────────────────────────────

class VaultEngine:
    @staticmethod
    def encrypt_file(src_path: str, vault_dir: str, password: str) -> dict:
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("Library 'cryptography' not found. Install: pip install cryptography")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if not os.path.isfile(src_path):
            raise FileNotFoundError(f"File not found: {src_path}")

        salt = secrets.token_bytes(SALT_SIZE)
        key  = _derive_key(password, salt)
        original_name = os.path.basename(src_path)
        original_ext  = os.path.splitext(original_name)[1]
        file_size     = os.path.getsize(src_path)
        file_date     = os.path.getmtime(src_path)

        with open(src_path, "rb") as f:
            plaintext = f.read()

        meta = {"original_name": original_name, "original_ext": original_ext,
                "size": file_size, "date": file_date}
        meta_bytes = json.dumps(meta).encode("utf-8")
        nonce_meta, enc_meta = _encrypt_data(key, meta_bytes)
        nonce_data, enc_data = _encrypt_data(key, plaintext)

        meta_len = len(enc_meta)
        header   = VAULT_MAGIC + struct.pack(">H", VAULT_VERSION) + salt
        header  += nonce_meta + struct.pack(">I", meta_len) + enc_meta + nonce_data

        encrypted_name = secrets.token_hex(16) + MFE_EXTENSION
        out_path = os.path.join(vault_dir, encrypted_name)
        os.makedirs(vault_dir, exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(header + enc_data)

        return {"encrypted_name": encrypted_name, "original_name": original_name,
                "original_ext": original_ext, "size": file_size,
                "date": file_date, "added": time.time()}

    @staticmethod
    def decrypt_file(mfe_path: str, dest_dir: str, password: str) -> str:
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("Library 'cryptography' not found.")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters.")

        with open(mfe_path, "rb") as f:
            raw = f.read()

        offset = 0
        magic = raw[offset:offset+4]; offset += 4
        if magic != VAULT_MAGIC:
            raise ValueError("Not a Macan vault file (invalid .mfe).")
        _ver   = struct.unpack(">H", raw[offset:offset+2])[0]; offset += 2
        salt   = raw[offset:offset+SALT_SIZE]; offset += SALT_SIZE
        n_meta = raw[offset:offset+NONCE_SIZE]; offset += NONCE_SIZE
        m_len  = struct.unpack(">I", raw[offset:offset+4])[0]; offset += 4
        e_meta = raw[offset:offset+m_len]; offset += m_len
        n_data = raw[offset:offset+NONCE_SIZE]; offset += NONCE_SIZE
        e_data = raw[offset:]

        key = _derive_key(password, salt)
        meta = json.loads(_decrypt_data(key, n_meta, e_meta).decode("utf-8"))
        plaintext = _decrypt_data(key, n_data, e_data)

        original_name = meta.get("original_name", "decrypted_file")
        os.makedirs(dest_dir, exist_ok=True)
        out_path = os.path.join(dest_dir, original_name)
        base, ext = os.path.splitext(out_path)
        counter = 1
        while os.path.exists(out_path):
            out_path = f"{base}_{counter}{ext}"
            counter += 1
        with open(out_path, "wb") as f:
            f.write(plaintext)
        return out_path

    @staticmethod
    def export_key(password: str, salt: bytes) -> bytes:
        key = _derive_key(password, salt)
        nonce, enc_ver = _encrypt_data(key, b"MACAN_VAULT_KEY_OK")
        return b"MFKY" + salt + nonce + enc_ver

    @staticmethod
    def verify_key_file(key_data: bytes, password: str = None) -> tuple[bool, bytes]:
        try:
            if key_data[:4] != b"MFKY":
                return False, b""
            salt    = key_data[4:4+SALT_SIZE]
            nonce   = key_data[4+SALT_SIZE:4+SALT_SIZE+NONCE_SIZE]
            enc_ver = key_data[4+SALT_SIZE+NONCE_SIZE:]
            if password:
                key = _derive_key(password, salt)
                plain = _decrypt_data(key, nonce, enc_ver)
                return (True, salt) if plain == b"MACAN_VAULT_KEY_OK" else (False, b"")
            return True, salt
        except Exception:
            return False, b""


# ─── Worker Thread ────────────────────────────────────────────────────────────

class VaultWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(bool, str)

    def __init__(self, task, **kwargs):
        super().__init__()
        self.task   = task
        self.kwargs = kwargs
        self._abort = False

    def abort(self):
        self._abort = True

    @Slot()
    def run(self):
        try:
            if self.task == "encrypt":
                self._run_encrypt()
            elif self.task == "decrypt":
                self._run_decrypt()
        except Exception as e:
            self.finished.emit(False, str(e))

    def _run_encrypt(self):
        files     = self.kwargs["files"]
        vault_dir = self.kwargs["vault_dir"]
        password  = self.kwargs["password"]
        index     = self.kwargs.get("index", {})
        results   = []
        total     = len(files)
        for i, fp in enumerate(files):
            if self._abort:
                self.finished.emit(False, "Operation cancelled by user.")
                return
            self.progress.emit(int(i / total * 100), f"Encrypting  {os.path.basename(fp)}")
            try:
                info = VaultEngine.encrypt_file(fp, vault_dir, password)
                index[info["encrypted_name"]] = info
                results.append(info)
                # Secure wipe original
                try:
                    sz = os.path.getsize(fp)
                    with open(fp, "wb") as f:
                        f.write(secrets.token_bytes(sz))
                    os.remove(fp)
                except Exception:
                    self.progress.emit(int(i / total * 100),
                                       f"Warning: could not delete original — {os.path.basename(fp)}")
            except Exception as e:
                self.finished.emit(False, f"Failed to encrypt '{os.path.basename(fp)}':\n{e}")
                return
            QApplication.processEvents()
        self.progress.emit(100, "Done.")
        self.finished.emit(True, json.dumps(results))

    def _run_decrypt(self):
        files    = self.kwargs["files"]
        dest_dir = self.kwargs["dest_dir"]
        password = self.kwargs["password"]
        results  = []
        total    = len(files)
        for i, fp in enumerate(files):
            if self._abort:
                self.finished.emit(False, "Operation cancelled.")
                return
            self.progress.emit(int(i / total * 100), f"Decrypting  {os.path.basename(fp)}")
            try:
                out = VaultEngine.decrypt_file(fp, dest_dir, password)
                results.append(out)
            except Exception as e:
                self.finished.emit(False, f"Failed to decrypt:\n{e}")
                return
            QApplication.processEvents()
        self.progress.emit(100, "Done.")
        self.finished.emit(True, "\n".join(results))


# ─── Vault Manager ────────────────────────────────────────────────────────────

class VaultManager:
    def __init__(self):
        self._settings        = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self._failed_attempts = int(self._settings.value("failed_attempts", 0))
        self._lockout_until   = float(self._settings.value("lockout_until", 0.0))
        self._vault_dir       = self._settings.value("vault_dir", "")
        self._index: dict     = {}
        self._unlocked        = False

    @property
    def is_locked_out(self) -> bool:
        return time.time() < self._lockout_until

    @property
    def lockout_remaining_sec(self) -> int:
        return max(0, int(self._lockout_until - time.time()))

    def record_failed_attempt(self):
        self._failed_attempts += 1
        if self._failed_attempts >= MAX_ATTEMPTS:
            self._lockout_until   = time.time() + LOCKOUT_SECONDS
            self._failed_attempts = 0
        self._settings.setValue("failed_attempts", self._failed_attempts)
        self._settings.setValue("lockout_until",   self._lockout_until)

    def reset_attempts(self):
        self._failed_attempts = 0
        self._lockout_until   = 0.0
        self._settings.setValue("failed_attempts", 0)
        self._settings.setValue("lockout_until",   0.0)

    @property
    def vault_dir(self) -> str:
        return self._vault_dir

    @vault_dir.setter
    def vault_dir(self, path: str):
        self._vault_dir = path
        self._settings.setValue("vault_dir", path)

    def _index_path(self) -> str:
        return os.path.join(self._vault_dir, "_vault_index.mfi")

    def save_index(self, password: str):
        if not self._vault_dir:
            return
        data = json.dumps(self._index).encode("utf-8")
        salt = secrets.token_bytes(SALT_SIZE)
        key  = _derive_key(password, salt)
        nonce, enc = _encrypt_data(key, data)
        with open(self._index_path(), "wb") as f:
            f.write(b"MFXI" + salt + nonce + enc)

    def load_index(self, password: str) -> bool:
        path = self._index_path()
        if not os.path.exists(path):
            self._index = {}
            return True
        try:
            with open(path, "rb") as f:
                raw = f.read()
            if raw[:4] != b"MFXI":
                return False
            salt  = raw[4:4+SALT_SIZE]
            nonce = raw[4+SALT_SIZE:4+SALT_SIZE+NONCE_SIZE]
            enc   = raw[4+SALT_SIZE+NONCE_SIZE:]
            key   = _derive_key(password, salt)
            plain = _decrypt_data(key, nonce, enc)
            self._index = json.loads(plain.decode("utf-8"))
            return True
        except Exception:
            return False

    @property
    def index(self) -> dict:
        return self._index

    def add_entry(self, info: dict):
        self._index[info["encrypted_name"]] = info

    def remove_entry(self, encrypted_name: str):
        self._index.pop(encrypted_name, None)

    @property
    def is_unlocked(self) -> bool:
        return self._unlocked

    def set_unlocked(self, value: bool):
        self._unlocked = value


# ─── Password Dialog ──────────────────────────────────────────────────────────

class VaultPasswordDialog(QDialog):
    def __init__(self, manager: VaultManager, mode="unlock", parent=None):
        super().__init__(parent)
        self.manager  = manager
        self.mode     = mode
        self.password = ""
        self.key_data : bytes = b""
        self._use_key = False
        self._build_ui()

    def _build_ui(self):
        title = "Unlock Vault" if self.mode == "unlock" else "Create New Vault"
        self.setWindowTitle(f"Macan File Vault — {title}")
        self.setMinimumWidth(460)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header band
        header = QFrame()
        header.setFixedHeight(72)
        header.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {CLR_BG_RAISED}, stop:1 #1a2540);
                border-bottom: 1px solid {CLR_BORDER};
            }}
        """)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(24, 0, 24, 0)

        lock_icon = QLabel("🔐")
        lock_icon.setStyleSheet("font-size: 26pt; background: transparent;")
        h_lay.addWidget(lock_icon)

        h_text = QVBoxLayout()
        h_text.setSpacing(2)
        title_lbl = QLabel("Macan File Vault")
        title_lbl.setStyleSheet(f"font-size: 13pt; font-weight: 700; color: {CLR_TEXT_PRIMARY}; background: transparent;")
        sub_lbl = QLabel(title)
        sub_lbl.setStyleSheet(f"font-size: 9pt; color: {CLR_TEXT_SECONDARY}; background: transparent;")
        h_text.addWidget(title_lbl)
        h_text.addWidget(sub_lbl)
        h_lay.addLayout(h_text)
        h_lay.addStretch()
        layout.addWidget(header)

        # Body
        body = QWidget()
        body.setStyleSheet(f"background: {CLR_BG_SURFACE};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(28, 24, 28, 24)
        body_lay.setSpacing(14)

        # Lockout state
        if self.manager.is_locked_out:
            mins = self.manager.lockout_remaining_sec // 60
            secs = self.manager.lockout_remaining_sec % 60
            warn = QLabel(f"⛔  Too many failed attempts.\nPlease try again in {mins:02d}:{secs:02d}.")
            warn.setStyleSheet(f"color: {CLR_DANGER}; font-weight: 600; font-size: 10pt; background: transparent;")
            warn.setAlignment(Qt.AlignmentFlag.AlignCenter)
            body_lay.addWidget(warn)
            self._lockout_label = warn
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick_lockout)
            self._timer.start(1000)
            btn = QPushButton("Close")
            btn.clicked.connect(self.reject)
            body_lay.addWidget(btn)
            layout.addWidget(body)
            return

        # Password field
        pw_lbl = QLabel("Vault Password" if self.mode == "unlock" else "Create Password  (minimum 8 characters)")
        pw_lbl.setStyleSheet(f"color: {CLR_TEXT_SECONDARY}; font-size: 8.5pt; font-weight: 600; background: transparent; letter-spacing: 0.5px;")
        body_lay.addWidget(pw_lbl)

        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_input.setPlaceholderText("Enter password…")
        self.pw_input.setFixedHeight(40)
        self.pw_input.returnPressed.connect(self._try_accept)
        body_lay.addWidget(self.pw_input)

        if self.mode == "setup":
            pw2_lbl = QLabel("Confirm Password")
            pw2_lbl.setStyleSheet(f"color: {CLR_TEXT_SECONDARY}; font-size: 8.5pt; font-weight: 600; background: transparent;")
            body_lay.addWidget(pw2_lbl)
            self.pw2_input = QLineEdit()
            self.pw2_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.pw2_input.setPlaceholderText("Repeat password…")
            self.pw2_input.setFixedHeight(40)
            self.pw2_input.returnPressed.connect(self._try_accept)
            body_lay.addWidget(self.pw2_input)
        else:
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet(f"background: {CLR_BORDER}; max-height: 1px;")
            body_lay.addWidget(sep)
            key_btn = QPushButton("📂   Load Key File  (.mfk)")
            key_btn.setProperty("accent", "blue")
            key_btn.setFixedHeight(36)
            key_btn.clicked.connect(self._load_key_file)
            body_lay.addWidget(key_btn)

        # Error / info label
        self.err_label = QLabel("")
        self.err_label.setStyleSheet(f"color: {CLR_DANGER}; font-size: 9pt; background: transparent;")
        self.err_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body_lay.addWidget(self.err_label)

        if self.manager._failed_attempts > 0:
            rem = MAX_ATTEMPTS - self.manager._failed_attempts
            self.err_label.setText(f"⚠  {rem} attempt(s) remaining before lockout.")

        body_lay.addSpacing(4)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(38)
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("Unlock Vault" if self.mode == "unlock" else "Create Vault")
        ok_btn.setFixedHeight(38)
        ok_btn.setProperty("accent", "blue")
        ok_btn.clicked.connect(self._try_accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        body_lay.addLayout(btn_row)

        layout.addWidget(body)
        self.pw_input.setFocus()

    def _tick_lockout(self):
        if not self.manager.is_locked_out:
            self._timer.stop()
            self._lockout_label.setText("✅  Lockout ended. You may close and try again.")
            self._lockout_label.setStyleSheet(f"color: {CLR_SUCCESS}; font-weight: 600; background: transparent;")
        else:
            m = self.manager.lockout_remaining_sec // 60
            s = self.manager.lockout_remaining_sec % 60
            self._lockout_label.setText(f"⛔  Too many failed attempts.\nPlease try again in {m:02d}:{s:02d}.")

    def _load_key_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Key File", "", f"Macan Key File (*{MFK_EXTENSION})")
        if not path:
            return
        try:
            with open(path, "rb") as f:
                data = f.read()
            ok, _ = VaultEngine.verify_key_file(data)
            if ok:
                self.key_data = data
                self._use_key = True
                self.err_label.setStyleSheet(f"color: {CLR_SUCCESS}; font-size: 9pt; background: transparent;")
                self.err_label.setText("✅  Key file verified. Click Unlock to continue.")
            else:
                self.err_label.setStyleSheet(f"color: {CLR_DANGER}; font-size: 9pt; background: transparent;")
                self.err_label.setText("❌  Invalid key file.")
        except Exception as e:
            self.err_label.setStyleSheet(f"color: {CLR_DANGER}; font-size: 9pt; background: transparent;")
            self.err_label.setText(f"❌  Could not read key file: {e}")

    def _try_accept(self):
        if self.manager.is_locked_out:
            return
        if self._use_key:
            self.password = "__KEY__"
            self.accept()
            return
        pw = self.pw_input.text()
        if len(pw) < 8:
            self.err_label.setStyleSheet(f"color: {CLR_DANGER}; font-size: 9pt; background: transparent;")
            self.err_label.setText("⚠  Password must be at least 8 characters.")
            return
        if self.mode == "setup" and pw != self.pw2_input.text():
            self.err_label.setStyleSheet(f"color: {CLR_DANGER}; font-size: 9pt; background: transparent;")
            self.err_label.setText("⚠  Passwords do not match.")
            return
        self.password = pw
        self.accept()


# ─── Locked Landing Page ──────────────────────────────────────────────────────

class LockedPage(QWidget):
    open_vault_requested  = Signal()
    create_vault_requested = Signal()
    choose_dir_requested  = Signal()

    def __init__(self, manager: VaultManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self._build_ui()

    def _build_ui(self):
        self.setAcceptDrops(False)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(0)
        lay.setContentsMargins(60, 40, 60, 40)

        # Shield icon
        icon_lbl = QLabel()
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("background: transparent;")
        _shield_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "macan_shield.png")
        if hasattr(sys, "_MEIPASS"):
            _shield_path = os.path.join(sys._MEIPASS, "macan_shield.png")
        _shield_pix = QPixmap(_shield_path)
        if not _shield_pix.isNull():
            icon_lbl.setPixmap(_shield_pix.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            icon_lbl.setText("🛡")
            icon_lbl.setStyleSheet("font-size: 72pt; background: transparent;")

        # App name
        name_lbl = QLabel("Macan File Vault")
        name_lbl.setStyleSheet(f"""
            font-size: 22pt; font-weight: 700;
            color: {CLR_TEXT_PRIMARY}; background: transparent;
            letter-spacing: -0.5px;
        """)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        tagline = QLabel("AES-256-GCM · PBKDF2-HMAC-SHA256 · Zero plaintext on disk")
        tagline.setStyleSheet(f"font-size: 9pt; color: {CLR_TEXT_MUTED}; background: transparent; letter-spacing: 0.3px;")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(icon_lbl)
        lay.addSpacing(12)
        lay.addWidget(name_lbl)
        lay.addSpacing(6)
        lay.addWidget(tagline)
        lay.addSpacing(32)

        # Vault location card
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {CLR_BG_RAISED};
                border: 1px solid {CLR_BORDER};
                border-radius: 10px;
            }}
        """)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(20, 16, 20, 16)
        card_lay.setSpacing(10)

        dir_hdr = QLabel("VAULT LOCATION")
        dir_hdr.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 8pt; font-weight: 700; background: transparent; letter-spacing: 1px;")

        self.dir_label = QLabel(self.manager.vault_dir or "No vault selected")
        self.dir_label.setStyleSheet(f"""
            color: {CLR_ACCENT if self.manager.vault_dir else CLR_TEXT_MUTED};
            font-size: 9.5pt; background: transparent;
            font-family: "Consolas", "Fira Code", monospace;
        """)
        self.dir_label.setWordWrap(True)

        choose_btn = QPushButton("Browse…")
        choose_btn.setFixedWidth(100)
        choose_btn.clicked.connect(self.choose_dir_requested)

        dir_row = QHBoxLayout()
        dir_row.addWidget(self.dir_label, 1)
        dir_row.addWidget(choose_btn)

        card_lay.addWidget(dir_hdr)
        card_lay.addLayout(dir_row)
        lay.addWidget(card)
        lay.addSpacing(24)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        btn_new = QPushButton("  Create New Vault")
        btn_new.setFixedHeight(42)
        btn_new.setProperty("accent", "blue")
        btn_new.clicked.connect(self.create_vault_requested)

        btn_open = QPushButton("  Unlock Vault")
        btn_open.setFixedHeight(42)
        btn_open.setProperty("accent", "green")
        btn_open.clicked.connect(self.open_vault_requested)

        btn_row.addWidget(btn_new)
        btn_row.addWidget(btn_open)
        lay.addLayout(btn_row)
        lay.addSpacing(24)

        # Feature pills
        pills_row = QHBoxLayout()
        pills_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pills_row.setSpacing(10)
        for text in ["AES-256-GCM", "Randomised filenames", "Secure wipe", "Brute-force lockout"]:
            pill = QLabel(text)
            pill.setStyleSheet(f"""
                background: {CLR_BG_RAISED};
                color: {CLR_TEXT_SECONDARY};
                border: 1px solid {CLR_BORDER};
                border-radius: 12px;
                padding: 4px 12px;
                font-size: 8.5pt;
            """)
            pills_row.addWidget(pill)
        lay.addLayout(pills_row)

    def refresh_dir_label(self):
        if self.manager.vault_dir:
            self.dir_label.setText(self.manager.vault_dir)
            self.dir_label.setStyleSheet(f"color: {CLR_ACCENT}; font-size: 9.5pt; background: transparent; font-family: 'Consolas', 'Fira Code', monospace;")
        else:
            self.dir_label.setText("No vault selected")
            self.dir_label.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 9.5pt; background: transparent;")


# ─── File List Item ───────────────────────────────────────────────────────────

def _human_size(b: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


# ─── Unlocked Main Panel ──────────────────────────────────────────────────────

class UnlockedPage(QWidget):
    lock_requested = Signal()
    back_requested = Signal()

    def __init__(self, manager: VaultManager, parent=None):
        super().__init__(parent)
        self.manager           = manager
        self._current_password = ""
        self._worker           = None
        self._thread           = None
        self.setAcceptDrops(True)
        self._build_ui()

    def set_password(self, pw: str):
        self._current_password = pw

    # ── UI ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Toolbar strip ──────────────────────────────────────────────────
        toolbar = QFrame()
        toolbar.setFixedHeight(52)
        toolbar.setStyleSheet(f"background: {CLR_BG_RAISED}; border-bottom: 1px solid {CLR_BORDER};")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(16, 0, 16, 0)
        tb.setSpacing(8)

        self.btn_back = QPushButton("  ← Back")
        self.btn_back.setFixedHeight(34)
        self.btn_back.setToolTip("Return to the home screen")
        self.btn_back.clicked.connect(self.back_requested)

        self.btn_encrypt = QPushButton("  Encrypt Files")
        self.btn_encrypt.setProperty("accent", "green")
        self.btn_encrypt.setFixedHeight(34)
        self.btn_encrypt.setToolTip("Add files to vault (Ctrl+E)")
        self.btn_encrypt.clicked.connect(self._encrypt_files)

        self.btn_decrypt = QPushButton("  Decrypt")
        self.btn_decrypt.setProperty("accent", "blue")
        self.btn_decrypt.setFixedHeight(34)
        self.btn_decrypt.setToolTip("Decrypt selected files (Ctrl+D)")
        self.btn_decrypt.clicked.connect(self._decrypt_selected)

        self.btn_delete = QPushButton("  Remove")
        self.btn_delete.setProperty("accent", "red")
        self.btn_delete.setFixedHeight(34)
        self.btn_delete.setToolTip("Securely remove selected files from vault (Del)")
        self.btn_delete.clicked.connect(self._delete_selected)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"background: {CLR_BORDER}; max-width: 1px;")
        sep.setFixedHeight(24)

        self.btn_export_key = QPushButton("  Export Key")
        self.btn_export_key.setFixedHeight(34)
        self.btn_export_key.setToolTip("Export a .mfk key file for backup")
        self.btn_export_key.clicked.connect(self._export_key)

        self.btn_lock = QPushButton("  Lock")
        self.btn_lock.setProperty("accent", "orange")
        self.btn_lock.setFixedHeight(34)
        self.btn_lock.setToolTip("Lock the vault and clear session (Ctrl+L)")
        self.btn_lock.clicked.connect(self.lock_requested)

        tb.addWidget(self.btn_back)

        sep0 = QFrame()
        sep0.setFrameShape(QFrame.Shape.VLine)
        sep0.setStyleSheet(f"background: {CLR_BORDER}; max-width: 1px;")
        sep0.setFixedHeight(24)
        tb.addWidget(sep0)

        tb.addWidget(self.btn_encrypt)
        tb.addWidget(self.btn_decrypt)
        tb.addWidget(self.btn_delete)
        tb.addWidget(sep)
        tb.addStretch()
        tb.addWidget(self.btn_export_key)
        tb.addWidget(self.btn_lock)
        root.addWidget(toolbar)

        # ── Progress strip ──────────────────────────────────────────────────
        self.progress_frame = QFrame()
        self.progress_frame.setFixedHeight(38)
        self.progress_frame.setStyleSheet(f"background: {CLR_BG_SURFACE}; border-bottom: 1px solid {CLR_BORDER};")
        pf_lay = QHBoxLayout(self.progress_frame)
        pf_lay.setContentsMargins(16, 0, 16, 0)
        pf_lay.setSpacing(12)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet(f"color: {CLR_TEXT_SECONDARY}; font-size: 8.5pt; background: transparent;")
        pf_lay.addWidget(self.progress_bar)
        pf_lay.addWidget(self.progress_label)
        self.progress_frame.setVisible(False)
        root.addWidget(self.progress_frame)

        # ── File list area ──────────────────────────────────────────────────
        list_area = QWidget()
        list_area.setStyleSheet(f"background: {CLR_BG_BASE};")
        list_lay = QVBoxLayout(list_area)
        list_lay.setContentsMargins(16, 16, 16, 8)
        list_lay.setSpacing(10)

        # List header
        hdr_row = QHBoxLayout()
        files_lbl = QLabel("ENCRYPTED FILES")
        files_lbl.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 8pt; font-weight: 700; background: transparent; letter-spacing: 1px;")
        self.count_lbl = QLabel("0 items")
        self.count_lbl.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 8.5pt; background: transparent;")
        hdr_row.addWidget(files_lbl)
        hdr_row.addStretch()
        hdr_row.addWidget(self.count_lbl)
        list_lay.addLayout(hdr_row)

        # Drop hint label (shown when empty)
        self.drop_hint = QLabel("Drop files here or click  Encrypt Files  to add")
        self.drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_hint.setStyleSheet(f"""
            color: {CLR_TEXT_MUTED};
            font-size: 10pt;
            background: transparent;
            padding: 40px;
        """)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._context_menu)
        self.file_list.setAlternatingRowColors(False)

        # Column headers row
        col_hdr = QFrame()
        col_hdr.setStyleSheet(f"background: {CLR_BG_RAISED}; border: 1px solid {CLR_BORDER}; border-radius: 6px;")
        col_hdr_lay = QHBoxLayout(col_hdr)
        col_hdr_lay.setContentsMargins(14, 6, 14, 6)
        col_hdr_lay.setSpacing(0)
        for label, stretch in [("Filename", 3), ("Type", 1), ("Size", 1), ("Date Added", 2)]:
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 8pt; font-weight: 700; background: transparent; letter-spacing: 0.5px;")
            col_hdr_lay.addWidget(lbl, stretch)

        list_lay.addWidget(col_hdr)
        list_lay.addWidget(self.drop_hint)
        list_lay.addWidget(self.file_list)
        root.addWidget(list_area, 1)

        # ── Info / status strip ─────────────────────────────────────────────
        info_strip = QFrame()
        info_strip.setFixedHeight(28)
        info_strip.setStyleSheet(f"background: {CLR_BG_SURFACE}; border-top: 1px solid {CLR_BORDER};")
        is_lay = QHBoxLayout(info_strip)
        is_lay.setContentsMargins(16, 0, 16, 0)
        self.info_lbl = QLabel("Vault unlocked")
        self.info_lbl.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 8.5pt; background: transparent;")
        self.vault_dir_lbl = QLabel("")
        self.vault_dir_lbl.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 8pt; background: transparent; font-family: 'Consolas', monospace;")
        is_lay.addWidget(self.info_lbl)
        is_lay.addStretch()
        is_lay.addWidget(self.vault_dir_lbl)
        root.addWidget(info_strip)

    # ── Drag & Drop ──────────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(f"QWidget {{ border: 2px solid {CLR_ACCENT}; }}")

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("")
        files = [u.toLocalFile() for u in event.mimeData().urls() if os.path.isfile(u.toLocalFile())]
        if files and self.manager.is_unlocked:
            self._run_worker(task="encrypt", files=files,
                             vault_dir=self.manager.vault_dir,
                             password=self._current_password,
                             index=self.manager.index)

    # ── Actions ──────────────────────────────────────────────────────────────

    def _encrypt_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files to Encrypt")
        if not files:
            return
        self._run_worker(task="encrypt", files=files,
                         vault_dir=self.manager.vault_dir,
                         password=self._current_password,
                         index=self.manager.index)

    def _decrypt_selected(self):
        selected = self.file_list.selectedItems()
        if not selected:
            QMessageBox.information(self, "No Selection", "Select one or more files to decrypt.")
            return
        dest = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if not dest:
            return
        mfe_paths = [os.path.join(self.manager.vault_dir,
                     item.data(Qt.ItemDataRole.UserRole)) for item in selected]
        self._run_worker(task="decrypt", files=mfe_paths, dest_dir=dest,
                         password=self._current_password)

    def _delete_selected(self):
        selected = self.file_list.selectedItems()
        if not selected:
            QMessageBox.information(self, "No Selection", "Select one or more files to remove.")
            return
        reply = QMessageBox.question(
            self, "Confirm Removal",
            f"Permanently and securely delete {len(selected)} file(s) from the vault?\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for item in selected:
            enc_name = item.data(Qt.ItemDataRole.UserRole)
            mfe_path = os.path.join(self.manager.vault_dir, enc_name)
            try:
                if os.path.exists(mfe_path):
                    sz = os.path.getsize(mfe_path)
                    with open(mfe_path, "wb") as f:
                        f.write(secrets.token_bytes(sz))
                    os.remove(mfe_path)
            except Exception as e:
                QMessageBox.warning(self, "Delete Failed", f"Could not delete {enc_name}:\n{e}")
                continue
            self.manager.remove_entry(enc_name)
        self.manager.save_index(self._current_password)
        self.refresh_list()

    def _export_key(self):
        if not self._current_password or len(self._current_password) < 8:
            QMessageBox.warning(self, "Export Key", "Vault must be unlocked with a valid password.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Key File",
            os.path.join(os.path.expanduser("~"), f"macan_vault_{int(time.time())}{MFK_EXTENSION}"),
            f"Macan Key File (*{MFK_EXTENSION})")
        if not path:
            return
        salt    = secrets.token_bytes(SALT_SIZE)
        key_raw = VaultEngine.export_key(self._current_password, salt)
        try:
            with open(path, "wb") as f:
                f.write(key_raw)
            QMessageBox.information(self, "Key File Saved",
                f"Key file saved to:\n{path}\n\n"
                "⚠️  Store this file securely. Anyone with the key file and your password can unlock the vault.")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Could not save key file:\n{e}")

    def _context_menu(self, pos):
        item = self.file_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_dec = menu.addAction("🔓  Decrypt selected")
        act_del = menu.addAction("🗑  Remove from vault")
        act = menu.exec(self.file_list.mapToGlobal(pos))
        if act == act_dec:
            self._decrypt_selected()
        elif act == act_del:
            self._delete_selected()

    # ── Worker ───────────────────────────────────────────────────────────────

    def _run_worker(self, task, **kwargs):
        self._worker = VaultWorker(task, **kwargs)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self.progress_bar.setValue(0)
        self.progress_frame.setVisible(True)
        self._set_buttons_enabled(False)
        self._thread.start()

    def _set_buttons_enabled(self, enabled: bool):
        for btn in [self.btn_encrypt, self.btn_decrypt, self.btn_delete, self.btn_export_key]:
            btn.setEnabled(enabled)

    @Slot(int, str)
    def _on_progress(self, pct: int, msg: str):
        self.progress_bar.setValue(pct)
        self.progress_label.setText(msg)

    @Slot(bool, str)
    def _on_finished(self, success: bool, message: str):
        self.progress_frame.setVisible(False)
        self._set_buttons_enabled(True)
        if success:
            if self._worker and self._worker.task == "encrypt":
                self.manager.save_index(self._current_password)
                added = len(json.loads(message))
                QMessageBox.information(self, "Encryption Complete",
                    f"✅  {added} file(s) encrypted and stored in vault.\n"
                    "🗑  Original file(s) have been securely wiped from disk.")
            elif self._worker and self._worker.task == "decrypt":
                paths = [p for p in message.split("\n") if p.strip()]
                QMessageBox.information(self, "Decryption Complete",
                    f"✅  {len(paths)} file(s) decrypted successfully.")
        else:
            QMessageBox.critical(self, "Operation Failed", message)
        self.refresh_list()
        self._worker = None
        self._thread = None

    # ── List refresh ─────────────────────────────────────────────────────────

    def refresh_list(self):
        self.file_list.clear()
        index = self.manager.index
        for enc_name, info in sorted(index.items(),
                                     key=lambda x: x[1].get("added", 0), reverse=True):
            orig     = info.get("original_name", "?")
            ext      = info.get("original_ext", "")
            size     = info.get("size", 0)
            added    = info.get("added", 0)
            date_str = datetime.datetime.fromtimestamp(added).strftime("%Y-%m-%d  %H:%M") if added else "—"
            size_str = _human_size(size)

            # Build a padded display line (tabular feel)
            name_part = orig[:46] + "…" if len(orig) > 48 else orig
            ext_part  = (ext.lstrip(".").upper() or "—")[:8]
            display   = f"{name_part:<50}  {ext_part:<8}  {size_str:<10}  {date_str}"

            item = QListWidgetItem(f"  🔒  {display}")
            item.setData(Qt.ItemDataRole.UserRole, enc_name)
            item.setToolTip(f"Encrypted name: {enc_name}\nOriginal: {orig}\nSize: {size_str}\nAdded: {date_str}")
            self.file_list.addItem(item)

        count = len(index)
        has_items = count > 0
        self.file_list.setVisible(has_items)
        self.drop_hint.setVisible(not has_items)
        self.count_lbl.setText(f"{count} item{'s' if count != 1 else ''}")
        self.info_lbl.setText(f"{count} encrypted file{'s' if count != 1 else ''} in vault")
        self.vault_dir_lbl.setText(self.manager.vault_dir)

    def cleanup(self):
        if self._thread and self._thread.isRunning():
            if self._worker:
                self._worker.abort()
            self._thread.quit()
            self._thread.wait(3000)
        self._current_password = ""


# ─── Main Window ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.manager  = VaultManager()
        self._current_password = ""

        self.setWindowTitle(f"Macan File Vault  {APP_VERSION}")
        self.setMinimumSize(860, 560)
        self.resize(1100, 680)
        icon_path = "macan_shield.ico"
        if hasattr(sys, "_MEIPASS"):
            icon_path = os.path.join(sys._MEIPASS, icon_path)
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Restore geometry
        settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        geom = settings.value("window_geometry")
        if geom:
            self.restoreGeometry(geom)

        self._build_ui()
        self._build_menu()
        self._build_statusbar()

        # Check crypto
        if not CRYPTO_AVAILABLE:
            self._set_status("⚠  cryptography library not found — install with: pip install cryptography", CLR_DANGER)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # Page 0 — locked
        self.locked_page = LockedPage(self.manager)
        self.locked_page.open_vault_requested.connect(self._unlock_vault)
        self.locked_page.create_vault_requested.connect(self._create_new_vault)
        self.locked_page.choose_dir_requested.connect(self._choose_vault_dir)
        self.stack.addWidget(self.locked_page)

        # Page 1 — unlocked
        self.vault_page = UnlockedPage(self.manager)
        self.vault_page.lock_requested.connect(self._lock_vault)
        self.vault_page.back_requested.connect(self._lock_vault)
        self.stack.addWidget(self.vault_page)

        self.stack.setCurrentIndex(0)

    def _build_menu(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")
        act_new   = QAction("New Vault…", self)
        act_new.setShortcut(QKeySequence("Ctrl+N"))
        act_new.triggered.connect(self._create_new_vault)

        act_open  = QAction("Open Vault…", self)
        act_open.setShortcut(QKeySequence("Ctrl+O"))
        act_open.triggered.connect(self._choose_vault_dir)

        act_lock  = QAction("Lock Vault", self)
        act_lock.setShortcut(QKeySequence("Ctrl+L"))
        act_lock.triggered.connect(self._lock_vault)

        act_quit  = QAction("Quit", self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)

        file_menu.addAction(act_new)
        file_menu.addAction(act_open)
        file_menu.addSeparator()
        file_menu.addAction(act_lock)
        file_menu.addSeparator()
        file_menu.addAction(act_quit)

        # Vault menu
        vault_menu = menubar.addMenu("&Vault")
        act_enc = QAction("Encrypt Files…", self)
        act_enc.setShortcut(QKeySequence("Ctrl+E"))
        act_enc.triggered.connect(lambda: self.vault_page._encrypt_files() if self.manager.is_unlocked else None)

        act_dec = QAction("Decrypt Selected", self)
        act_dec.setShortcut(QKeySequence("Ctrl+D"))
        act_dec.triggered.connect(lambda: self.vault_page._decrypt_selected() if self.manager.is_unlocked else None)

        act_key = QAction("Export Key File…", self)
        act_key.triggered.connect(lambda: self.vault_page._export_key() if self.manager.is_unlocked else None)

        vault_menu.addAction(act_enc)
        vault_menu.addAction(act_dec)
        vault_menu.addSeparator()
        vault_menu.addAction(act_key)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        act_about = QAction("About Macan File Vault", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    def _build_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(f"color: {CLR_TEXT_SECONDARY}; background: transparent;")
        self._lock_indicator = QLabel("🔴  Locked")
        self._lock_indicator.setStyleSheet(f"color: {CLR_LOCKED}; font-weight: 600; background: transparent; padding-right: 8px;")
        self.status_bar.addWidget(self._status_lbl, 1)
        self.status_bar.addPermanentWidget(self._lock_indicator)

    def _set_status(self, text: str, color: str = None):
        self._status_lbl.setText(text)
        if color:
            self._status_lbl.setStyleSheet(f"color: {color}; background: transparent;")
        else:
            self._status_lbl.setStyleSheet(f"color: {CLR_TEXT_SECONDARY}; background: transparent;")

    def _set_lock_indicator(self, unlocked: bool):
        if unlocked:
            self._lock_indicator.setText("🟢  Unlocked")
            self._lock_indicator.setStyleSheet(f"color: {CLR_UNLOCKED}; font-weight: 600; background: transparent; padding-right: 8px;")
        else:
            self._lock_indicator.setText("🔴  Locked")
            self._lock_indicator.setStyleSheet(f"color: {CLR_LOCKED}; font-weight: 600; background: transparent; padding-right: 8px;")

    # ── Vault actions ─────────────────────────────────────────────────────────

    def _choose_vault_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Vault Folder")
        if path:
            self.manager.vault_dir = path
            self.locked_page.refresh_dir_label()
            self._set_status(f"Vault location: {path}")

    def _create_new_vault(self):
        path = QFileDialog.getExistingDirectory(self, "Select Folder for New Vault")
        if not path:
            return
        self.manager.vault_dir = path
        self.locked_page.refresh_dir_label()

        dlg = VaultPasswordDialog(self.manager, mode="setup", parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        pw = dlg.password
        self.manager._index = {}
        self.manager.save_index(pw)

        reply = QMessageBox.question(self, "Save Key File",
            "Vault created successfully.\n\n"
            "Would you like to export a backup key file (.mfk) now?\n"
            "A key file can be used as an alternative unlock factor.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.vault_page.set_password(pw)
            self.vault_page._export_key()

        self._open_vault(pw)
        QMessageBox.information(self, "Vault Created",
            "Your new encrypted vault is ready.\n\n"
            f"Location:  {path}")

    def _unlock_vault(self):
        if not self.manager.vault_dir:
            QMessageBox.warning(self, "No Vault Selected", "Please select a vault folder first.")
            return
        if self.manager.is_locked_out:
            m = self.manager.lockout_remaining_sec // 60
            s = self.manager.lockout_remaining_sec % 60
            QMessageBox.warning(self, "Account Locked",
                f"Too many failed attempts.\nPlease wait {m:02d}:{s:02d} before trying again.")
            return

        dlg = VaultPasswordDialog(self.manager, mode="unlock", parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        # Key file path
        if dlg._use_key and dlg.key_data:
            self._unlock_with_key(dlg.key_data)
            return

        pw = dlg.password
        if not self.manager.load_index(pw):
            self.manager.record_failed_attempt()
            if self.manager.is_locked_out:
                QMessageBox.critical(self, "Vault Locked",
                    f"Too many incorrect attempts.\n"
                    f"The vault is locked for {LOCKOUT_SECONDS // 60} minutes.")
            else:
                rem = MAX_ATTEMPTS - self.manager._failed_attempts
                QMessageBox.warning(self, "Authentication Failed",
                    f"Incorrect password. {rem} attempt(s) remaining.")
            return

        self.manager.reset_attempts()
        self._open_vault(pw)

    def _unlock_with_key(self, key_data: bytes):
        ok, _ = VaultEngine.verify_key_file(key_data)
        if not ok:
            QMessageBox.warning(self, "Invalid Key File", "The selected key file is not valid.")
            return
        pw, confirmed = QInputDialog.getText(self, "Confirm Password",
            "Enter vault password to confirm identity:",
            QLineEdit.EchoMode.Password)
        if not confirmed or len(pw) < 8:
            return
        if not self.manager.load_index(pw):
            self.manager.record_failed_attempt()
            if self.manager.is_locked_out:
                QMessageBox.critical(self, "Vault Locked",
                    f"Too many incorrect attempts. Vault locked for {LOCKOUT_SECONDS // 60} minutes.")
            else:
                rem = MAX_ATTEMPTS - self.manager._failed_attempts
                QMessageBox.warning(self, "Authentication Failed",
                    f"Incorrect password. {rem} attempt(s) remaining.")
            return
        self.manager.reset_attempts()
        self._open_vault(pw)

    def _open_vault(self, pw: str):
        self._current_password = pw
        self.manager.set_unlocked(True)
        self.vault_page.set_password(pw)
        self.vault_page.refresh_list()
        self.stack.setCurrentIndex(1)
        self._set_lock_indicator(True)
        self._set_status(f"Vault unlocked  ·  {self.manager.vault_dir}")
        self.setWindowTitle(f"Macan File Vault  {APP_VERSION}  —  {os.path.basename(self.manager.vault_dir)}")

    def _lock_vault(self):
        self.vault_page.cleanup()
        self.manager.set_unlocked(False)
        self._current_password = ""
        self.stack.setCurrentIndex(0)
        self._set_lock_indicator(False)
        self._set_status("Vault locked.")
        self.setWindowTitle(f"Macan File Vault  {APP_VERSION}")

    def _show_about(self):
        QMessageBox.about(self, "About Macan File Vault",
            f"<b>Macan File Vault</b> &nbsp; v{APP_VERSION}<br><br>"
            "AES-256-GCM file encryption with PBKDF2-HMAC-SHA256 key derivation.<br><br>"
            "<b>Encryption:</b> AES-256-GCM (authenticated)<br>"
            "<b>Key Derivation:</b> PBKDF2-HMAC-SHA256 · 310,000 iterations<br>"
            "<b>Salt:</b> 16-byte random per file<br>"
            "<b>Brute-force protection:</b> 3 attempts → 30-minute lockout<br><br>"
            "© MacanAngkasa")

    # ── Window events ─────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self.vault_page.cleanup()
        settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        settings.setValue("window_geometry", self.saveGeometry())
        event.accept()


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(SETTINGS_ORG)
    app.setStyleSheet(GLOBAL_STYLESHEET)

    # Improve font rendering on Windows
    font = QFont("Segoe UI", 10)
    font.setHintingPreference(QFont.HintingPreference.PreferDefaultHinting)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
