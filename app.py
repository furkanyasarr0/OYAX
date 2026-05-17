import os
import sys
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import csv
import json
import webbrowser
import re
import urllib.request
import queue
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import END, BOTH, LEFT, RIGHT, X, Y, VERTICAL, BOTTOM, messagebox
import tkinter as tk
from tkinter import ttk, filedialog

# Windows DPI Scaling (Bulanık görünümü ve laptop ölçekleme sorunlarını çözer)
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# AppData yolunu bul ve Oyax klasörü yoksa oluştur
APPDATA_PATH = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'Oyax')
if not os.path.exists(APPDATA_PATH):
    os.makedirs(APPDATA_PATH)

DB_FILE = os.path.join(APPDATA_PATH, "maintenance_logs.db")
APP_VERSION = "1.2.8"
AUTHOR_NAME = "furkanysrr0"

TASK_CATEGORIES = {
    "Geçici Dosyalar ve Cache": [
        {"name": "Geçici Dosyaları Temizle", "requires_admin": False, "type": "python"},
        {
            "name": "Windows Temp Temizliği (powershell)",
            "requires_admin": True,
            "type": "command",
            "command": ["powershell", "-Command", "Get-ChildItem -Path C:\\Windows\\Temp -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"],
        },
        {
            "name": "Prefetch Temizliği",
            "requires_admin": True,
            "type": "command",
            "command": ["powershell", "-Command", "Remove-Item -Path C:\\Windows\\Prefetch\\* -Force -Recurse -ErrorAction SilentlyContinue"],
        },
        {
            "name": "Geri Dönüşüm Kutusu Temizle",
            "requires_admin": False,
            "type": "command",
            "command": ["powershell", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
        },
        {
            "name": "Microsoft Store Cache Sıfırla",
            "requires_admin": False,
            "type": "command",
            "command": ["wsreset.exe"],
        },
    ],
    "Ağ ve DNS": [
        {"name": "DNS Önbelleğini Temizle (ipconfig /flushdns)", "requires_admin": True, "type": "command", "command": ["ipconfig", "/flushdns"]},
        {"name": "DNS Önbelleğini Görüntüle", "requires_admin": False, "type": "command", "command": ["ipconfig", "/displaydns"]},
        {"name": "DNS Yeniden Kaydet (ipconfig /registerdns)", "requires_admin": True, "type": "command", "command": ["ipconfig", "/registerdns"]},
        {
            "name": "IP Adresini Yenile (release + renew)",
            "requires_admin": True,
            "type": "command",
            "command": ["powershell", "-Command", "ipconfig /release; ipconfig /renew"],
        },
        {"name": "ARP Cache Temizliği", "requires_admin": True, "type": "command", "command": ["arp", "-d", "*"]},
    ],
    "Ağ Sıfırlama": [
        {"name": "Winsock Sıfırla (netsh winsock reset)", "requires_admin": True, "type": "command", "command": ["netsh", "winsock", "reset"]},
        {"name": "TCP/IP Stack Sıfırla", "requires_admin": True, "type": "command", "command": ["netsh", "int", "ip", "reset"]},
        {"name": "Windows Güvenlik Duvarını Sıfırla", "requires_admin": True, "type": "command", "command": ["netsh", "advfirewall", "reset"]},
    ],
    "Sistem Sağlığı": [
        {"name": "SFC Taraması (sfc /scannow)", "requires_admin": True, "type": "command", "command": ["sfc", "/scannow"]},
        {"name": "DISM Health Check", "requires_admin": True, "type": "command", "command": ["DISM", "/Online", "/Cleanup-Image", "/CheckHealth"]},
        {"name": "DISM Scan Health", "requires_admin": True, "type": "command", "command": ["DISM", "/Online", "/Cleanup-Image", "/ScanHealth"]},
        {"name": "DISM Restore Health", "requires_admin": True, "type": "command", "command": ["DISM", "/Online", "/Cleanup-Image", "/RestoreHealth"]},
        {"name": "Disk Tarama (chkdsk /scan)", "requires_admin": True, "type": "command", "command": ["chkdsk", "/scan"]},
    ],
}

def build_task_map() -> dict:
    tasks: dict = {}
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
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def cleanup_temp_directories() -> tuple:
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
    try:
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

        self.configure(bg="#0f172a")

        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self._configure_styles()
        
        try:
            self.overrideredirect(True)
            # Uygulama açıldıktan hemen sonra görev çubuğu simgesini zorla göster
            self.after(100, lambda: (self.update_idletasks(), self._set_exstyle_for_taskbar()))
        except Exception:
            pass

        self.option_add("*TCombobox*Listbox.background", "#020617")
        self.option_add("*TCombobox*Listbox.foreground", "#f8fafc")
        self.option_add("*TCombobox*Listbox.selectBackground", "#3b82f6")
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

        self.advanced_mode = tk.BooleanVar(value=False)
        self.cancel_requested = False
        self.current_process = None
        self.task_queue = queue.Queue()
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)

        self.ensure_db()
        self._build_ui()

        self.center_window(500, 660)
        
        try:
            self.after(50, self.toggle_view)
            self.after(50, self.refresh_logs)
        except Exception:
            self.toggle_view()
            self.refresh_logs()
        
        self.process_queue()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        try:
            self._last_window_state = self.state()
        except Exception:
            self._last_window_state = 'normal'
            
        self.bind('<Configure>', self._on_configure)
        
        try:
            self.after(50, lambda: (self._set_maximize_box(False), self._install_wndproc_hook()))
        except Exception:
            pass

    def process_queue(self) -> None:
        try:
            while True:
                msg = self.task_queue.get_nowait()
                action = msg.get("action")
                
                if action == "append_output":
                    self.append_output(msg["message"])
                elif action == "add_log":
                    self.add_log(msg["task_name"], msg["status"], msg["details"])
                elif action == "update_progress":
                    self.progress_var.set(msg["value"])
                elif action == "finish_batch":
                    self.append_output("Toplu görevler tamamlandı veya iptal edildi.")
                    self.set_controls(True)
                    self.refresh_logs()
                    
                self.task_queue.task_done()
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_queue)

    def on_closing(self) -> None:
        self.cancel_requested = True
        if self.current_process:
            try:
                self.current_process.kill()
            except:
                pass
        try:
            self.conn.close()
        except Exception as ex:
            print(f"Kapanış hatası: {ex}")
        self.destroy()

    def ensure_db(self) -> None:
        with self.conn:
            self.conn.execute(
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

    def add_log(self, task_name: str, status: str, details: str) -> None:
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO logs (timestamp, task_name, status, details) VALUES (?, ?, ?, ?)",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), task_name, status, details),
                )
        except Exception as ex:
            self.after(0, self.append_output, f"SİSTEM HATASI (Log Kaydedilemedi): {ex}")

    def clear_logs(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM logs")

    def center_window(self, width: int, height: int) -> None:
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _set_maximize_box(self, enabled: bool) -> None:
        try:
            import ctypes
            hwnd = self.winfo_id()
            GWL_STYLE = -16
            WS_MAXIMIZEBOX = 0x00010000
            GetWindowLong = ctypes.windll.user32.GetWindowLongW
            SetWindowLong = ctypes.windll.user32.SetWindowLongW
            style = GetWindowLong(hwnd, GWL_STYLE)
            new_style = style | WS_MAXIMIZEBOX if enabled else style & ~WS_MAXIMIZEBOX
            if new_style != style:
                SetWindowLong(hwnd, GWL_STYLE, new_style)
                SWP_FLAGS = 0x0001 | 0x0002 | 0x0004 | 0x0020
                ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)
        except Exception:
            pass

    def _install_wndproc_hook(self) -> None:
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            GWLP_WNDPROC = -4
            WM_SYSCOMMAND = 0x0112
            SC_MAXIMIZE = 0xF030
            hwnd = self.winfo_id()
            
            try:
                user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
                user32.DefWindowProcW.restype = wintypes.LRESULT
            except Exception:
                pass

            WNDPROCTYPE = ctypes.WINFUNCTYPE(wintypes.LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

            def _wndproc(hWnd, msg, wParam, lParam):
                try:
                    if msg == WM_SYSCOMMAND:
                        cmd = int(wParam) & 0xFFF0
                        if cmd == SC_MAXIMIZE:
                            return wintypes.LRESULT(0)
                    orig = getattr(self, '_orig_wndproc', None)
                    if orig:
                        return orig(hWnd, msg, wParam, lParam)
                except Exception:
                    pass
                try:
                    return user32.DefWindowProcW(hWnd, msg, wParam, lParam)
                except Exception:
                    return wintypes.LRESULT(0)

            self._wnd_proc_ref = WNDPROCTYPE(_wndproc)
            
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                SetWindowLongPtr = user32.SetWindowLongPtrW
                GetWindowLongPtr = user32.GetWindowLongPtrW
            else:
                SetWindowLongPtr = user32.SetWindowLongW
                GetWindowLongPtr = user32.GetWindowLongW

            prev = GetWindowLongPtr(hwnd, GWLP_WNDPROC)
            if prev:
                self._orig_wndproc = WNDPROCTYPE(prev)
            else:
                self._orig_wndproc = None
            SetWindowLongPtr(hwnd, GWLP_WNDPROC, ctypes.cast(self._wnd_proc_ref, ctypes.c_void_p))
        except Exception:
            self._orig_wndproc = None
            self._wnd_proc_ref = None

    def _remove_wndproc_hook(self) -> None:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            GWLP_WNDPROC = -4
            hwnd = self.winfo_id()
            if hasattr(self, '_orig_wndproc') and self._orig_wndproc:
                SetWindowLongPtr = user32.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user32.SetWindowLongW
                try:
                    SetWindowLongPtr(hwnd, GWLP_WNDPROC, ctypes.cast(self._orig_wndproc, ctypes.c_void_p))
                except Exception:
                    pass
            self._orig_wndproc = None
            self._wnd_proc_ref = None
        except Exception:
            pass

    def _configure_styles(self) -> None:
        self.style.configure(".", font=("Segoe UI", 10))
        self.style.configure("App.TFrame", background="#0f172a")
        self.style.configure("Card.TFrame", background="#1e293b")
        self.style.configure("InnerCard.TFrame", background="#0f172a")
        
        self.style.configure("HeaderTitle.TLabel", background="#1e293b", foreground="#f8fafc", font=("Segoe UI", 18, "bold"))
        self.style.configure("HeaderSub.TLabel", background="#1e293b", foreground="#94a3b8", font=("Segoe UI", 10))
        self.style.configure("EULALink.TLabel", background="#1e293b", foreground="#3b82f6", font=("Segoe UI", 10, "underline"), cursor="hand2")
        
        self.style.configure("TaskMenuTitle.TLabel", background="#1e293b", foreground="#f8fafc", font=("Segoe UI", 12, "bold"))
        self.style.configure("TaskMenuSub.TLabel", background="#1e293b", foreground="#94a3b8", font=("Segoe UI", 9))
        self.style.configure("InnerTitle.TLabel", background="#0f172a", foreground="#f8fafc", font=("Segoe UI", 11, "bold"))
        self.style.configure("InnerSub.TLabel", background="#0f172a", foreground="#94a3b8", font=("Segoe UI", 9))
        
        self.style.configure("HistoryTitle.TLabel", background="#1e293b", foreground="#f8fafc", font=("Segoe UI", 12, "bold"))
        self.style.configure("HistorySub.TLabel", background="#1e293b", foreground="#94a3b8", font=("Segoe UI", 9))
        self.style.configure("Muted.TLabel", background="#1e293b", foreground="#94a3b8", font=("Segoe UI", 9))
        self.style.configure("TLabel", background="#1e293b", foreground="#e2e8f0")

        self.style.configure("StatusNeutral.TLabel", background="#334155", foreground="#f8fafc", font=("Segoe UI", 9, "bold"), padding=(8, 4))
        self.style.configure("StatusGood.TLabel", background="#064e3b", foreground="#34d399", font=("Segoe UI", 9, "bold"), padding=(8, 4))
        self.style.configure("StatusWarn.TLabel", background="#78350f", foreground="#fbbf24", font=("Segoe UI", 9, "bold"), padding=(8, 4))

        self.style.configure("Section.TLabelframe", background="#1e293b", foreground="#f8fafc", borderwidth=0, relief="flat")
        self.style.configure("Section.TLabelframe.Label", background="#1e293b", foreground="#f8fafc", font=("Segoe UI", 11, "bold"))

        self.style.configure("Primary.TButton", background="#3b82f6", foreground="#ffffff", borderwidth=0, padding=(0, 8), font=("Segoe UI", 10, "bold"))
        self.style.map("Primary.TButton", background=[("active", "#2563eb"), ("disabled", "#1e293b")], foreground=[("active", "#ffffff"), ("disabled", "#64748b")])
        
        self.style.configure("Secondary.TButton", background="#334155", foreground="#f8fafc", borderwidth=0, padding=(0, 8))
        self.style.map("Secondary.TButton", background=[("active", "#475569"), ("disabled", "#1e293b")], foreground=[("active", "#ffffff"), ("disabled", "#64748b")])
        
        self.style.configure("Danger.TButton", background="#ef4444", foreground="#ffffff", borderwidth=0, padding=(0, 8), font=("Segoe UI", 10, "bold"))
        self.style.map("Danger.TButton", background=[("active", "#dc2626"), ("disabled", "#1e293b")], foreground=[("active", "#ffffff"), ("disabled", "#64748b")])

        self.style.configure("TEntry", fieldbackground="#020617", foreground="#f8fafc", borderwidth=0, padding=8)
        self.style.map("TEntry", fieldbackground=[("readonly", "#020617"), ("disabled", "#111827")], foreground=[("readonly", "#f8fafc"), ("disabled", "#64748b")])
        
        self.style.configure("TCombobox", fieldbackground="#020617", background="#020617", foreground="#f8fafc", arrowcolor="#93c5fd", borderwidth=0, padding=6)
        self.style.map("TCombobox", fieldbackground=[("readonly", "#020617"), ("disabled", "#111827")], selectbackground=[("readonly", "#1e293b")], selectforeground=[("readonly", "#f8fafc")])
        
        self.style.configure("TCheckbutton", background="#1e293b", foreground="#f8fafc")
        self.style.map("TCheckbutton", background=[("active", "#1e293b")])

        self.style.configure("Treeview", background="#020617", fieldbackground="#020617", foreground="#e2e8f0", rowheight=30, borderwidth=0, font=("Segoe UI", 10))
        self.style.configure("Treeview.Heading", background="#0f172a", foreground="#f8fafc", font=("Segoe UI", 10, "bold"), borderwidth=0, padding=4)
        self.style.map("Treeview", background=[("selected", "#3b82f6")], foreground=[("selected", "#ffffff")])

        self.style.configure("TProgressbar", thickness=12, background="#3b82f6", troughcolor="#0f172a", borderwidth=0)

    def _on_configure(self, event) -> None:
        try:
            current_state = self.state()
        except Exception:
            current_state = 'normal'

        if self.advanced_mode.get() and current_state == 'zoomed':
            try:
                try:
                    self.attributes('-fullscreen', False)
                except Exception:
                    pass
                self.state('normal')
                self.after(20, self.toggle_view)
            except Exception:
                pass
        self._last_window_state = current_state

    def _start_move(self, event) -> None:
        try:
            self._drag_x = event.x
            self._drag_y = event.y
        except Exception:
            self._drag_x = 0
            self._drag_y = 0

    def _on_move(self, event) -> None:
        try:
            x = self.winfo_pointerx() - getattr(self, '_drag_x', 0)
            y = self.winfo_pointery() - getattr(self, '_drag_y', 0)
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _build_ui(self) -> None:
        # Üst Başlık Çubuğu
        title_bar = tk.Frame(self, bg="#0f172a", relief="raised", bd=0)
        title_bar.pack(fill=X, side=tk.TOP)
        title_bar.bind("<Button-1>", self._start_move)
        title_bar.bind("<B1-Motion>", self._on_move)

        title_label = tk.Label(title_bar, text="OYAX - Windows Bakım Aracı", bg="#0f172a", fg="#f8fafc", font=("Segoe UI", 11, "bold"))
        title_label.pack(side=LEFT, padx=(10, 6))
        title_label.bind("<Button-1>", self._start_move)
        title_label.bind("<B1-Motion>", self._on_move)

        btn_frame = tk.Frame(title_bar, bg="#0f172a")
        btn_frame.pack(side=RIGHT, padx=6)

        def _minimize():
            try:
                try: self.overrideredirect(False)
                except Exception: pass
                
                try: self._set_exstyle_for_taskbar()
                except Exception: pass

                try:
                    self._create_taskbar_placeholder()
                    self.withdraw()
                except Exception:
                    try:
                        import ctypes
                        user32 = ctypes.windll.user32
                        user32.ShowWindow(self.winfo_id(), 6)
                    except Exception:
                        try: self.iconify()
                        except Exception: pass
            except Exception:
                pass

        def _close():
            try: self.on_closing()
            except Exception: 
                try: self.destroy()
                except Exception: pass

        close_btn = tk.Button(btn_frame, text="✕", command=_close, bg="#0f172a", fg="#f8fafc", relief="flat", bd=0, padx=8, pady=2)
        close_btn.pack(side=RIGHT)
        
        try:
            def _on_map(event=None):
                try:
                    def _restore():
                        try:
                            try: self.overrideredirect(True)
                            except Exception: pass
                            try: self._restore_exstyle()
                            except Exception: pass
                        except Exception: pass
                    self.after(10, _restore)
                except Exception: pass
            self.bind('<Map>', _on_map)
        except Exception:
            pass

        # --- SORUNLU KISIM BURADAN İTİBAREN DÜZELTİLDİ ---
        # Arayüzü tutan ana Container
        main_frame = ttk.Frame(self, style="App.TFrame", padding=10)
        main_frame.pack(fill=BOTH, expand=True)

        left_panel = ttk.Frame(main_frame, style="Card.TFrame", padding=12, width=480)
        left_panel.pack(side=LEFT, fill=Y, padx=(0, 10))
        left_panel.pack_propagate(False)

        header_row = ttk.Frame(left_panel, style="Card.TFrame")
        header_row.pack(fill=X)
        ttk.Label(header_row, text="Görev Menüsü", style="TaskMenuTitle.TLabel").pack(side=LEFT)
        self.view_toggle = ttk.Checkbutton(
            header_row,
            text="Gelişmiş Görünüm",
            variable=self.advanced_mode,
            command=self.toggle_view,
            style="TCheckbutton"
        )
        self.view_toggle.pack(side=RIGHT)

        ttk.Label(left_panel, text="Kategoriye göre filtrele ve görev seçimi yap.", style="TaskMenuSub.TLabel").pack(anchor="w", pady=(2, 10))

        status_box = ttk.Frame(left_panel, style="InnerCard.TFrame", padding=10)
        status_box.pack(fill=X, pady=(0, 10))
        self.selection_summary_var = tk.StringVar(value="Seçili görev: 0")
        ttk.Label(status_box, textvariable=self.selection_summary_var, style="InnerTitle.TLabel").pack(anchor="w")
        
        badge_row = ttk.Frame(status_box, style="InnerCard.TFrame")
        badge_row.pack(fill=X, pady=(6, 0))
        self.admin_required_var = tk.StringVar(value="Admin gerektiren: 0")
        self.admin_required_badge = ttk.Label(badge_row, textvariable=self.admin_required_var, style="StatusNeutral.TLabel")
        self.admin_required_badge.pack(side=LEFT)
        self.admin_note_var = tk.StringVar(value="Admin modu: Kapalı")
        self.admin_mode_badge = ttk.Label(badge_row, textvariable=self.admin_note_var, style="StatusNeutral.TLabel")
        self.admin_mode_badge.pack(side=LEFT, padx=(8, 0))

        action_box = ttk.Frame(left_panel, style="Card.TFrame")
        action_box.pack(side=tk.BOTTOM, fill=X)
        ttk.Separator(action_box).pack(fill=X, pady=(4, 8))

        run_row = ttk.Frame(action_box, style="Card.TFrame")
        run_row.pack(fill=X, pady=(0, 6))
        self.run_btn = ttk.Button(run_row, text="Seçili Görevleri Çalıştır", style="Primary.TButton", command=self.run_selected_tasks)
        self.run_btn.pack(side=LEFT, fill=X, expand=True, padx=(0, 4))
        self.cancel_btn = ttk.Button(run_row, text="İptal Et", style="Danger.TButton", command=self.request_cancel, state="disabled")
        self.cancel_btn.pack(side=LEFT, fill=X, expand=True, padx=(4, 0))

        maintenance_row = ttk.Frame(action_box, style="Card.TFrame")
        maintenance_row.pack(fill=X, pady=(0, 6))
        self.winget_btn = ttk.Button(maintenance_row, text="Winget Güncelle", style="Secondary.TButton", command=self.run_winget_upgrade_all)
        self.winget_btn.pack(side=LEFT, fill=X, expand=True, padx=(0, 2))
        self.quick_btn = ttk.Button(maintenance_row, text="Hızlı Bakım", style="Secondary.TButton", command=self.run_quick_maintenance)
        self.quick_btn.pack(side=LEFT, fill=X, expand=True, padx=(2, 2))
        ttk.Button(maintenance_row, text="Hakkında", style="Secondary.TButton", command=self.open_about_dialog).pack(side=LEFT, fill=X, expand=True, padx=(2, 0))
        
        self.simple_status_var = tk.StringVar(value="Durum: Bekleniyor...")
        self.simple_status_label = ttk.Label(action_box, textvariable=self.simple_status_var, style="Muted.TLabel", wraplength=440)
        self.simple_status_label.pack(fill=X, pady=(2, 6))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(action_box, variable=self.progress_var, maximum=100, style="TProgressbar")
        self.progress_bar.pack(fill=X, pady=(0, 2))

        menu_content = ttk.Frame(left_panel, style="Card.TFrame")
        menu_content.pack(side=tk.TOP, fill=BOTH, expand=True)

        filter_box = ttk.Frame(menu_content, style="InnerCard.TFrame", padding=10)
        filter_box.pack(fill=X, pady=(0, 8))
        
        filter_controls = ttk.Frame(filter_box, style="InnerCard.TFrame")
        filter_controls.pack(fill=X)
        
        ttk.Label(filter_controls, text="Kategori: ", style="InnerSub.TLabel").pack(side=LEFT)
        self.category_var = tk.StringVar(value="Tümü")
        category_values = ["Tümü"] + list(TASK_CATEGORIES.keys())
        self.category_combo = ttk.Combobox(filter_controls, textvariable=self.category_var, values=category_values, state="readonly", width=18)
        self.category_combo.pack(side=LEFT, fill=X, expand=True, padx=(0, 6))
        self.category_combo.bind("<<ComboboxSelected>>", lambda _e: self.render_task_checkboxes())

        ttk.Button(filter_controls, text="Tümünü Seç", style="Secondary.TButton", command=self.select_visible_tasks).pack(side=LEFT, padx=(0, 4))
        ttk.Button(filter_controls, text="Temizle", style="Secondary.TButton", command=self.clear_all_tasks).pack(side=LEFT)

        task_header = ttk.Frame(menu_content, style="Card.TFrame")
        task_header.pack(fill=X, pady=(2, 6))
        ttk.Label(task_header, text="Uygulanabilir Görevler", style="TaskMenuTitle.TLabel").pack(side=LEFT)
        self.visible_tasks_var = tk.StringVar(value="Görünen: 0")
        ttk.Label(task_header, textvariable=self.visible_tasks_var, style="TaskMenuSub.TLabel").pack(side=RIGHT)
        
        task_list_box = ttk.Frame(menu_content, style="InnerCard.TFrame", padding=4)
        task_list_box.pack(fill=BOTH, expand=True, pady=(0, 4))

        task_canvas = tk.Canvas(task_list_box, bg="#020617", relief="flat", bd=0, highlightthickness=0)
        task_scrollbar = tk.Scrollbar(task_list_box, orient=VERTICAL, width=10, relief="flat", troughcolor="#020617", bg="#1e293b", activebackground="#334155", bd=0, highlightthickness=0, command=task_canvas.yview)
        self.scrollable_task_frame = tk.Frame(task_canvas, bg="#020617")
        self.scrollable_task_frame.bind("<Configure>", lambda _e: task_canvas.configure(scrollregion=task_canvas.bbox("all")))
        task_canvas_window = task_canvas.create_window((0, 0), window=self.scrollable_task_frame, anchor="nw")
        task_canvas.configure(yscrollcommand=task_scrollbar.set)
        task_canvas.bind("<Configure>", lambda e: task_canvas.itemconfigure(task_canvas_window, width=e.width))
        task_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        task_scrollbar.pack(side=RIGHT, fill=Y)
        
        def _on_mousewheel(event):
            task_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        def _bound_to_mousewheel(event):
            task_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _unbound_to_mousewheel(event):
            task_canvas.unbind_all("<MouseWheel>")
            
        task_canvas.bind('<Enter>', _bound_to_mousewheel)
        task_canvas.bind('<Leave>', _unbound_to_mousewheel)

        self.selected_task_names = set()
        self.visible_task_names = []
        self.visible_task_display_names = []
        self.render_task_checkboxes()

        self.right_panel = ttk.Frame(main_frame, style="App.TFrame")
        self.right_panel.pack(side=RIGHT, fill=BOTH, expand=True)

        self.content_pane = ttk.PanedWindow(self.right_panel, orient=tk.VERTICAL)
        self.content_pane.pack(fill=BOTH, expand=True)

        output_box = ttk.LabelFrame(self.content_pane, text="Canlı Çıktı", style="Section.TLabelframe", padding=8)
        self.output_text = tk.Text(
            output_box, height=10, wrap="word", bg="#020617", fg="#f8fafc",
            insertbackground="#3b82f6", relief="flat", padx=12, pady=12, font=("Consolas", 10)
        )
        self.output_text.pack(fill=BOTH, expand=True)

        history_box = ttk.LabelFrame(self.content_pane, text="İşlem Geçmişi (SQLite)", style="Section.TLabelframe", padding=12)
        self.history_box = history_box

        history_header = ttk.Frame(history_box, style="Card.TFrame")
        history_header.pack(fill=X, pady=(0, 12))
        ttk.Label(history_header, text="İşlem Geçmişi", style="HistoryTitle.TLabel").pack(side=LEFT)
        self.history_meta_var = tk.StringVar(value="Son 200 kayıt")

        history_actions = ttk.Frame(history_header, style="Card.TFrame")
        history_actions.pack(side=RIGHT, padx=(8, 0))
        ttk.Button(history_actions, text="Yenile", style="Secondary.TButton", command=self.refresh_logs).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(history_actions, text="Temizle", style="Danger.TButton", command=self.clear_logs_with_confirm).pack(side=RIGHT)

        history_stats = ttk.Frame(history_box, style="Card.TFrame")
        history_stats.pack(fill=X, pady=(0, 12))
        self.history_ok_var = tk.StringVar(value="OK: 0")
        self.history_warn_var = tk.StringVar(value="Uyarı: 0")
        self.history_err_var = tk.StringVar(value="Hata: 0")
        ttk.Label(history_stats, textvariable=self.history_ok_var, style="StatusGood.TLabel").pack(side=LEFT)
        ttk.Label(history_stats, textvariable=self.history_warn_var, style="StatusWarn.TLabel").pack(side=LEFT, padx=(10, 0))
        ttk.Label(history_stats, textvariable=self.history_err_var, style="StatusNeutral.TLabel").pack(side=LEFT, padx=(10, 0))

        filter_row = ttk.Frame(history_box, style="Card.TFrame")
        filter_row.pack(fill=X, pady=(0, 12))

        ttk.Label(filter_row, text="Tarih:", style="HistorySub.TLabel").pack(side=LEFT)
        self.date_filter_var = tk.StringVar(value="Tümü")
        date_combo = ttk.Combobox(filter_row, textvariable=self.date_filter_var, values=["Tümü", "Bugün", "Son 7 Gün", "Son 30 Gün"], state="readonly", width=12)
        date_combo.pack(side=LEFT, padx=(8, 16))
        date_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_logs())

        ttk.Label(filter_row, text="Durum:", style="HistorySub.TLabel").pack(side=LEFT)
        self.status_filter_var = tk.StringVar(value="Tümü")
        status_combo = ttk.Combobox(filter_row, textvariable=self.status_filter_var, values=["Tümü", "OK", "Uyarı", "Hata"], state="readonly", width=10)
        status_combo.pack(side=LEFT, padx=(8, 16))
        status_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_logs())

        ttk.Label(filter_row, text="Ara:", style="HistorySub.TLabel").pack(side=LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_row, textvariable=self.search_var, width=22)
        search_entry.pack(side=LEFT, padx=(8, 12))
        search_entry.bind("<KeyRelease>", lambda _e: self.refresh_logs())

        ttk.Label(filter_row, textvariable=self.history_meta_var, style="HistorySub.TLabel").pack(side=LEFT, padx=(8, 12))

        table_box = ttk.Frame(history_box, style="Card.TFrame")
        table_box.pack(fill=BOTH, expand=True)

        tree_v_scrollbar = tk.Scrollbar(table_box, orient=VERTICAL, width=10, relief="flat", troughcolor="#020617", bg="#1e293b", activebackground="#334155", bd=0, highlightthickness=0)
        tree_h_scrollbar = tk.Scrollbar(table_box, orient=tk.HORIZONTAL, troughcolor="#020617", bg="#1e293b", activebackground="#334155", bd=0, highlightthickness=0)

        columns = ("timestamp", "task", "status", "details")
        self.log_tree = ttk.Treeview(table_box, columns=columns, show="headings")
        self.log_tree.heading("timestamp", text="Zaman")
        self.log_tree.heading("task", text="Görev")
        self.log_tree.heading("status", text="Durum")
        self.log_tree.heading("details", text="Detay")

        self.log_tree.column("timestamp", width=145, anchor="center")
        self.log_tree.column("task", width=240, anchor="w")
        self.log_tree.column("status", width=90, anchor="center")
        self.log_tree.column("details", width=380, anchor="w")

        self.log_tree.configure(yscrollcommand=tree_v_scrollbar.set, xscrollcommand=tree_h_scrollbar.set)
        tree_v_scrollbar.configure(command=self.log_tree.yview)
        tree_h_scrollbar.configure(command=self.log_tree.xview)

        self.log_tree.pack(side=LEFT, fill=BOTH, expand=True)
        tree_v_scrollbar.pack(side=RIGHT, fill=Y)
        tree_h_scrollbar.pack(side=BOTTOM, fill=X)

        def _adjust_log_columns(event=None):
            try:
                total_width = table_box.winfo_width()
                vs_width = tree_v_scrollbar.winfo_width() or 10
                usable = max(200, total_width - vs_width - 8)
                w_timestamp = int(usable * 0.18)
                w_task = int(usable * 0.36)
                w_status = int(usable * 0.12)
                w_details = max(80, usable - (w_timestamp + w_task + w_status))

                self.log_tree.column("timestamp", width=w_timestamp)
                self.log_tree.column("task", width=w_task)
                self.log_tree.column("status", width=w_status)
                self.log_tree.column("details", width=w_details)
            except Exception:
                pass

        table_box.bind("<Configure>", _adjust_log_columns)
        self.log_tree.bind("<Double-1>", self.show_log_details_dialog)

        self.content_pane.add(output_box, weight=2)
        self.content_pane.add(history_box, weight=3)

    def _set_exstyle_for_taskbar(self) -> None:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_APPWINDOW = 0x00040000
            
            # Tkinter'da görev çubuğu simgesini yönetmek için ana sarmalayıcı (wrapper) id'si gerekebilir
            hwnd = user32.GetParent(self.winfo_id())
            if not hwnd:
                hwnd = self.winfo_id()
                
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                GetWindowLongPtr = user32.GetWindowLongPtrW
                SetWindowLongPtr = user32.SetWindowLongPtrW
            else:
                GetWindowLongPtr = user32.GetWindowLongW
                SetWindowLongPtr = user32.SetWindowLongW

            ex = GetWindowLongPtr(hwnd, GWL_EXSTYLE)
            new = (ex & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            if new != ex:
                SetWindowLongPtr(hwnd, GWL_EXSTYLE, new)
                SWP_FLAGS = 0x0001 | 0x0002 | 0x0020
                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)
        except Exception:
            pass

    def _restore_exstyle(self) -> None:
        # Eski haline (gizli simge) döndürmek yerine her zaman görev çubuğunda kalmasını sağla
        self._set_exstyle_for_taskbar()

    def _create_taskbar_placeholder(self) -> None:
        try:
            if hasattr(self, '_placeholder') and self._placeholder:
                return

            ph = tk.Toplevel()
            ph.title("OYAX")
            ph.geometry('240x80')
            ph.configure(bg='#0f172a')
            try:
                ph.attributes('-topmost', False)
            except Exception:
                pass

            lbl = tk.Label(ph, text='OYAX (tıklayarak geri getir)', bg='#0f172a', fg='#f8fafc')
            lbl.pack(expand=True, fill=BOTH, padx=8, pady=8)

            def _on_click(_e=None):
                try:
                    try: ph.destroy()
                    except Exception: pass
                    self.deiconify()
                    try: self.overrideredirect(True)
                    except Exception: pass
                    try: self._restore_exstyle()
                    except Exception: pass
                except Exception:
                    pass

            ph.bind('<Button-1>', _on_click)
            ph.protocol('WM_DELETE_WINDOW', lambda: None)
            self._placeholder = ph
        except Exception:
            pass

    def toggle_view(self) -> None:
        if not hasattr(self, 'right_panel'):
            try: self.after(50, self.toggle_view)
            except Exception: pass
            return
            
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        target_height = min(720, int(screen_height * 0.85))

        if self.state() == 'zoomed':
            self.state('normal')

        if self.advanced_mode.get():
            self.resizable(True, True)
            try: self.attributes('-fullscreen', False)
            except Exception: pass

            try: self.after(50, lambda: self._set_maximize_box(False))
            except Exception: self._set_maximize_box(False)

            min_w, min_h = 1180, 600
            max_w = min(int(screen_width * 0.85), 1600)
            max_h = min(int(screen_height * 0.85), target_height)

            if min_w > max_w: min_w = max_w
            if min_h > max_h: min_h = max_h

            self.minsize(min_w, min_h)
            self.maxsize(max_w, max_h)

            self.right_panel.pack(side=RIGHT, fill=BOTH, expand=True)
            width = min(1180, int(screen_width * 0.7), max_w)
            height = min(target_height, int(screen_height * 0.7), max_h)
            self.center_window(width, height)
        else:
            self.right_panel.pack_forget()
            small_w, small_h = 500, max(600, min(target_height, screen_height - 40))
            self.minsize(small_w, 600)
            self.maxsize(small_w, small_h)
            self.center_window(small_w, small_h)
            self.resizable(False, False)

            try: self.after(50, lambda: self._set_maximize_box(False))
            except Exception: self._set_maximize_box(False)

    def append_output(self, message: str) -> None:
        short_msg = message.split('\n')[0][:80]
        if len(message.split('\n')[0]) > 80:
            short_msg += "..."
        self.simple_status_var.set(f"Durum: {short_msg}")
        self.output_text.insert(END, message + "\n")
        self.output_text.see(END)
        self.output_text.update_idletasks()
        self.simple_status_label.update_idletasks()

    def set_controls(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        cancel_state = "disabled" if enabled else "normal"

        self.run_btn.configure(state=state)
        self.winget_btn.configure(state=state)
        self.quick_btn.configure(state=state)
        self.category_combo.configure(state="readonly" if enabled else "disabled")
        self.cancel_btn.configure(state=cancel_state)
        
        if hasattr(self, "scrollable_task_frame"):
            for child in self.scrollable_task_frame.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(state=state)
        
        if enabled:
            self.progress_var.set(0)
            self.simple_status_var.set("Durum: Bekleniyor...")

    def request_cancel(self) -> None:
        # Note: messagebox is available from tkinter imports
        self.cancel_requested = True
        if self.current_process:
            try:
                self.current_process.kill()
            except Exception as e:
                print(f"Kill error: {e}")
        self.append_output("⚠️ İptal isteği alındı. Sıradaki görevler durduruluyor...")

    def _get_selected_tasks(self) -> list:
        return [(task_name, TASKS[task_name]) for task_name in sorted(self.selected_task_names)]

    def render_task_checkboxes(self) -> None:
        selected_category = self.category_var.get()
        
        for widget in self.scrollable_task_frame.winfo_children():
            widget.destroy()
            
        self.visible_task_display_names = []
        
        if selected_category == "Kategori Seçiniz...":
            self.visible_task_names = []
            lbl = tk.Label(self.scrollable_task_frame, text=" ℹ️  Lütfen işlem yapmak için bir kategori seçin...", bg="#020617", fg="#64748b", font=("Segoe UI", 10), anchor="w")
            lbl.pack(fill=X, padx=5, pady=10)
            self.visible_tasks_var.set("Görünen: 0")
            self.update_selection_summary()
            return
            
        if selected_category == "Tümü":
            self.visible_task_names = list(TASKS.keys())
        else:
            self.visible_task_names = [name for name, task in TASKS.items() if task.get("category") == selected_category]

        for task_name in self.visible_task_names:
            config = TASKS[task_name]
            self.visible_task_display_names.append(task_name)
            
            is_selected = task_name in self.selected_task_names
            admin_suffix = " [Admin]" if config.get('requires_admin') else ""
            
            prefix = "✓  " if is_selected else "•  "
            text_color = "#38bdf8" if is_selected else "#cbd5e1"
            bg_color = "#0f172a" if is_selected else "#020617"
            
            lbl = tk.Label(
                self.scrollable_task_frame,
                text=f"  {prefix}{task_name}{admin_suffix}",
                bg=bg_color,
                fg=text_color,
                font=("Segoe UI", 10),
                anchor="w",
                cursor="hand2"
            )
            lbl.bind("<Button-1>", lambda e, t=task_name: self.on_task_toggle(t))
            lbl.pack(fill=X, padx=2, pady=1)

        self.visible_tasks_var.set(f"Görünen: {len(self.visible_task_display_names)}")
        self.update_selection_summary()

    def on_task_toggle(self, task_name: str) -> None:
        if task_name in self.selected_task_names:
            self.selected_task_names.remove(task_name)
        else:
            self.selected_task_names.add(task_name)
        self.render_task_checkboxes()

    def select_visible_tasks(self) -> None:
        if self.category_var.get() == "Kategori Seçiniz...":
            return
        for task_name in self.visible_task_display_names:
            self.selected_task_names.add(task_name)
        self.render_task_checkboxes()

    def clear_all_tasks(self) -> None:
        self.selected_task_names.clear()
        self.render_task_checkboxes()

    def update_selection_summary(self) -> None:
        selected_count = len(self.selected_task_names)
        admin_count = sum(1 for name in self.selected_task_names if TASKS[name].get("requires_admin"))
        self.selection_summary_var.set(f"Seçili görev: {selected_count}")
        self.admin_required_var.set(f"Admin gerektiren: {admin_count}")
        admin_mode_enabled = is_admin()
        self.admin_note_var.set(f"Admin Modu: {'Açık' if admin_mode_enabled else 'Kapalı'}")
        self.admin_required_badge.configure(style="StatusWarn.TLabel" if admin_count > 0 else "StatusGood.TLabel")
        self.admin_mode_badge.configure(style="StatusGood.TLabel" if admin_mode_enabled else "StatusNeutral.TLabel")
        self.visible_tasks_var.set(f"Görünen: {len(self.visible_task_display_names)} | Seçili: {selected_count}")

    def restart_as_admin(self) -> None:
        try:
            import ctypes
            if getattr(sys, 'frozen', False):
                executable = sys.executable
                params = ""
            else:
                executable = sys.executable
                params = f'"{os.path.abspath(sys.argv[0])}"'
            
            result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
            if result > 32:
                self.destroy()
                sys.exit()
            else:
                error_msg = "Yönetici izni alınamadı veya işlem reddedildi."
                self.task_queue.put({"action": "add_log", "task_name": "SİSTEM YETKİLENDİRME", "status": "Hata", "details": error_msg})
        except Exception as e:
            error_msg = f"Yeniden başlatma sırasında bir hata oluştu: {e}"
            self.task_queue.put({"action": "add_log", "task_name": "SİSTEM YETKİLENDİRME", "status": "Hata", "details": error_msg})

    def run_selected_tasks(self) -> None:
        selected_tasks = self._get_selected_tasks()
        if not selected_tasks:
            messagebox.showwarning("Uyarı", "Lütfen işlem yapmak için en az bir görev seçin.")
            return

        # 1. Admin yetkisi kontrolü ve onayı
        if any(task.get("requires_admin") for _, task in selected_tasks) and not is_admin():
            if messagebox.askyesno("Yönetici İzni Gerekli", "Seçili görevlerden bazıları yönetici yetkisi gerektiriyor.\n\nİşleme devam edebilmek için uygulamayı yönetici olarak yeniden başlatmak ister misin?"):
                self.restart_as_admin()
            return

        # 2. İşlemi başlatma onayı
        if not messagebox.askyesno("Onay", f"Seçilen {len(selected_tasks)} görevi çalıştırmak istediğine emin misin?"):
            return

        self.output_text.delete("1.0", END)
        self.append_output(f"Toplu görev başlatıldı. Görev sayısı: {len(selected_tasks)}")
        self.set_controls(False)
        thread = threading.Thread(target=self._run_batch_worker, args=(selected_tasks,), daemon=True)
        thread.start()

    def run_winget_upgrade_all(self) -> None:
        if not is_admin():
            if messagebox.askyesno("Yönetici İzni Gerekli", "Winget güncellemesi yönetici yetkisi gerektiriyor.\n\nUygulamayı yönetici olarak yeniden başlatmak ister misin?"):
                self.restart_as_admin()
            return
            
        if not messagebox.askyesno("Onay", "Winget ile tüm sistem paketlerini güncellemek istediğine emin misin?"):
            return

        self.output_text.delete("1.0", END)
        self.append_output("Winget tüm paketler güncelleniyor...")
        self.set_controls(False)
        winget_task = [("Winget Tümünü Güncelle", {"type": "command", "command": ["winget", "upgrade", "--all"]})]
        thread = threading.Thread(target=self._run_batch_worker, args=(winget_task,), daemon=True)
        thread.start()

    def run_quick_maintenance(self) -> None:
        quick_tasks = [
            ("Geçici Dosyaları Temizle", TASKS["Geçici Dosyaları Temizle"]),
            ("DNS Önbelleğini Temizle (ipconfig /flushdns)", TASKS["DNS Önbelleğini Temizle (ipconfig /flushdns)"]),
        ]
        
        if not is_admin():
            if messagebox.askyesno("Yönetici İzni Gerekli", "Hızlı bakım işlemleri yönetici yetkisi gerektiriyor.\n\nUygulamayı yönetici olarak yeniden başlatmak ister misin?"):
                self.restart_as_admin()
            return
            
        if not messagebox.askyesno("Onay", "Hızlı bakım işlemlerini başlatmak istediğine emin misin?"):
            return

        self.output_text.delete("1.0", END)
        self.append_output("Hızlı bakım başlatıldı...")
        self.set_controls(False)
        thread = threading.Thread(target=self._run_batch_worker, args=(quick_tasks,), daemon=True)
        thread.start()

    def _run_batch_worker(self, tasks: list) -> None:
        self.cancel_requested = False
        total_tasks = len(tasks)
        
        for index, (task_name, task) in enumerate(tasks, start=1):
            if self.cancel_requested:
                self.task_queue.put({"action": "append_output", "message": "⚠️ İşlemler kullanıcı tarafından iptal edildi!"})
                break
                
            progress_val = ((index - 1) / total_tasks) * 100
            self.task_queue.put({"action": "update_progress", "value": progress_val})
            self.task_queue.put({"action": "append_output", "message": f"[{index}/{total_tasks}] Çalışıyor: {task_name}"})
            
            self._execute_task(task_name, task)
            
        self.task_queue.put({"action": "update_progress", "value": 100})
        self.task_queue.put({"action": "finish_batch"})

    def _execute_task(self, task_name: str, task: dict) -> None:
        try:
            if task["type"] == "python":
                details, error_count = cleanup_temp_directories()
                status = "OK" if error_count == 0 else "Uyarı"
                self.task_queue.put({"action": "append_output", "message": details})
                self.task_queue.put({"action": "add_log", "task_name": task_name, "status": status, "details": details})
            else:
                command = task["command"]
                cmd_str = " ".join(command) if isinstance(command, list) else command
                self.task_queue.put({"action": "append_output", "message": f"Komut: {cmd_str}"})
                
                self.current_process = subprocess.Popen(
                    command, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding='cp1254', errors='replace'
                )
                
                stdout, stderr = self.current_process.communicate(timeout=300)
                
                if self.cancel_requested:
                    self.task_queue.put({"action": "append_output", "message": "Görev iptal edildi."})
                    self.task_queue.put({"action": "add_log", "task_name": task_name, "status": "Uyarı", "details": "Kullanıcı işlemi iptal etti."})
                    return

                output = stdout if stdout else "(çıktı yok)"
                if stderr:
                    output += f"\nHata çıktısı: {stderr}"

                status = "OK" if self.current_process.returncode == 0 else "Hata"
                details = f"Çıkış kodu: {self.current_process.returncode}"

                self.task_queue.put({"action": "append_output", "message": output})
                self.task_queue.put({"action": "append_output", "message": details})
                log_details = f"{details}\n\n--- ÇIKTI ---\n{output[:3000]}"
                self.task_queue.put({"action": "add_log", "task_name": task_name, "status": status, "details": log_details})

        except subprocess.TimeoutExpired:
            if self.current_process:
                self.current_process.kill()
            error_msg = f"Hata: Görev zaman aşımına uğradı (5 dakika)."
            self.task_queue.put({"action": "append_output", "message": error_msg})
            self.task_queue.put({"action": "add_log", "task_name": task_name, "status": "Hata", "details": error_msg})
        except Exception as ex:
            if self.cancel_requested:
                error_msg = "Görev zorla kapatıldı."
                status = "Uyarı"
            else:
                error_msg = f"Beklenmeyen hata: {ex}"
                status = "Hata"
                
            self.task_queue.put({"action": "append_output", "message": error_msg})
            self.task_queue.put({"action": "add_log", "task_name": task_name, "status": status, "details": error_msg})
        finally:
            self.current_process = None

    def clear_logs_with_confirm(self) -> None:
        self.clear_logs()
        self.refresh_logs()
        self.append_output("Log geçmişi temizlendi.")

    def export_logs_to_csv(self) -> None:
        save_path = filedialog.asksaveasfilename(title="Logları CSV Olarak Kaydet", defaultextension=".csv", filetypes=[("CSV dosyası", "*.csv")])
        if not save_path: return
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT timestamp, task_name, status, details FROM logs ORDER BY id DESC")
            rows = cur.fetchall()
            with open(save_path, "w", newline="", encoding="utf-8-sig") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["timestamp", "task_name", "status", "details"])
                writer.writerows(rows)
            self.append_output(f"CSV dışa aktarma tamamlandı: {save_path}")
        except Exception as ex:
            self.append_output(f"Dışa aktarma hatası: {ex}")

    def open_about_dialog(self) -> None:
        about = tk.Toplevel(self)
        about.title("OYAX - Hakkında")
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
        about.configure(bg="#0f172a")
        about.transient(self)
        about.grab_set()

        container = ttk.Frame(about, style="Card.TFrame", padding=24)
        container.pack(fill=BOTH, expand=True, padx=16, pady=16)

        ttk.Label(container, text="OYAX - Windows Bakım Aracı", style="HeaderTitle.TLabel").pack(anchor="w")
        ttk.Label(container, text=f"Sürüm: {APP_VERSION}", style="HeaderSub.TLabel").pack(anchor="w", pady=(4, 0))
        eula_label = ttk.Label(container, text="EULA Kullanım Koşulları", style="EULALink.TLabel")
        eula_label.pack(anchor="w", pady=(4, 0))
        eula_label.bind("<Button-1>", self.open_eula)
        ttk.Label(container, text=f"Geliştirici: {AUTHOR_NAME}", style="HeaderSub.TLabel").pack(anchor="w", pady=(0, 16))

        ttk.Label(container, text="Bu araç Windows bakım komutlarını tek panelde sunar.\nGitHub reposundan güncel versiyonları kontrol etmeyi unutmayın.", style="Muted.TLabel").pack(anchor="w")

        status_var = tk.StringVar(value="Durum: Kontrol Edilmedi")
        latest_var = tk.StringVar(value="GitHub Repo: Kontrol Edilmedi")
        ttk.Label(container, textvariable=latest_var, style="HeaderSub.TLabel").pack(anchor="w", pady=(16, 4))
        ttk.Label(container, textvariable=status_var, style="HeaderSub.TLabel").pack(anchor="w", pady=(0, 12))

        button_row = ttk.Frame(container, style="Card.TFrame")
        button_row.pack(fill=X, pady=(8, 0))
        ttk.Button(button_row, text="GitHub Güncelleme Kontrolü", style="Primary.TButton", command=lambda: self.start_update_check(status_var, latest_var)).pack(side=LEFT)
        ttk.Button(button_row, text="Kapat", style="Secondary.TButton", command=about.destroy).pack(side=RIGHT)

    def open_eula(self, event):
        webbrowser.open_new("https://github.com/furkanyasarr0/OYAX/blob/main/EULA.md")

    def start_update_check(self, status_var: tk.StringVar, repo_var: tk.StringVar) -> None:
        status_var.set("Durum: Kontrol başladı...")
        thread = threading.Thread(target=self._update_check_worker, args=(status_var, repo_var), daemon=True)
        thread.start()

    def _update_check_worker(self, status_var: tk.StringVar, repo_var: tk.StringVar) -> None:
        repo_name = "furkanyasarr0/OYAX"
        self.after(0, lambda: repo_var.set(f"GitHub Repo: {repo_name}"))
        url = f"https://api.github.com/repos/{repo_name}/releases/latest"
        try:
            request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "OyaxUpdater"})
            with urllib.request.urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
            latest_tag = str(payload.get("tag_name", "")).strip()
            if not latest_tag:
                self.after(0, lambda: status_var.set("Durum: Release etiketi bulunamadı."))
                return

            latest_version = self.normalize_version(latest_tag)
            current_version = self.normalize_version(APP_VERSION)
            if self.compare_versions(latest_version, current_version) > 0:
                self.after(0, lambda: status_var.set(f"Durum: Yeni sürüm var ({latest_tag}) - mevcut: {APP_VERSION}"))
            else:
                self.after(0, lambda: status_var.set(f"Durum: En Son Sürümü Kullanıyorsunuz! ({APP_VERSION})"))
        except Exception as ex:
            self.after(0, lambda: status_var.set(f"Durum: Güncelleme kontrol hatası: {ex}"))

    def normalize_version(self, raw_version: str) -> str:
        return raw_version.strip().lower().lstrip("v")

    def compare_versions(self, left: str, right: str) -> int:
        def parts(version: str) -> list:
            nums = []
            for item in version.split("."):
                try: nums.append(int(item))
                except ValueError: nums.append(0)
            while len(nums) < 3: nums.append(0)
            return nums[:3]

        left_parts = parts(left)
        right_parts = parts(right)
        if left_parts > right_parts: return 1
        if left_parts < right_parts: return -1
        return 0

    def refresh_logs(self) -> None:
        if not hasattr(self, 'log_tree'):
            try: self.after(50, self.refresh_logs)
            except Exception: pass
            return

        for row in self.log_tree.get_children():
            self.log_tree.delete(row)

        date_filter = self.date_filter_var.get().strip()
        status_filter = self.status_filter_var.get().strip()
        search_text = self.search_var.get().strip().lower()

        conditions = []
        params = []

        if date_filter and date_filter != "Tümü":
            now = datetime.now()
            if date_filter == "Bugün":
                cutoff_date = now.strftime("%Y-%m-%d 00:00:00")
                conditions.append("timestamp >= ?")
                params.append(cutoff_date)
            elif date_filter == "Son 7 Gün":
                cutoff_date = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
                conditions.append("timestamp >= ?")
                params.append(cutoff_date)
            elif date_filter == "Son 30 Gün":
                cutoff_date = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
                conditions.append("timestamp >= ?")
                params.append(cutoff_date)

        if status_filter and status_filter != "Tümü":
            conditions.append("status = ?")
            params.append(status_filter)

        if search_text:
            conditions.append("(LOWER(task_name) LIKE ? OR LOWER(details) LIKE ?)")
            term = f"%{search_text}%"
            params.extend([term, term])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        try:
            cur = self.conn.cursor()
            cur.execute(f"SELECT timestamp, task_name, status, details FROM logs {where_clause} ORDER BY id DESC LIMIT 200", params)
            rows = cur.fetchall()
            cur.execute(f"SELECT status, COUNT(*) FROM logs {where_clause} GROUP BY status", params)
            status_counts = dict(cur.fetchall())
        except Exception:
            rows = []
            status_counts = {}

        self.log_tree.tag_configure("evenrow", background="#020617")
        self.log_tree.tag_configure("oddrow", background="#0f172a")

        for index, row in enumerate(rows):
            row_tag = "evenrow" if index % 2 == 0 else "oddrow"
            self.log_tree.insert("", END, values=row, tags=(row_tag,))
            
        self.history_ok_var.set(f"OK: {status_counts.get('OK', 0)}")
        self.history_warn_var.set(f"Uyarı: {status_counts.get('Uyarı', 0)}")
        self.history_err_var.set(f"Hata: {status_counts.get('Hata', 0)}")
        self.history_meta_var.set(f"Gösterilen kayıt: {len(rows)}")

    def show_log_details_dialog(self, event) -> None:
        selected_items = self.log_tree.selection()
        if not selected_items: return
        
        item = selected_items[0]
        values = self.log_tree.item(item, "values")
        if not values or len(values) < 4: return
        timestamp, task, status, details = values

        dialog = tk.Toplevel(self)
        dialog.title("OYAX - Log Detayları")
        dialog.geometry("760x560")
        dialog.configure(bg="#0f172a")
        dialog.transient(self) 
        dialog.grab_set() 

        container = ttk.Frame(dialog, style="Card.TFrame", padding=24)
        container.pack(fill=BOTH, expand=True, padx=16, pady=16)

        ttk.Label(container, text=task, style="HeaderTitle.TLabel").pack(anchor="w")
        info_text = f"Zaman: {timestamp}   |   Durum: {status}"
        ttk.Label(container, text=info_text, style="HeaderSub.TLabel").pack(anchor="w", pady=(4, 16))

        text_area = tk.Text(container, wrap="word", bg="#020617", fg="#f8fafc", relief="flat", padx=16, pady=16, font=("Consolas", 10))
        formatted_details = str(details).replace("\\n", "\n")
        text_area.insert("1.0", formatted_details)
        text_area.configure(state="disabled") 
        text_area.pack(fill=BOTH, expand=True, pady=(0, 16))

        action_row = ttk.Frame(container, style="Card.TFrame")
        action_row.pack(fill=X)

        def copy_to_clipboard():
            dialog.clipboard_clear()
            full_text = f"Görev: {task}\nZaman: {timestamp}\nDurum: {status}\n\n{formatted_details}"
            dialog.clipboard_append(full_text)

        def export_to_txt():
            safe_time = str(timestamp).replace(":", "-").replace(" ", "_")
            save_path = filedialog.asksaveasfilename(parent=dialog, title="Log Detayını TXT Olarak Kaydet", defaultextension=".txt", initialfile=f"oyax_log_{safe_time}.txt", filetypes=[("Text dosyası", "*.txt")])
            if save_path:
                try:
                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write(f"Görev: {task}\nZaman: {timestamp}\nDurum: {status}\n\nDetaylar:\n{formatted_details}")
                except Exception: pass

        ttk.Button(action_row, text="Panoya Kopyala", style="Secondary.TButton", command=copy_to_clipboard).pack(side=LEFT)
        ttk.Button(action_row, text="Dışa Aktar (TXT)", style="Secondary.TButton", command=export_to_txt).pack(side=LEFT, padx=(8, 0))
        ttk.Button(action_row, text="Kapat", style="Primary.TButton", command=dialog.destroy).pack(side=RIGHT)

if __name__ == "__main__":
    app = MaintenanceApp()
    app.mainloop()
