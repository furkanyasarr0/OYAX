
<div  align="center">

# 🛠️ OYAX - Windows Maintenance Tool

  

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](#)

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](#)

[![License](https://img.shields.io/badge/license-Open_Source-green.svg)](#)

[![Platform](https://img.shields.io/badge/platform-windows-lightgrey.svg)](#)

[![Stars](https://img.shields.io/github/stars/furkanyasarr0/OYAX?style=social)](https://github.com/furkanyasarr0/OYAX)

  

</div>

  

---

  

**OYAX** is a fully open-source optimization tool that allows you to manage performance-enhancing maintenance and critical repair operations on the Windows operating system from a single interface.

  

# ⭐ Changelog & Updates

  

- `winget upgrade --all` is a Windows Package Manager command that updates all installed applications to their latest available versions. It helps keep software up to date quickly and efficiently through a single command in the Windows terminal.

  

## ✨ Key Features

  

- 🗂️ **Categorized Menu:** Dedicated control panels for Temporary files, Network/DNS, and System Health.

- 🧹 **Advanced Cleaning:** - `Temp` and `Prefetch` directories.

- Recycle Bin.

- Windows Store cache.

- 🌐 **Network & DNS Optimization:** - Flush DNS cache.

- IP Release/Renew.

- Winsock protocol reset.

- 🛡️ **Critical System Repair:** - File verification with `SFC Scannow`.

- Image repair with `DISM` tools.

-  `chkdsk` disk error scanning.

- 🚀 **Quick Maintenance Mode:** Runs the most critical tasks sequentially with a single click.

- 📊 **SQLite Registry:** Keeps a history of operations and allows you to export as CSV.

  

## 📸 Screenshot

  

<div  align="center">

<img src="[https://via.placeholder.com/600x350?text=OYAX+Dashboard](https://via.placeholder.com/600x350?text=OYAX+Dashboard)" alt="OYAX Main Screen">

</div>

  

## 🚀 Installation and Usage

  

Follow the steps below to run the project on your computer.

  

### Prerequisites

- Python 3.10 or higher must be installed.

- Windows operating system (Some commands require administrator privileges).

  

### Execution Steps

1. Clone or download the project repo.

2. Navigate to the project directory in the command line.

3. Create and activate your virtual environment (venv):

```powershell

python -m venv venv

.\venv\Scripts\activate

```

4. Start the application:

```powershell

python app.py

```

  

> [!IMPORTANT]

> It is recommended to open the application with the **Run as Administrator** option for features that interact with system files (SFC/DISM etc.) to function correctly.

  

## 🛠️ Technical Infrastructure

  

-  **Programming Language:** Python

-  **Interface (UI):** Tkinter (Modernized, user-friendly theme)

-  **Database:** SQLite3 (For transaction logs)

  

## 🛡️ License and Terms of Use

  

This project is entirely **Open Source**. The application is completely free of any restrictive license or hardware verification systems. You are welcome to use the application, examine the source code, modify it to suit your needs, and contribute to its ongoing development.

  

---

**Developer:** [furkanysrr0](https://github.com/furkanyasarr0)