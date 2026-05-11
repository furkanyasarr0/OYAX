import os
import sys
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import csv
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from tkinter import END, BOTH, LEFT, RIGHT, X, Y, VERTICAL, messagebox
import tkinter as tk
from tkinter import ttk, filedialog

# from license_system import OyaxLicense


# AppData yolunu bul ve Oyax klasörü yoksa oluştur
APPDATA_PATH = os.path.join(os.environ.get(
    'APPDATA', os.path.expanduser('~')), 'Oyax')
if not os.path.exists(APPDATA_PATH):
    os.makedirs(APPDATA_PATH)

DB_FILE = os.path.join(APPDATA_PATH, "maintenance_logs.db")
APP_VERSION = "1.1"
AUTHOR_NAME = "furkanysrr0"


TASK_CATEGORIES = {
    "Geçici Dosyalar ve Cache": [
        {"name": "Geçici Dosyaları Temizle",
            "requires_admin": False, "type": "python"},
        {
            "name": "Windows Temp Temizliği (powershell)",
            "requires_admin": True,
            "type": "command",
            "command": 'powershell -Command "Get-ChildItem -Path C:\\Windows\\Temp -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"',
        },
        {
            "name": "Prefetch Temizliği",
            "requires_admin": True,
            "type": "command",
            "command": 'powershell -Command "Remove-Item -Path C:\\Windows\\Prefetch\\* -Force -Recurse -ErrorAction SilentlyContinue"',
        },
        {
            "name": "Geri Dönüşüm Kutusu Temizle",
            "requires_admin": False,
            "type": "command",
            "command": 'powershell -Command "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"',
        },
        {
            "name": "Microsoft Store Cache Sıfırla",
            "requires_admin": False,
            "type": "command",
            "command": "wsreset.exe",
        },
    ],
    "Ağ ve DNS": [
        {
            "name": "DNS Önbelleğini Temizle (ipconfig /flushdns)",
            "requires_admin": True,
            "type": "command",
            "command": "ipconfig /flushdns",
        },
        {
            "name": "DNS Önbelleğini Görüntüle",
            "requires_admin": False,
            "type": "command",
            "command": "ipconfig /displaydns",
        },
        {
            "name": "DNS Yeniden Kaydet (ipconfig /registerdns)",
            "requires_admin": True,
            "type": "command",
            "command": "ipconfig /registerdns",
        },
        {
            "name": "IP Adresini Yenile (release + renew)",
            "requires_admin": True,
            "type": "command",
            "command": "ipconfig /release && ipconfig /renew",
        },
        {
            "name": "ARP Cache Temizliği",
            "requires_admin": True,
            "type": "command",
            "command": "arp -d *",
        },
    ],
    "Ağ Sıfırlama": [
        {
            "name": "Winsock Sıfırla (netsh winsock reset)",
            "requires_admin": True,
            "type": "command",
            "command": "netsh winsock reset",
        },
        {
            "name": "TCP/IP Stack Sıfırla",
            "requires_admin": True,
            "type": "command",
            "command": "netsh int ip reset",
        },
        {
            "name": "Windows Güvenlik Duvarını Sıfırla",
            "requires_admin": True,
            "type": "command",
            "command": "netsh advfirewall reset",
        },
    ],
    "Sistem Sağlığı": [
        {"name": "SFC Taraması (sfc /scannow)", "requires_admin": True,
                                "type": "command", "command": "sfc /scannow"},
        {
            "name": "DISM Health Check",
            "requires_admin": True,
            "type": "command",
            "command": "DISM /Online /Cleanup-Image /CheckHealth",
        },
        {
            "name": "DISM Scan Health",
            "requires_admin": True,
            "type": "command",
            "command": "DISM /Online /Cleanup-Image /ScanHealth",
        },
        {
            "name": "DISM Restore Health",
            "requires_admin": True,
            "type": "command",
            "command": "DISM /Online /Cleanup-Image /RestoreHealth",
        },
        {"name": "Disk Tarama (chkdsk /scan)", "requires_admin": True,
                               "type": "command", "command": "chkdsk /scan"},
    ],
}


def build_task_map() -> dict[str, dict]:
    tasks: dict[str, dict] = {}
    for category_name, category_tasks in TASK_CATEGORIES.items():
        for task in category_tasks:
            tasks[task["name"]] = {
                "requires_admin": task["requires_admin"],
                "type": task["type"],
                "command": task.get("command"),
                "category": category_name,
            }
    return tasks


TASKS = build_task_map()


def is_admin() -> bool:
    try:
        import ctypes  # pylint: disable=import-outside-toplevel

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def ensure_db() -> None:
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                task_name TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT
            )
            """
        )


def add_log(task_name: str, status: str, details: str) -> None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO logs (timestamp, task_name, status, details) VALUES (?, ?, ?, ?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 task_name, status, details),
            )
    except Exception:
        pass


def clear_logs() -> None:
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM logs")


def cleanup_temp_directories() -> tuple[str, int]:
    deleted_count = 0
    errors = []

    temp_paths = [
        Path(tempfile.gettempdir()),
        Path(os.environ.get("TEMP", "")),
        Path(os.environ.get("TMP", "")),
        Path("C:/Windows/Temp"),
    ]

    unique_paths = []
    for path in temp_paths:
        if str(path) and path.exists() and path not in unique_paths:
            unique_paths.append(path)

    for folder in unique_paths:
        try:
            for item in folder.iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
                    deleted_count += 1
                except Exception as ex:
                    errors.append(f"{item}: {ex}")
        except Exception as ex:
            errors.append(f"{folder}: {ex}")

    details = f"Silinen öğe sayısı: {deleted_count}"
    if errors:
        details += f"\nAtlanan/Hatalı öğe sayısı: {len(errors)}"

    return details, len(errors)


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class MaintenanceApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OYAX - Windows Bakım Aracı")
        try:
            icon_path = resource_path("icon.ico")
            self.iconbitmap(icon_path)
        except:
            pass

        width = 1220
        height = 760

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)

        self.geometry(f"{width}x{height}+{x}+{y}")

        self.minsize(1080, 640)
        self.resizable(True, True)
        self.configure(bg="#0f172a")

        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self._configure_styles()
        self.option_add("*TCombobox*Listbox.background", "#0b1220")
        self.option_add("*TCombobox*Listbox.foreground", "#e5e7eb")
        self.option_add("*TCombobox*Listbox.selectBackground", "#1e293b")
        self.option_add("*TCombobox*Listbox.selectForeground", "#e5e7eb")

        ensure_db()
        self._build_ui()
        self.refresh_logs()

    def _configure_styles(self) -> None:
        self.style.configure(".", font=("Segoe UI", 10))
        self.style.configure("Card.TFrame", background="#111827")
        self.style.configure("Header.TFrame", background="#111827")
        self.style.configure("HeaderTitle.TLabel", background="#111827", foreground="#f9fafb", font=("Segoe UI", 18, "bold"))
        self.style.configure("HeaderSub.TLabel", background="#111827", foreground="#9ca3af", font=("Segoe UI", 10))
        self.style.configure(
            "Section.TLabelframe",
            background="#111827",
            foreground="#e5e7eb",
            borderwidth=0,
            relief="flat",
        )
        self.style.configure(
            "Section.TLabelframe.Label",
            background="#111827",
            foreground="#e5e7eb",
            font=("Segoe UI", 10, "bold"),
        )
        self.style.configure("TaskMenu.TFrame", background="#0b1220")
        self.style.configure("TaskMenuTitle.TLabel", background="#0b1220", foreground="#f1f5f9", font=("Segoe UI", 11, "bold"))
        self.style.configure("TaskMenuSub.TLabel", background="#0b1220", foreground="#94a3b8")
        self.style.configure("TaskCard.TFrame", background="#111827")
        self.style.configure("StatusNeutral.TLabel", background="#0f172a", foreground="#cbd5e1", font=("Segoe UI", 9, "bold"))
        self.style.configure("StatusGood.TLabel", background="#14532d", foreground="#dcfce7", font=("Segoe UI", 9, "bold"))
        self.style.configure("StatusWarn.TLabel", background="#7c2d12", foreground="#ffedd5", font=("Segoe UI", 9, "bold"))
        self.style.configure("HistoryCard.TFrame", background="#111827")
        self.style.configure("HistoryTitle.TLabel", background="#111827", foreground="#f1f5f9", font=("Segoe UI", 11, "bold"))
        self.style.configure("HistorySub.TLabel", background="#111827", foreground="#94a3b8")
        self.style.configure("TLabel", background="#111827", foreground="#e5e7eb")
        self.style.configure("Muted.TLabel", background="#111827", foreground="#94a3b8")

        self.style.configure("Primary.TButton", background="#2563eb", foreground="#ffffff", borderwidth=0, padding=8)
        self.style.map(
            "Primary.TButton",
            background=[("active", "#1d4ed8"), ("disabled", "#475569")],
            foreground=[("active", "#ffffff"), ("disabled", "#cbd5e1")],
        )
        self.style.configure("Secondary.TButton", background="#1f2937", foreground="#e5e7eb", borderwidth=0, padding=8)
        self.style.map(
            "Secondary.TButton",
            background=[("active", "#334155"), ("disabled", "#374151")],
            foreground=[("active", "#e5e7eb"), ("disabled", "#94a3b8")],
        )
        self.style.configure("Danger.TButton", background="#b91c1c", foreground="#ffffff", borderwidth=0, padding=8)
        self.style.map(
            "Danger.TButton",
            background=[("active", "#991b1b"), ("disabled", "#7f1d1d")],
            foreground=[("active", "#ffffff"), ("disabled", "#fecaca")],
        )

        self.style.configure(
            "TEntry",
            fieldbackground="#0b1220",
            foreground="#e5e7eb",
            borderwidth=0,
            relief="flat",
            insertcolor="#93c5fd",
        )
        self.style.map(
            "TEntry",
            fieldbackground=[("readonly", "#0b1220"), ("disabled", "#111827")],
            foreground=[("readonly", "#e5e7eb"), ("disabled", "#64748b")],
        )
        self.style.configure(
            "TCombobox",
            fieldbackground="#0b1220",
            background="#0b1220",
            foreground="#e5e7eb",
            arrowcolor="#93c5fd",
            selectbackground="#1e293b",
            selectforeground="#e5e7eb",
            borderwidth=0,
            relief="flat",
            lightcolor="#0b1220",
            darkcolor="#0b1220",
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#0b1220"), ("disabled", "#111827")],
            foreground=[("readonly", "#e5e7eb"), ("disabled", "#64748b")],
            selectbackground=[("readonly", "#1e293b")],
            selectforeground=[("readonly", "#e5e7eb")],
        )
        self.style.configure("TCheckbutton", background="#111827", foreground="#e5e7eb")
        self.style.map(
            "TCheckbutton",
            background=[("active", "#111827"), ("disabled", "#111827")],
            foreground=[("active", "#e5e7eb"), ("disabled", "#64748b")],
        )
        self.style.configure(
            "Treeview",
            background="#0b1220",
            fieldbackground="#0b1220",
            foreground="#e5e7eb",
            rowheight=26,
            borderwidth=0,
            relief="flat",
        )
        self.style.configure(
            "Treeview.Heading",
            background="#1f2937",
            foreground="#e5e7eb",
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
            relief="flat",
        )
        self.style.map(
            "Treeview",
            background=[("selected", "#1d4ed8"), ("!selected", "#0b1220")],
            foreground=[("selected", "#f8fafc"), ("!selected", "#e5e7eb")],
        )

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self, style="Card.TFrame", padding=14)
        main_frame.pack(fill=BOTH, expand=True)

        left_panel = ttk.Frame(main_frame, style="TaskMenu.TFrame", padding=12, width=460)
        left_panel.pack(side=LEFT, fill=Y, padx=(0, 10))
        left_panel.pack_propagate(False)

        ttk.Label(left_panel, text="Görev Menüsü", style="TaskMenuTitle.TLabel").pack(anchor="w")
        ttk.Label(
            left_panel,
            text="Kategoriye göre filtrele ve görev seçimi yap.",
            style="TaskMenuSub.TLabel",
        ).pack(anchor="w", pady=(2, 10))

        status_box = ttk.Frame(left_panel, style="TaskCard.TFrame", padding=10)
        status_box.pack(fill=X, pady=(0, 10))
        self.selection_summary_var = tk.StringVar(value="Seçili görev: 0")
        ttk.Label(status_box, textvariable=self.selection_summary_var, style="TaskMenuTitle.TLabel").pack(anchor="w")
        badge_row = ttk.Frame(status_box, style="TaskCard.TFrame")
        badge_row.pack(fill=X, pady=(6, 0))
        self.admin_required_var = tk.StringVar(value="Admin gerektiren: 0")
        self.admin_required_badge = ttk.Label(badge_row, textvariable=self.admin_required_var, style="StatusNeutral.TLabel")
        self.admin_required_badge.pack(side=LEFT)
        self.admin_note_var = tk.StringVar(value="Admin modu: Kapalı")
        self.admin_mode_badge = ttk.Label(badge_row, textvariable=self.admin_note_var, style="StatusNeutral.TLabel")
        self.admin_mode_badge.pack(side=LEFT, padx=(6, 0))

        menu_content = ttk.Frame(left_panel, style="TaskMenu.TFrame")
        menu_content.pack(fill=BOTH, expand=True)

        filter_box = ttk.Frame(menu_content, style="TaskCard.TFrame", padding=10)
        filter_box.pack(fill=X, pady=(0, 8))
        ttk.Label(filter_box, text="Filtre ve Secim", style="TaskMenuTitle.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Label(filter_box, text="Kategori secimi ile gorevleri filtrele.", style="TaskMenuSub.TLabel").pack(
            anchor="w", pady=(0, 8)
        )

        ttk.Label(filter_box, text="Kategori", style="Muted.TLabel").pack(anchor="w")
        self.category_var = tk.StringVar(value="Tümü")
        category_values = ["Tümü"] + list(TASK_CATEGORIES.keys())
        self.category_combo = ttk.Combobox(
            filter_box, textvariable=self.category_var, values=category_values, state="readonly"
        )
        self.category_combo.pack(fill=X, pady=(4, 8))
        self.category_combo.bind("<<ComboboxSelected>>", lambda _e: self.render_task_checkboxes())

        category_action_row = ttk.Frame(filter_box, style="Card.TFrame")
        category_action_row.pack(fill=X)
        ttk.Button(category_action_row, text="Tumunu Sec", style="Secondary.TButton", command=self.select_visible_tasks).pack(
            side=LEFT, fill=X, expand=True
        )
        ttk.Button(category_action_row, text="Temizle", style="Secondary.TButton", command=self.clear_visible_tasks).pack(
            side=LEFT, fill=X, expand=True, padx=(6, 0)
        )

        task_header = ttk.Frame(menu_content, style="TaskMenu.TFrame")
        task_header.pack(fill=X, pady=(0, 6))
        ttk.Label(task_header, text="Uygulanabilir Gorevler", style="TaskMenuTitle.TLabel").pack(side=LEFT)
        self.visible_tasks_var = tk.StringVar(value="Görünen: 0")
        ttk.Label(task_header, textvariable=self.visible_tasks_var, style="TaskMenuSub.TLabel").pack(side=RIGHT)
        ttk.Label(menu_content, text="Ctrl ile çoklu seçim yapabilirsin.", style="TaskMenuSub.TLabel").pack(
            anchor="w", pady=(0, 6)
        )
        task_list_box = ttk.Frame(menu_content, style="TaskCard.TFrame", padding=2)
        task_list_box.pack(fill=BOTH, expand=True, pady=(0, 8))
        task_scrollbar = tk.Scrollbar(
            task_list_box,
            orient=VERTICAL,
            width=8,
            relief="flat",
            troughcolor="#0b1220",
            bg="#1f2937",
            activebackground="#334155",
            bd=0,
            highlightthickness=0,
        )
        self.task_listbox = tk.Listbox(
            task_list_box,
            height=6,
            selectmode=tk.EXTENDED,
            bg="#0b1220",
            fg="#e2e8f0",
            selectbackground="#1d4ed8",
            selectforeground="#f8fafc",
            font=("Segoe UI", 10),
            relief="flat",
            bd=0,
            highlightthickness=0,
            activestyle="none",
        )
        self.task_listbox.configure(yscrollcommand=task_scrollbar.set)
        task_scrollbar.configure(command=self.task_listbox.yview)
        self.task_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        task_scrollbar.pack(side=RIGHT, fill=Y)

        self.selected_task_names: set[str] = set()
        self.visible_task_names: list[str] = []
        self.visible_task_display_names: list[str] = []
        self.task_listbox.bind("<<ListboxSelect>>", self.on_task_listbox_select)
        self.render_task_checkboxes()

        action_box = ttk.Frame(left_panel, style="TaskMenu.TFrame")
        action_box.pack(side="bottom", fill=X)
        ttk.Separator(action_box).pack(fill=X, pady=(2, 10))

        self.run_btn = ttk.Button(
            action_box, text="Seçili Görevleri Çalıştır", style="Primary.TButton", command=self.run_selected_tasks
        )
        self.run_btn.pack(fill=X, pady=(4, 6))

        self.quick_btn = ttk.Button(
            action_box, text="Hızlı Bakım (Temp + FlushDNS)", style="Secondary.TButton", command=self.run_quick_maintenance
        )
        self.quick_btn.pack(fill=X, pady=(0, 6))
        ttk.Button(action_box, text="Hakkında", style="Secondary.TButton", command=self.open_about_dialog).pack(fill=X)

        right_panel = ttk.Frame(main_frame, style="Card.TFrame")
        right_panel.pack(side=RIGHT, fill=BOTH, expand=True)

        custom_box = ttk.LabelFrame(right_panel, text="Ozel Komut (CMD)", style="Section.TLabelframe", padding=8)
        custom_box.pack(fill=X, pady=(0, 10))

        ttk.Label(custom_box, text="Komut Girisi:", style="Muted.TLabel").pack(anchor="w")
        self.custom_command_var = tk.StringVar()
        self.custom_command_entry = ttk.Entry(custom_box, textvariable=self.custom_command_var)
        self.custom_command_entry.pack(fill=X, pady=(4, 6))

        custom_actions = ttk.Frame(custom_box, style="Card.TFrame")
        custom_actions.pack(fill=X)
        self.custom_admin_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            custom_actions,
            text="Yönetici gerektirir",
            variable=self.custom_admin_var,
        ).pack(side=LEFT)

        self.custom_run_btn = ttk.Button(
            custom_actions, text="Ozel Komutu Calistir", style="Primary.TButton", command=self.run_custom_command
        )
        self.custom_run_btn.pack(side=RIGHT)

        self.content_pane = ttk.PanedWindow(right_panel, orient=tk.VERTICAL)
        self.content_pane.pack(fill=BOTH, expand=True)

        output_box = ttk.LabelFrame(self.content_pane, text="Canlı Çıktı", style="Section.TLabelframe", padding=8)

        self.output_text = tk.Text(
            output_box,
            height=12,
            wrap="word",
            bg="#020617",
            fg="#e2e8f0",
            insertbackground="#93c5fd",
            relief="flat",
            padx=8,
            pady=8,
        )
        self.output_text.pack(fill=BOTH, expand=True)

        history_box = ttk.LabelFrame(self.content_pane, text="İşlem Geçmişi (SQLite)", style="Section.TLabelframe", padding=10)
        self.history_box = history_box

        history_header = ttk.Frame(history_box, style="HistoryCard.TFrame")
        history_header.pack(fill=X, pady=(0, 8))
        ttk.Label(history_header, text="İşlem Geçmişi", style="HistoryTitle.TLabel").pack(side=LEFT)
        self.history_meta_var = tk.StringVar(value="Son 200 kayıt")
        ttk.Label(history_header, textvariable=self.history_meta_var, style="HistorySub.TLabel").pack(side=RIGHT)

        history_stats = ttk.Frame(history_box, style="HistoryCard.TFrame")
        history_stats.pack(fill=X, pady=(0, 8))
        self.history_ok_var = tk.StringVar(value="OK: 0")
        self.history_warn_var = tk.StringVar(value="Uyari: 0")
        self.history_err_var = tk.StringVar(value="Hata: 0")
        ttk.Label(history_stats, textvariable=self.history_ok_var, style="StatusGood.TLabel").pack(side=LEFT)
        ttk.Label(history_stats, textvariable=self.history_warn_var, style="StatusWarn.TLabel").pack(side=LEFT, padx=(6, 0))
        ttk.Label(history_stats, textvariable=self.history_err_var, style="StatusNeutral.TLabel").pack(side=LEFT, padx=(6, 0))

        filter_row = ttk.Frame(history_box, style="HistoryCard.TFrame")
        filter_row.pack(fill=X, pady=(0, 8))

        ttk.Label(filter_row, text="Durum", style="HistorySub.TLabel").pack(side=LEFT)
        self.status_filter_var = tk.StringVar(value="Tümü")
        status_combo = ttk.Combobox(
            filter_row,
            textvariable=self.status_filter_var,
            values=["Tümü", "OK", "Uyarı", "Hata"],
            state="readonly",
            width=12,
        )
        status_combo.pack(side=LEFT, padx=(6, 10))
        status_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_logs())

        ttk.Label(filter_row, text="Ara", style="HistorySub.TLabel").pack(side=LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_row, textvariable=self.search_var, width=28)
        search_entry.pack(side=LEFT, padx=(6, 8))
        search_entry.bind("<KeyRelease>", lambda _e: self.refresh_logs())

        actions_row = ttk.Frame(filter_row, style="HistoryCard.TFrame")
        actions_row.pack(side=RIGHT)
        ttk.Button(actions_row, text="Yenile", style="Secondary.TButton", command=self.refresh_logs).pack(side=LEFT)
        ttk.Button(actions_row, text="CSV Disa Aktar", style="Secondary.TButton", command=self.export_logs_to_csv).pack(
            side=LEFT, padx=(8, 0)
        )
        ttk.Button(actions_row, text="Gecmisi Temizle", style="Danger.TButton", command=self.clear_logs_with_confirm).pack(
            side=LEFT, padx=(8, 0)
        )

        table_box = ttk.Frame(history_box, style="HistoryCard.TFrame")
        table_box.pack(fill=BOTH, expand=True)
        tree_scrollbar = tk.Scrollbar(
            table_box,
            orient=VERTICAL,
            width=8,
            relief="flat",
            troughcolor="#0b1220",
            bg="#1f2937",
            activebackground="#334155",
            bd=0,
            highlightthickness=0,
        )
        columns = ("timestamp", "task", "status", "details")
        self.log_tree = ttk.Treeview(table_box, columns=columns, show="headings", height=8)
        self.log_tree.heading("timestamp", text="Zaman")
        self.log_tree.heading("task", text="Görev")
        self.log_tree.heading("status", text="Durum")
        self.log_tree.heading("details", text="Detay")
        self.log_tree.column("timestamp", width=135, anchor="center")
        self.log_tree.column("task", width=230, anchor="w")
        self.log_tree.column("status", width=80, anchor="center")
        self.log_tree.column("details", width=390, anchor="w")
        self.log_tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.configure(command=self.log_tree.yview)
        self.log_tree.pack(side=LEFT, fill=BOTH, expand=True)
        tree_scrollbar.pack(side=RIGHT, fill=Y)

        self.content_pane.add(output_box, weight=3)
        self.content_pane.add(history_box, weight=1)

    def append_output(self, message: str) -> None:
        self.output_text.insert(END, message + "\n")
        self.output_text.see(END)
        self.output_text.update_idletasks()

    def set_controls(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.run_btn.configure(state=state)
        self.quick_btn.configure(state=state)
        self.custom_run_btn.configure(state=state)
        self.custom_command_entry.configure(state=state)
        self.category_combo.configure(state="readonly" if enabled else "disabled")
        self.task_listbox.configure(state=state)

    def _get_selected_tasks(self) -> list[tuple[str, dict]]:
        return [(task_name, TASKS[task_name]) for task_name in sorted(self.selected_task_names)]

    def render_task_checkboxes(self) -> None:
        selected_category = self.category_var.get()
        if selected_category == "Tümü":
            self.visible_task_names = list(TASKS.keys())
        else:
            self.visible_task_names = [
                name for name, task in TASKS.items() if task.get("category") == selected_category
            ]

        self.task_listbox.delete(0, END)
        self.visible_task_display_names = []
        for task_name in self.visible_task_names:
            config = TASKS[task_name]
            label = f"{task_name}{' [Admin]' if config.get('requires_admin') else ''}"
            self.visible_task_display_names.append(task_name)
            self.task_listbox.insert(END, label)

        for index, task_name in enumerate(self.visible_task_display_names):
            if task_name in self.selected_task_names:
                self.task_listbox.selection_set(index)
        self.visible_tasks_var.set(f"Gorunen: {len(self.visible_task_display_names)}")
        self.update_selection_summary()

    def select_visible_tasks(self) -> None:
        for task_name in self.visible_task_display_names:
            self.selected_task_names.add(task_name)
        self._sync_listbox_selection_from_set()
        self.update_selection_summary()

    def clear_visible_tasks(self) -> None:
        for task_name in self.visible_task_display_names:
            self.selected_task_names.discard(task_name)
        self._sync_listbox_selection_from_set()
        self.update_selection_summary()

    def update_selection_summary(self) -> None:
        selected_count = len(self.selected_task_names)
        admin_count = sum(1 for name in self.selected_task_names if TASKS[name].get("requires_admin"))
        self.selection_summary_var.set(f"Secili gorev: {selected_count}")
        self.admin_required_var.set(f"Admin gerektiren: {admin_count}")
        admin_mode_enabled = is_admin()
        self.admin_note_var.set(f"Admin modu: {'Acik' if admin_mode_enabled else 'Kapali'}")
        self.admin_required_badge.configure(style="StatusWarn.TLabel" if admin_count > 0 else "StatusGood.TLabel")
        self.admin_mode_badge.configure(style="StatusGood.TLabel" if admin_mode_enabled else "StatusNeutral.TLabel")
        self.visible_tasks_var.set(f"Gorunen: {len(self.visible_task_display_names)} | Secili: {selected_count}")

    def on_task_listbox_select(self, _event=None) -> None:
        visible_set = set(self.visible_task_display_names)
        self.selected_task_names = {name for name in self.selected_task_names if name not in visible_set}
        for index in self.task_listbox.curselection():
            if 0 <= index < len(self.visible_task_display_names):
                self.selected_task_names.add(self.visible_task_display_names[index])
        self.update_selection_summary()

    def _sync_listbox_selection_from_set(self) -> None:
        self.task_listbox.selection_clear(0, END)
        for index, task_name in enumerate(self.visible_task_display_names):
            if task_name in self.selected_task_names:
                self.task_listbox.selection_set(index)

    def run_selected_tasks(self) -> None:
        selected_tasks = self._get_selected_tasks()
        if not selected_tasks:
            messagebox.showinfo("Bilgi", "En az bir görev seçmelisin.")
            return

        if any(task.get("requires_admin") for _, task in selected_tasks) and not is_admin():
            messagebox.showwarning("Yönetici Yetkisi Gerekli", "Seçili görevler yönetici gerektiriyor.")
            return

        self.output_text.delete("1.0", END)
        self.append_output(f"Toplu görev başlatıldı. Görev sayısı: {len(selected_tasks)}")
        self.set_controls(False)
        thread = threading.Thread(target=self._run_batch_worker, args=(selected_tasks,), daemon=True)
        thread.start()

    def run_quick_maintenance(self) -> None:
        quick_tasks = [
            ("Geçici Dosyaları Temizle", TASKS["Geçici Dosyaları Temizle"]),
            (
                "DNS Önbelleğini Temizle (ipconfig /flushdns)",
                TASKS["DNS Önbelleğini Temizle (ipconfig /flushdns)"],
            ),
        ]
        if not is_admin():
            messagebox.showwarning("Yönetici Yetkisi Gerekli", "Hızlı bakım için yönetici izni gerekli.")
            return
        self.output_text.delete("1.0", END)
        self.append_output("Hızlı bakım başlatıldı...")
        self.set_controls(False)
        thread = threading.Thread(target=self._run_batch_worker, args=(quick_tasks,), daemon=True)
        thread.start()

    def run_custom_command(self) -> None:
        command = self.custom_command_var.get().strip()
        if not command:
            messagebox.showinfo("Bilgi", "Çalıştırmak için bir komut gir.")
            return
        if self.custom_admin_var.get() and not is_admin():
            messagebox.showwarning("Yönetici Yetkisi Gerekli", "Bu özel komut yönetici yetkisi gerektiriyor.")
            return
        self.output_text.delete("1.0", END)
        self.append_output(f"Özel komut başlatıldı: {command}")
        self.set_controls(False)
        thread = threading.Thread(
            target=self._run_task_worker,
            args=("Özel Komut", {"type": "command", "command": command}),
            daemon=True,
        )
        thread.start()

    def _run_batch_worker(self, tasks: list[tuple[str, dict]]) -> None:
        for index, (task_name, task) in enumerate(tasks, start=1):
            self.after(0, self.append_output, f"[{index}/{len(tasks)}] Çalışıyor: {task_name}")
            self._run_task_worker(task_name, task, manage_controls=False)
        self.after(0, self.append_output, "Toplu görevler tamamlandı.")
        self.after(0, self.set_controls, True)
        self.after(0, self.refresh_logs)

    def _run_task_worker(self, task_name: str, task: dict, manage_controls: bool = True) -> None:
        try:
            if task["type"] == "python":
                details, error_count = cleanup_temp_directories()
                status = "OK" if error_count == 0 else "Uyarı"
                self.after(0, self.append_output, details)
                add_log(task_name, status, details)
            else:
                command = task["command"]
                self.after(0, self.append_output, f"Komut: {command}")
                
                # Use a timeout for subprocess calls to prevent hanging
                process = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding='cp857', # Windows Turkish encoding
                    errors='replace',
                    timeout=300 # 5 minutes timeout
                )
                stdout = (process.stdout or "").strip()
                stderr = (process.stderr or "").strip()

                output = stdout if stdout else "(çıktı yok)"
                if stderr:
                    output += f"\nHata çıktısı: {stderr}"

                status = "OK" if process.returncode == 0 else "Hata"
                details = f"Çıkış kodu: {process.returncode}"

                self.after(0, self.append_output, output)
                self.after(0, self.append_output, details)
                add_log(task_name, status, details + f" | {output[:400]}")

        except subprocess.TimeoutExpired:
            error_msg = f"Hata: Görev zaman aşımına uğradı (5 dakika)."
            self.after(0, self.append_output, error_msg)
            add_log(task_name, "Hata", error_msg)
        except Exception as ex:
            error_msg = f"Beklenmeyen hata: {ex}"
            self.after(0, self.append_output, error_msg)
            add_log(task_name, "Hata", error_msg)
        finally:
            if manage_controls:
                self.after(0, self.set_controls, True)
                self.after(0, self.refresh_logs)

    def clear_logs_with_confirm(self) -> None:
        confirmed = messagebox.askyesno("OYAX - Onay", "Tüm işlem geçmişi silinsin mi?")
        if not confirmed:
            return
        clear_logs()
        self.refresh_logs()
        self.append_output("Log geçmişi temizlendi.")

    def export_logs_to_csv(self) -> None:
        save_path = filedialog.asksaveasfilename(
            title="Logları CSV Olarak Kaydet",
            defaultextension=".csv",
            filetypes=[("CSV dosyası", "*.csv")],
        )
        if not save_path:
            return

        try:
            with sqlite3.connect(DB_FILE) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT timestamp, task_name, status, details
                    FROM logs
                    ORDER BY id DESC
                    """
                )
                rows = cur.fetchall()

            with open(save_path, "w", newline="", encoding="utf-8-sig") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["timestamp", "task_name", "status", "details"])
                writer.writerows(rows)

            self.append_output(f"CSV dışa aktarma tamamlandı: {save_path}")
        except Exception as ex:
            error_msg = f"Dışa aktarma hatası: {ex}"
            self.append_output(error_msg)
            messagebox.showerror("Hata", error_msg)

    def open_about_dialog(self) -> None:
        about = tk.Toplevel(self)
        about.title("Hakkında")
        try:
            icon_path = resource_path("icon.ico")
            about.iconbitmap(icon_path)
        except:
            pass
        width = 560
        height = 340

        screen_width = about.winfo_screenwidth()
        screen_height = about.winfo_screenheight()

        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)

        about.geometry(f"{width}x{height}+{x}+{y}")
        about.resizable(False, False)
        about.configure(bg="#111827")
        about.transient(self)
        about.grab_set()

        container = ttk.Frame(about, style="Card.TFrame", padding=14)
        container.pack(fill=BOTH, expand=True)

        ttk.Label(container, text="OYAX - Windows Bakım Aracı", style="HeaderTitle.TLabel").pack(anchor="w")
        ttk.Label(container, text=f"Sürüm: {APP_VERSION}", style="HeaderSub.TLabel").pack(anchor="w", pady=(2, 0))
        ttk.Label(container, text=f"Geliştirici: {AUTHOR_NAME}", style="HeaderSub.TLabel").pack(anchor="w", pady=(0, 12))

        ttk.Label(
            container,
            text=(
                "Bu araç Windows bakım komutlarını tek panelde sunar.\n"
                "GitHub reposundan güncel versiyonları kontrol etmeyi unutmayın."
            ),
            style="Muted.TLabel",
        ).pack(anchor="w")

        status_var = tk.StringVar(value="Durum: Kontrol Edilmedi")
        latest_var = tk.StringVar(value="GitHub Repo: Kontrol Edilmedi")
        ttk.Label(container, textvariable=latest_var, style="HeaderSub.TLabel").pack(anchor="w", pady=(14, 4))
        ttk.Label(container, textvariable=status_var, style="HeaderSub.TLabel").pack(anchor="w", pady=(0, 10))

        button_row = ttk.Frame(container, style="Card.TFrame")
        button_row.pack(fill=X, pady=(8, 0))
        ttk.Button(
            button_row,
            text="GitHub Guncelleme Kontrolu",
            style="Primary.TButton",
            command=lambda: self.start_update_check(status_var, latest_var),
        ).pack(side=LEFT)
        ttk.Button(button_row, text="Kapat", style="Secondary.TButton", command=about.destroy).pack(
            side=RIGHT
        )

    def start_update_check(self, status_var: tk.StringVar, repo_var: tk.StringVar) -> None:
        status_var.set("Durum: Kontrol basladi...")
        thread = threading.Thread(
            target=self._update_check_worker,
            args=(status_var, repo_var),
            daemon=True,
        )
        thread.start()

    def _update_check_worker(self, status_var: tk.StringVar, repo_var: tk.StringVar) -> None:
        repo_name = "furkanyasarr0/OYAX"
        self.after(0, lambda: repo_var.set(f"GitHub Repo: {repo_name}"))
        
        url = f"https://api.github.com/repos/{repo_name}/releases/latest"
        try:
            request = urllib.request.Request(
                url,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "OyaxUpdater"},
            )
            with urllib.request.urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
            latest_tag = str(payload.get("tag_name", "")).strip()
            if not latest_tag:
                self.after(0, lambda: status_var.set("Durum: Release etiketi bulunamadi."))
                return

            latest_version = self.normalize_version(latest_tag)
            current_version = self.normalize_version(APP_VERSION)
            if self.compare_versions(latest_version, current_version) > 0:
                self.after(
                    0,
                    lambda: status_var.set(f"Durum: Yeni surum var ({latest_tag}) - mevcut: {APP_VERSION}"),
                )
            else:
                self.after(0, lambda: status_var.set(f"Durum: En Son Sürümü Kullanıyorsunuz! ({APP_VERSION})"))
        except Exception as ex:
            self.after(0, lambda: status_var.set(f"Durum: Guncelleme kontrol hatasi: {ex}"))

    def detect_github_repo(self) -> str | None:
        try:
            output = subprocess.check_output(
                ["git", "config", "--get", "remote.origin.url"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=3,
            ).strip()
            match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$", output)
            if not match:
                return None
            return f"{match.group('owner')}/{match.group('repo')}"
        except Exception:
            return None

    def normalize_version(self, raw_version: str) -> str:
        return raw_version.strip().lower().lstrip("v")

    def compare_versions(self, left: str, right: str) -> int:
        def parts(version: str) -> list[int]:
            nums = []
            for item in version.split("."):
                try:
                    nums.append(int(item))
                except ValueError:
                    nums.append(0)
            while len(nums) < 3:
                nums.append(0)
            return nums[:3]

        left_parts = parts(left)
        right_parts = parts(right)
        if left_parts > right_parts:
            return 1
        if left_parts < right_parts:
            return -1
        return 0

    def refresh_logs(self) -> None:
        for row in self.log_tree.get_children():
            self.log_tree.delete(row)

        status_filter = self.status_filter_var.get().strip()
        search_text = self.search_var.get().strip().lower()

        conditions = []
        params: list[str] = []

        if status_filter and status_filter != "Tümü":
            conditions.append("status = ?")
            params.append(status_filter)

        if search_text:
            conditions.append("(LOWER(task_name) LIKE ? OR LOWER(details) LIKE ?)")
            term = f"%{search_text}%"
            params.extend([term, term])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        try:
            with sqlite3.connect(DB_FILE) as conn:
                cur = conn.cursor()
                cur.execute(
                    f"""
                    SELECT timestamp, task_name, status, details
                    FROM logs
                    {where_clause}
                    ORDER BY id DESC
                    LIMIT 200
                    """,
                    params,
                )
                rows = cur.fetchall()
                cur.execute(
                    f"""
                    SELECT status, COUNT(*)
                    FROM logs
                    {where_clause}
                    GROUP BY status
                    """,
                    params,
                )
                status_counts = dict(cur.fetchall())
        except Exception as ex:
            print(f"Veritabani hatasi: {ex}")
            rows = []
            status_counts = {}

        for row in rows:
            self.log_tree.insert("", END, values=row)
        self.history_ok_var.set(f"OK: {status_counts.get('OK', 0)}")
        self.history_warn_var.set(f"Uyari: {status_counts.get('Uyarı', 0)}")
        self.history_err_var.set(f"Hata: {status_counts.get('Hata', 0)}")
        self.history_meta_var.set(f"Gosterilen kayit: {len(rows)}")


if __name__ == "__main__":
    app = MaintenanceApp()
    app.mainloop()
