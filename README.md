
<div  align="center">

# 🛠️ OYAX - Windows Maintenance Tool

[![Version](https://img.shields.io/badge/version-1.4-blue.svg)](#)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](#)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](#)
[![Platform](https://img.shields.io/badge/platform-windows-lightgrey.svg)](#)
[![Stars](https://img.shields.io/github/stars/furkanyasarr0/OYAX?style=social)](https://github.com/furkanyasarr0/OYAX)

</div>

  

---

  

**OYAX** is a fully open-source optimization tool that allows you to manage performance-enhancing maintenance and critical repair operations on the Windows operating system from a single interface.

  

## ⭐ Changelog & Updates

  

### v1.4
- Added **4 new task categories**: Performance Optimization, Disk Management, Security, System Info
- Added **20+ new maintenance tasks** (Defender scan, disk reports, startup programs, large file scan, etc.)
- Thread-safe database operations with `threading.Lock`
- CSV export button added to the History panel UI
- Fixed PyInstaller build entry point (`OYAX.spec`)
- Log clear now requires user confirmation
- Improved subprocess encoding with `utf-8` fallback
- Bare `except` blocks replaced with `except Exception` for better debugging
- Version bump to 1.4

### v1.3
- `winget upgrade --all` support for bulk package updates
- Initial public release with categorized task system

  

## ✨ Key Features

  

- 🗂️ **Categorized Menu:** Dedicated control panels for Temporary files, Network/DNS, System Health, Performance, Disk Management, Security, and System Info.

- 🧹 **Advanced Cleaning:** `Temp`, `Prefetch`, Thumbnail Cache, Font Cache, Icon Cache, and Recycle Bin cleanup.

- 🌐 **Network & DNS Optimization:** Flush DNS cache, IP Release/Renew, Winsock protocol reset, active connections view.

- 🛡️ **Critical System Repair:** File verification with `SFC Scannow`, image repair with `DISM` tools, `chkdsk` disk scanning, component store cleanup.

- 🚀 **Performance Optimization:** Power plan management, Windows Update cache cleanup, visual effects tuning, fast startup toggle.

- 💾 **Disk Management:** Defrag/TRIM optimization, disk space reports, large file scanning (500MB+), Compact OS queries.

- 🔒 **Security:** Windows Defender quick scan, definition updates, firewall status monitoring.

- 📊 **System Info:** Hardware summary, driver list, installed updates, startup programs, running services.

- ⚡ **Quick Maintenance Mode:** Runs the most critical tasks sequentially with a single click.

- 📋 **SQLite Registry:** Keeps a history of operations with filtering, search, and CSV export.

  

## 🚀 Installation and Usage

  

Follow the steps below to run the project on your computer.

  

### Prerequisites

- Python 3.10 or higher must be installed.

- Windows operating system (Some commands require administrator privileges).

  

### Execution Steps

1. Clone or download the project repo.

2. Navigate to the project directory in the command line.

3. Create and activate your virtual environment (venv) and install dependencies:

```powershell

python -m venv venv

.\venv\Scripts\activate

pip install -r requirements.txt

```

4. Start the application:

```powershell

python OYAX.py

```

  

> [!IMPORTANT]

> It is recommended to open the application with the **Run as Administrator** option for features that interact with system files (SFC/DISM etc.) to function correctly.

  

## 🛠️ Technical Infrastructure

  

-  **Programming Language:** Python

-  **Interface (UI):** CustomTkinter (Modern Windows 11 Dark theme, sleek cards and sidebar)

-  **Database:** SQLite3 (Thread-safe, for transaction logs)

  

## 🛡️ License and Terms of Use

  

This project is entirely **Open Source** under the [MIT License](LICENSE). The application is completely free of any restrictive license or hardware verification systems. You are welcome to use the application, examine the source code, modify it to suit your needs, and contribute to its ongoing development.

  

---

**Developer:** [furkanysrr0](https://github.com/furkanyasarr0)