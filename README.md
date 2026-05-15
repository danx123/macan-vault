<div align="center">

<img src="macan_shield.png" alt="Macan File Vault" width="96" height="96"/>

# Macan File Vault

**A lightweight, self-contained desktop vault for encrypting and managing sensitive files.**

[![Version](https://img.shields.io/badge/version-1.3.0-blue?style=flat-square)](https://github.com/danx123/macan-vault/releases)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey?style=flat-square)]()

AES-256-GCM · PBKDF2-HMAC-SHA256 · Zero plaintext on disk

</div>

---

## Overview

Macan File Vault is a standalone desktop application that lets you encrypt, store, and decrypt files inside a local vault — with no cloud dependency, no account required, and no plaintext ever written to disk. It ships as a single Python script and runs on any platform that supports PySide6.

<div align="center">
  <img src="https://raw.githubusercontent.com/danx123/macan-vault/main/screenshots/locked.png" alt="Locked Screen" width="520"/>
  &nbsp;&nbsp;
  <img src="https://raw.githubusercontent.com/danx123/macan-vault/main/screenshots/unlocked.png" alt="Unlocked Screen" width="520"/>
</div>

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
| **Cross-platform** | Runs on Windows, macOS, and Linux via PySide6 |

---

## Requirements

- Python **3.10** or later
- [PySide6](https://pypi.org/project/PySide6/) — Qt for Python (UI framework)
- [cryptography](https://pypi.org/project/cryptography/) — AES-GCM and PBKDF2 primitives

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

**3. Run the application**

```bash
python macan_vault_standalone.py
```

---

## Quick Start

1. **Select a vault folder** — choose an empty directory where encrypted files will be stored, or point to an existing vault.
2. **Create a new vault** — click *Create New Vault* and set a strong master password. The vault index is encrypted immediately.
3. **Unlock an existing vault** — click *Unlock Vault* and enter your password. After 3 wrong attempts, the vault locks out for 30 minutes.
4. **Encrypt files** — click *Encrypt Files* in the toolbar, or drag and drop files onto the window. Files are encrypted in-place and the originals can be wiped.
5. **Decrypt files** — select one or more entries from the list and click *Decrypt*. Choose a destination folder for the recovered files.
6. **Lock** — click *Lock* or press **Ctrl+L** to clear the session key from memory and return to the locked state.

---

## Keyboard Shortcuts

| Action | Shortcut |
|---|---|
| Encrypt files | `Ctrl+E` |
| Decrypt selected | `Ctrl+D` |
| Lock vault | `Ctrl+L` |
| New vault | `Ctrl+N` |

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
- The brute-force lockout is enforced in-process. For server or shared-machine deployments, consider additional OS-level access controls.

---

## Project Structure

```
macan-vault/
├── macan_vault_standalone.py   # Single-file application entry point
├── macan_shield.png            # Application logo (used in UI)
├── macan_shield.ico            # Window icon (Windows)
├── screenshots/
│   ├── locked.png
│   └── unlocked.png
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
