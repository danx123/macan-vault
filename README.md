<div align="center">

<img src="macan_shield.png" alt="Macan File Vault" width="96" height="96"/>

# Macan File Vault

**A lightweight, self-contained desktop vault for encrypting and managing sensitive files.**

[![Version](https://img.shields.io/badge/version-2.1.0-blue?style=flat-square)](https://github.com/danx123/macan-vault/releases)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey?style=flat-square)]()

AES-256-GCM · PBKDF2-HMAC-SHA256 · Zero plaintext on disk

</div>

---

## Overview

Macan File Vault is a standalone desktop application that lets you encrypt, store, and decrypt files inside a local vault — with no cloud dependency, no account required, and no plaintext ever written to disk. It ships as a single Python script and runs on any platform that supports PySide6.

<img width="1102" height="715" alt="Screenshot 2026-08-08 065438" src="https://github.com/user-attachments/assets/7a551424-199c-42e0-98c6-4b15da42058f" />



https://github.com/user-attachments/assets/a9c63ce6-a66c-4ad3-af32-3545a1663e09


---

## Features

| Feature | Detail |
|---|---|
| **AES-256-GCM encryption** | Authenticated encryption — ciphertext integrity is verified on every decrypt |
| **PBKDF2-HMAC-SHA256** | 310,000 iterations of key derivation for strong password-to-key hardening |
| **Randomised filenames** | Encrypted files are stored under random hex names (`.mfe`) — no metadata leakage |
| **Zero plaintext on disk** | Original files are never written in decrypted form during processing |
| **Secure wipe** | Files are overwritten before deletion to resist recovery by forensic tools |
| **Brute-force lockout** | 3 failed unlock attempts triggers a 30-minute lockout |
| **Exportable key file** | Back up your derived key as a `.mfk` file for vault recovery |
| **Drag-and-drop** | Drop files directly onto the vault window to encrypt them instantly |
| **Quick View sidebar** | Preview encrypted files in-place without decrypting to disk — images, video, audio, documents, code, and more |
| **Cross-platform** | Runs on Windows, macOS, and Linux via PySide6 |

---

## Quick View

Quick View is an in-application sidebar that lets you inspect the contents of any encrypted vault file instantly, without extracting it to disk. Press **F3** or click the Quick View button on any selected file to open it.

All decryption happens exclusively in RAM. The moment you switch files or close the sidebar, the plaintext is discarded — nothing is ever written to the filesystem.

### Supported Formats

| Category | Extensions |
|---|---|
| **Images** | `.jpg` `.jpeg` `.png` `.gif` `.bmp` `.webp` `.ico` `.tiff` `.svg` |
| **Text / Config** | `.txt` `.md` `.log` `.ini` `.cfg` `.yaml` `.yml` `.toml` `.xml` `.html` `.csv` `.json` `.env` and more |
| **Source Code** | `.py` `.js` `.ts` `.jsx` `.tsx` `.java` `.c` `.cpp` `.go` `.rs` `.rb` `.php` `.sh` `.sql` `.swift` `.kt` and more |
| **Audio** | `.mp3` `.wav` `.ogg` `.flac` `.m4a` `.aac` `.wma` `.opus` `.aiff` |
| **Video** | `.mp4` `.mkv` `.avi` `.mov` `.webm` `.wmv` `.flv` `.m4v` `.3gp` |
| **PDF** | `.pdf` — first 3 pages rendered as plain text |
| **Archives** | `.zip` — full file listing with names, sizes, and dates |
| **Office** | `.docx` `.xlsx` `.pptx` — paragraph text, sheet rows, and slide content |
| **Binary** | All other formats — hex dump of the first 1,024 bytes |

### Audio & Video Playback

Audio and video files play directly inside the sidebar via `QMediaPlayer` (PySide6 QtMultimedia). No external player is launched and no decrypted file is written to disk.

The transport bar provides:

- **Play / Pause** toggle
- **Seek bar** with drag support
- **Elapsed / total time** label (`m:ss / m:ss`)
- **Volume** slider

Audio viewers additionally display a waveform visualisation sampled from the raw byte stream, along with embedded metadata where available (ID3v1 tags for `.mp3`, RIFF header for `.wav`).

### Source Code Highlighting

Text and source code files are rendered in a monospaced editor with lightweight syntax highlighting — keywords, string literals, comments, and numeric literals — for Python, JavaScript/TypeScript, Java, Go, Rust, and SQL.

### Non-blocking Architecture

Decryption runs on a background `QThread` so the main UI remains fully responsive while large files are being processed. Switching to a different file cancels the in-flight job immediately.

---

## Requirements

- Python **3.10** or later
- [PySide6](https://pypi.org/project/PySide6/) — Qt for Python (UI framework)
- [cryptography](https://pypi.org/project/cryptography/) — AES-GCM and PBKDF2 primitives

### Optional Dependencies

The following packages unlock additional Quick View capabilities. Each one degrades gracefully if absent — the relevant viewer falls back to a metadata display with installation instructions rather than raising an error.

| Package | Enables |
|---|---|
| `PySide6-Addons` | Audio and video playback (`QtMultimedia`) |
| `pypdf` | PDF text extraction |
| `python-docx` | DOCX paragraph preview |
| `openpyxl` | XLSX sheet preview |
| `python-pptx` | PPTX slide text preview |

Install all optional packages at once:

```bash
pip install PySide6-Addons pypdf python-docx openpyxl python-pptx
```

---

## Installation

**1. Clone the repository**

```bash
git clone https://github.com/danx123/macan-vault.git
cd macan-vault
```

**2. Install dependencies**

```bash
pip install PySide6 cryptography
```

> Using a virtual environment is recommended:
> ```bash
> python -m venv .venv
> source .venv/bin/activate   # Windows: .venv\Scripts\activate
> pip install PySide6 cryptography
> ```

**3. (Optional) Install Quick View extras**

```bash
pip install PySide6-Addons pypdf python-docx openpyxl python-pptx
```

**4. Run the application**

```bash
python macan_vault_standalone.py
```

---

## Quick Start

1. **Select a vault folder** — choose an empty directory where encrypted files will be stored, or point to an existing vault.
2. **Create a new vault** — click *Create New Vault* and set a strong master password. The vault index is encrypted immediately.
3. **Unlock an existing vault** — click *Unlock Vault* and enter your password. After 3 wrong attempts, the vault locks out for 30 minutes.
4. **Encrypt files** — click *Encrypt Files* in the toolbar, or drag and drop files onto the window. Files are encrypted in-place and the originals can be wiped.
5. **Preview files** — select any entry and press **F3** (or click *Quick View*) to inspect its contents without decrypting to disk.
6. **Decrypt files** — select one or more entries from the list and click *Decrypt*. Choose a destination folder for the recovered files.
7. **Lock** — click *Lock* or press **Ctrl+L** to clear the session key from memory and return to the locked state.

---

## Keyboard Shortcuts

| Action | Shortcut |
|---|---|
| Encrypt files | `Ctrl+E` |
| Decrypt selected | `Ctrl+D` |
| Lock vault | `Ctrl+L` |
| New vault | `Ctrl+N` |
| Quick View | `F3` |

---

## File Format

Encrypted files use the `.mfe` (Macan File Encrypted) container format:

```
┌─────────────────────────────────────────────────────────────────┐
│  Magic      │  4 bytes  │  "MCVT"                               │
│  Version    │  1 byte   │  Format version (currently 1)         │
│  Salt       │  16 bytes │  PBKDF2 salt (random per file)        │
│  Nonce      │  12 bytes │  AES-GCM nonce (random per file)      │
│  Ciphertext │  N bytes  │  AES-256-GCM encrypted payload        │
└─────────────────────────────────────────────────────────────────┘
```

Key files (`.mfk`) store a versioned, encrypted copy of the derived key for backup and recovery purposes.

---

## Security Notes

- The master password is **never stored** anywhere. Only the derived key (in memory, for the duration of the session) and the encrypted index are persisted.
- Each file is encrypted with a **unique salt and nonce**, ensuring ciphertext diversity even for identical inputs.
- GCM authentication tags are verified before any plaintext is returned — a tampered or corrupted file will be rejected outright.
- **Quick View** decrypts exclusively in RAM. No plaintext is ever written to disk; content is discarded the moment the viewer is closed or switched.
- The brute-force lockout is enforced in-process. For server or shared-machine deployments, consider additional OS-level access controls.

---

## Project Structure

```
macan-vault/
├── macan_vault_standalone.py   # Single-file application entry point
├── quick_view_module.py        # Quick View sidebar (format preview engine)
├── macan_shield.png            # Application logo (used in UI)
├── macan_shield.ico            # Window icon (Windows)
├── screenshots/
│   ├── locked.png
│   └── unlocked.png
├── CHANGELOG.md
└── README.md
```

---

## Contributing

Contributions are welcome. Please open an issue to discuss significant changes before submitting a pull request. All code should follow PEP 8 and include docstrings for public functions.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a pull request

---

## License

This project is licensed under the [MIT License](LICENSE).

---

<div align="center">
  <sub>Built with PySide6 and the Python <code>cryptography</code> library · Macan Angkasa</sub>
</div>
