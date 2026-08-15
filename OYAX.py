import os
import sys
import re
import time
import subprocess
import threading
import json
import webbrowser
import urllib.request
import zipfile
import shutil
import queue
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core.config import DB_FILE, APP_VERSION, AUTHOR_NAME, TASK_CATEGORIES, TASKS, CATEGORY_ICONS
from core.utils import apply_dpi_scaling, is_admin, cleanup_temp_directories, resource_path
from core.database import DatabaseManager

apply_dpi_scaling()

# Modern Theme Setup
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Theme Colors Palette
PALETTE = {
    "bg_dark": "#0b0f19",
    "sidebar_bg": "#0f172a",
    "card_bg": "#1e293b",
    "card_selected": "#172554",
    "card_hover": "#26354a",
    "card_border": "#334155",
    "card_border_sel": "#3b82f6",
    "inner_bg": "#090d16",
    "accent": "#3b82f6",
    "accent_hover": "#2563eb",
    "success": "#10b981",
    "success_bg": "#064e3b",
    "warning": "#f59e0b",
    "warning_bg": "#78350f",
    "danger": "#ef4444",
    "danger_hover": "#dc2626",
    "text_main": "#f8fafc",
    "text_muted": "#94a3b8",
    "text_dim": "#64748b",
}

# Typography with robust emoji support fallback
FONT_FAMILY = "Segoe UI"
EMOJI_FONT_FAMILY = "Segoe UI Emoji"


def decode_subprocess_output(raw_bytes: bytes) -> str:
    """Intelligently decodes subprocess bytes handling Turkish Windows encodings (UTF-8, CP857, CP1254)."""
    if not raw_bytes:
        return ""
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        pass

    for enc in ["cp857", "cp1254", "iso-8859-9", "latin-1"]:
        try:
            return raw_bytes.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def parse_version_tuple(v_str: str) -> tuple:
    """Parses version strings like 'v1.4', '1.4.2' into integer comparison tuples."""
    parts = re.findall(r'\d+', str(v_str))
    return tuple(int(p) for p in parts) if parts else (0,)


def is_newer_version(remote_ver: str, local_ver: str) -> bool:
    """Returns True if remote_ver is strictly greater than local_ver."""
    return parse_version_tuple(remote_ver) > parse_version_tuple(local_ver)


class OyaxApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        
        self.title("OYAX - Modern Windows Bakım ve Ağ Aracı")
        self.geometry("1240x800")
        self.minsize(1040, 660)
        
        try:
            icon_path = resource_path("icon.ico")
            self.iconbitmap(icon_path)
        except Exception:
            pass

        self.configure(fg_color=PALETTE["bg_dark"])
        
        # State variables
        self.current_tab = "tasks"
        self.cancel_requested = False
        self.current_process = None
        self.task_queue = queue.Queue()
        self.db = DatabaseManager(DB_FILE)
        
        self.selected_task_names = set()
        self.current_category = "Tümü"
        self.search_query = ""
        self._search_debounce_job = None
        
        # High-performance Widget Registry (Zero-flicker cached rendering)
        self.task_card_map = {}
        
        self._build_ui()
        self.center_window(1240, 800)
        
        self.process_queue()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.after(100, self.refresh_logs)
        
        # Background Auto-Update Check on App Launch
        self.after(1200, self._auto_check_update_on_startup)

    def center_window(self, width: int, height: int) -> None:
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = max(0, (screen_width // 2) - (width // 2))
        y = max(0, (screen_height // 2) - (height // 2))
        self.geometry(f"{width}x{height}+{x}+{y}")

    def on_closing(self) -> None:
        self.cancel_requested = True
        if self.current_process:
            try:
                self.current_process.kill()
            except Exception:
                pass
        try:
            self.db.close()
        except Exception:
            pass
        self.destroy()

    def process_queue(self) -> None:
        try:
            while True:
                msg = self.task_queue.get_nowait()
                action = msg.get("action")
                
                if action == "append_output":
                    self.append_output(msg["message"])
                elif action == "append_diag":
                    self.diag_text.insert("end", msg["message"] + "\n")
                    self.diag_text.see("end")
                elif action == "add_log":
                    try:
                        self.db.add_log(msg["task_name"], msg["status"], msg["details"])
                    except Exception as ex:
                        self.append_output(f"SİSTEM HATASI (Log Kaydedilemedi): {ex}")
                elif action == "update_progress":
                    self.set_progress(msg["value"])
                elif action == "set_status":
                    self.status_label.configure(text=f"Durum: {msg['text']}")
                elif action == "finish_batch":
                    self.append_output("\n✨ İşlemler tamamlandı.")
                    self.set_controls(True)
                    self.refresh_logs()
                    self.show_toast("✅ Tüm işlemler başarıyla tamamlandı")
                    
                self.task_queue.task_done()
        except queue.Empty:
            pass
        finally:
            self.after(50, self.process_queue)

    def set_progress(self, val: float) -> None:
        normalized = max(0.0, min(1.0, val / 100.0))
        self.progress_bar.set(normalized)

    def show_toast(self, text: str, duration_ms: int = 3000) -> None:
        """Sleek animated toast notification pill"""
        try:
            if hasattr(self, "toast_label"):
                self.toast_label.configure(text=text)
                self.toast_frame.grid(row=0, column=0, sticky="n", pady=10)
                if hasattr(self, "_toast_timer") and self._toast_timer:
                    self.after_cancel(self._toast_timer)
                self._toast_timer = self.after(duration_ms, lambda: self.toast_frame.grid_forget())
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # UI INITIALIZATION
    # ══════════════════════════════════════════════════════════════════════════
    def _build_ui(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._build_sidebar()
        self._build_main_container()

    # ────────────────────────────────── SIDEBAR ──────────────────────────────────
    def _build_sidebar(self) -> None:
        self.sidebar = ctk.CTkFrame(
            self,
            width=230,
            corner_radius=0,
            fg_color=PALETTE["sidebar_bg"],
            border_width=0
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)

        # Brand Title
        brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_frame.grid(row=0, column=0, padx=16, pady=(20, 16), sticky="ew")

        logo_title = ctk.CTkLabel(
            brand_frame,
            text="⚡ OYAX",
            font=ctk.CTkFont(family=FONT_FAMILY, size=22, weight="bold"),
            text_color=PALETTE["text_main"]
        )
        logo_title.pack(side="left")

        ver_badge = ctk.CTkLabel(
            brand_frame,
            text=f"v{APP_VERSION}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            fg_color=PALETTE["accent"],
            text_color="#ffffff",
            corner_radius=6,
            padx=6,
            pady=2
        )
        ver_badge.pack(side="right", pady=4)

        subtitle = ctk.CTkLabel(
            self.sidebar,
            text="Windows Sistem & Ağ Bakımı",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=PALETTE["text_muted"]
        )
        subtitle.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="w")

        # Navigation Buttons
        self.nav_buttons = {}
        nav_items = [
            ("tasks", "🛠️  Bakım & Görevler"),
            ("diag", "🔍  Gelişmiş Ağ Tanı"),
            ("logs", "📜  İşlem Günlüğü"),
            ("about", "⚙️  Ayarlar & Hakkında"),
        ]

        for idx, (tab_id, label) in enumerate(nav_items, start=2):
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                anchor="w",
                font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold" if tab_id == "tasks" else "normal"),
                fg_color=PALETTE["accent"] if tab_id == "tasks" else "transparent",
                text_color=PALETTE["text_main"] if tab_id == "tasks" else PALETTE["text_muted"],
                hover_color=PALETTE["card_hover"],
                corner_radius=8,
                height=40,
                command=lambda t=tab_id: self.switch_tab(t)
            )
            btn.grid(row=idx, column=0, padx=12, pady=4, sticky="ew")
            self.nav_buttons[tab_id] = btn

        # Sidebar Bottom Section: Status & Quick Actions
        bottom_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_frame.grid(row=7, column=0, padx=12, pady=16, sticky="ew")

        # Admin Badge
        admin_active = is_admin()
        admin_badge = ctk.CTkLabel(
            bottom_frame,
            text="🛡️ Yönetici: Aktif" if admin_active else "⚠️ Standart Kullanıcı",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=PALETTE["success_bg"] if admin_active else PALETTE["warning_bg"],
            text_color=PALETTE["success"] if admin_active else PALETTE["warning"],
            corner_radius=8,
            height=28
        )
        admin_badge.pack(fill="x", pady=(0, 10))

        # Quick Action Buttons
        self.quick_maint_btn = ctk.CTkButton(
            bottom_frame,
            text="⚡ Hızlı Bakım",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=PALETTE["card_bg"],
            hover_color=PALETTE["card_hover"],
            text_color=PALETTE["text_main"],
            height=34,
            corner_radius=6,
            command=self.run_quick_maintenance
        )
        self.quick_maint_btn.pack(fill="x", pady=2)

        self.winget_btn = ctk.CTkButton(
            bottom_frame,
            text="📦 Winget Güncelle",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=PALETTE["card_bg"],
            hover_color=PALETTE["card_hover"],
            text_color=PALETTE["text_main"],
            height=34,
            corner_radius=6,
            command=self.run_winget_upgrade_all
        )
        self.winget_btn.pack(fill="x", pady=2)

        if not admin_active:
            elevate_btn = ctk.CTkButton(
                bottom_frame,
                text="🔑 Yönetici Olarak Başlat",
                font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
                fg_color=PALETTE["warning_bg"],
                text_color=PALETTE["warning"],
                hover_color="#92400e",
                height=34,
                corner_radius=6,
                command=self.restart_as_admin
            )
            elevate_btn.pack(fill="x", pady=(6, 0))

    # ────────────────────────────────── MAIN CONTAINER ───────────────────────────
    def _build_main_container(self) -> None:
        self.main_container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        # Tab Views
        self.views = {
            "tasks": self._create_tasks_view(),
            "diag": self._create_diagnostics_view(),
            "logs": self._create_logs_view(),
            "about": self._create_about_view(),
        }

        # Floating Toast notification overlay
        self.toast_frame = ctk.CTkFrame(self.main_container, fg_color=PALETTE["sidebar_bg"], corner_radius=20, border_width=1, border_color=PALETTE["accent"])
        self.toast_label = ctk.CTkLabel(self.toast_frame, text="", font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"), text_color=PALETTE["text_main"], padx=14, pady=6)
        self.toast_label.pack()

        self.switch_tab("tasks")

    def switch_tab(self, tab_id: str) -> None:
        self.current_tab = tab_id
        for tid, btn in self.nav_buttons.items():
            is_active = (tid == tab_id)
            btn.configure(
                fg_color=PALETTE["accent"] if is_active else "transparent",
                text_color=PALETTE["text_main"] if is_active else PALETTE["text_muted"],
                font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold" if is_active else "normal")
            )
            
        for tid, frame in self.views.items():
            if tid == tab_id:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_forget()

    # ══════════════════════════════════════════════════════════════════════════
    # VIEW 1: BAKIM & GÖREVLER (3-Column Layout: Clean Categories | Tasks | Terminal)
    # ══════════════════════════════════════════════════════════════════════════
    def _create_tasks_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.main_container, fg_color="transparent")
        view.grid_rowconfigure(0, weight=1)
        
        # Strictly uniform 3-column split: Categories (22%) | Tasks List (45%) | Console & Deck (33%)
        view.grid_columnconfigure(0, weight=22, uniform="task_hub_cols") # Col 0: Dedicated Categories Panel
        view.grid_columnconfigure(1, weight=45, uniform="task_hub_cols") # Col 1: Tasks Cards List
        view.grid_columnconfigure(2, weight=33, uniform="task_hub_cols") # Col 2: Live Console & Deck

        # ────────────────────── COL 0: DEDICATED VERTICAL CATEGORIES PANEL (NO SCROLLBAR) ──────────────────────
        cat_panel = ctk.CTkFrame(
            view,
            fg_color=PALETTE["card_bg"],
            corner_radius=10,
            border_width=1,
            border_color=PALETTE["card_border"]
        )
        cat_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        cat_panel.grid_rowconfigure(1, weight=1)
        cat_panel.grid_columnconfigure(0, weight=1)

        # Categories Header
        cat_hdr = ctk.CTkFrame(cat_panel, fg_color="transparent", height=40)
        cat_hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

        ctk.CTkLabel(
            cat_hdr,
            text="🗂️ Kategoriler",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=PALETTE["text_main"]
        ).pack(side="left")

        # Clean vertical category button container (No ugly scrollbar!)
        cat_list_container = ctk.CTkFrame(
            cat_panel,
            fg_color="transparent"
        )
        cat_list_container.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 8))

        self.category_buttons = {}
        all_categories = ["Tümü"] + list(TASK_CATEGORIES.keys())
        
        for cat in all_categories:
            icon = CATEGORY_ICONS.get(cat, "📋")
            cnt = len(TASKS) if cat == "Tümü" else len(TASK_CATEGORIES.get(cat, []))
            is_active = (cat == "Tümü")
            
            # Category tile button with emoji support
            btn_text = f" {icon}  {cat}"
            btn = ctk.CTkButton(
                cat_list_container,
                text=btn_text,
                anchor="w",
                font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold" if is_active else "normal"),
                fg_color=PALETTE["accent"] if is_active else PALETTE["inner_bg"],
                text_color=PALETTE["text_main"] if is_active else PALETTE["text_muted"],
                hover_color=PALETTE["card_hover"],
                height=36,
                corner_radius=6,
                command=lambda c=cat: self.select_category(c)
            )
            btn.pack(fill="x", pady=2)
            self.category_buttons[cat] = btn

        # ────────────────────── COL 1: TASK CARDS & SEARCH ──────────────────────
        tasks_panel = ctk.CTkFrame(view, fg_color="transparent")
        tasks_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        tasks_panel.grid_rowconfigure(2, weight=1)
        tasks_panel.grid_columnconfigure(0, weight=1)

        # Top Search & Action Bar
        search_card = ctk.CTkFrame(tasks_panel, fg_color=PALETTE["card_bg"], corner_radius=10, border_width=1, border_color=PALETTE["card_border"], height=48)
        search_card.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        search_card.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            search_card,
            placeholder_text="🔍 Görev veya komut ara...",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            height=34,
            fg_color=PALETTE["inner_bg"],
            border_color=PALETTE["card_border"],
            corner_radius=6
        )
        self.search_entry.grid(row=0, column=0, padx=8, pady=7, sticky="ew")
        self.search_entry.bind("<KeyRelease>", self._on_search_change_debounced)

        act_box = ctk.CTkFrame(search_card, fg_color="transparent")
        act_box.grid(row=0, column=1, padx=(0, 8), pady=7, sticky="e")

        ctk.CTkButton(
            act_box,
            text="Tümünü Seç",
            width=80,
            height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=PALETTE["inner_bg"],
            hover_color=PALETTE["card_hover"],
            corner_radius=6,
            command=self.select_visible_tasks
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            act_box,
            text="Temizle",
            width=65,
            height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=PALETTE["inner_bg"],
            hover_color=PALETTE["card_hover"],
            corner_radius=6,
            command=self.clear_all_tasks
        ).pack(side="left", padx=2)

        # Middle Header Info
        list_header = ctk.CTkFrame(tasks_panel, fg_color="transparent", height=24)
        list_header.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        self.list_info_label = ctk.CTkLabel(
            list_header,
            text=f"📋 Tümü ({len(TASKS)} Görev)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=PALETTE["text_main"]
        )
        self.list_info_label.pack(side="left")

        self.sel_count_badge = ctk.CTkLabel(
            list_header,
            text="0 Seçili",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=PALETTE["card_bg"],
            text_color=PALETTE["accent"],
            corner_radius=6,
            padx=8,
            pady=2
        )
        self.sel_count_badge.pack(side="right")

        # Scrollable Task Cards Frame
        self.task_scroll = ctk.CTkScrollableFrame(
            tasks_panel,
            fg_color=PALETTE["card_bg"],
            corner_radius=10,
            border_width=1,
            border_color=PALETTE["card_border"]
        )
        self.task_scroll.grid(row=2, column=0, sticky="nsew")

        # ────────────────────── COL 2: LIVE CONSOLE & CONTROL DECK ──────────────────────
        deck_panel = ctk.CTkFrame(view, fg_color="transparent")
        deck_panel.grid(row=0, column=2, sticky="nsew")
        deck_panel.grid_rowconfigure(2, weight=1)
        deck_panel.grid_columnconfigure(0, weight=1)

        # Execution Control Card
        ctrl_card = ctk.CTkFrame(deck_panel, fg_color=PALETTE["card_bg"], corner_radius=10, border_width=1, border_color=PALETTE["card_border"])
        ctrl_card.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ctrl_inner = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        ctrl_inner.pack(fill="x", padx=12, pady=10)

        # Status & Progress
        self.status_label = ctk.CTkLabel(
            ctrl_inner,
            text="Durum: Bekleniyor...",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=PALETTE["text_muted"],
            anchor="w",
            wraplength=340
        )
        self.status_label.pack(fill="x", pady=(0, 6))

        self.progress_bar = ctk.CTkProgressBar(
            ctrl_inner,
            height=10,
            corner_radius=5,
            progress_color=PALETTE["accent"],
            fg_color=PALETTE["inner_bg"]
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=(0, 10))

        # Big Run & Cancel Buttons
        btn_row = ctk.CTkFrame(ctrl_inner, fg_color="transparent")
        btn_row.pack(fill="x")

        self.run_btn = ctk.CTkButton(
            btn_row,
            text="▶️  Çalıştır",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            fg_color=PALETTE["accent"],
            hover_color=PALETTE["accent_hover"],
            height=38,
            corner_radius=8,
            command=self.run_selected_tasks
        )
        self.run_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.cancel_btn = ctk.CTkButton(
            btn_row,
            text="⏹️ İptal",
            width=70,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=PALETTE["danger"],
            hover_color=PALETTE["danger_hover"],
            height=38,
            corner_radius=8,
            state="disabled",
            command=self.request_cancel
        )
        self.cancel_btn.pack(side="right")

        # Terminal Output Box Header
        term_header = ctk.CTkFrame(deck_panel, fg_color="transparent")
        term_header.grid(row=1, column=0, sticky="ew", pady=(4, 4))

        ctk.CTkLabel(
            term_header,
            text="💻 Canlı Konsol Çıktısı",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=PALETTE["text_main"]
        ).pack(side="left")

        term_actions = ctk.CTkFrame(term_header, fg_color="transparent")
        term_actions.pack(side="right")

        ctk.CTkButton(
            term_actions,
            text="📋 Kopyala",
            width=65,
            height=24,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            fg_color=PALETTE["card_bg"],
            hover_color=PALETTE["card_hover"],
            command=self.copy_output_to_clipboard
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            term_actions,
            text="🧹 Temizle",
            width=60,
            height=24,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            fg_color=PALETTE["card_bg"],
            hover_color=PALETTE["card_hover"],
            command=lambda: self.output_box.delete("1.0", "end")
        ).pack(side="left", padx=2)

        self.output_box = ctk.CTkTextbox(
            deck_panel,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=PALETTE["inner_bg"],
            text_color="#e2e8f0",
            corner_radius=10,
            border_width=1,
            border_color=PALETTE["card_border"],
            wrap="char"
        )
        self.output_box.grid(row=2, column=0, sticky="nsew")

        # Build card widgets once on startup
        self._init_task_cards()
        self._apply_task_filters()
        return view

    # ────────────────────────────────── HIGH-PERFORMANCE ZERO-FLICKER RENDERING ───────────────────────────
    def _init_task_cards(self) -> None:
        """Instantiate all task cards once to prevent recreating widgets on filter/toggle."""
        for task_name, task in TASKS.items():
            req_admin = task.get("requires_admin", False)
            desc = task.get("description", "")

            card = ctk.CTkFrame(
                self.task_scroll,
                fg_color=PALETTE["card_bg"],
                corner_radius=8,
                border_width=1,
                border_color=PALETTE["card_border"],
                cursor="hand2"
            )

            header_frame = ctk.CTkFrame(card, fg_color="transparent")
            header_frame.pack(fill="x", padx=10, pady=(8, 2))

            chk_var = ctk.BooleanVar(value=False)
            chk = ctk.CTkCheckBox(
                header_frame,
                text=task_name,
                variable=chk_var,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                text_color="#cbd5e1",
                fg_color=PALETTE["accent"],
                hover_color=PALETTE["accent_hover"],
                border_color=PALETTE["card_border"],
                corner_radius=5,
                command=lambda t=task_name: self.on_task_toggle(t)
            )
            chk.pack(side="left", fill="x", expand=True)

            if req_admin:
                admin_pill = ctk.CTkLabel(
                    header_frame,
                    text="🔑 Admin",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=9, weight="bold"),
                    fg_color=PALETTE["warning_bg"],
                    text_color=PALETTE["warning"],
                    corner_radius=4,
                    padx=5,
                    pady=1
                )
                admin_pill.pack(side="right")

            desc_lbl = None
            if desc:
                desc_lbl = ctk.CTkLabel(
                    card,
                    text=desc,
                    font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                    text_color=PALETTE["text_muted"],
                    anchor="w",
                    justify="left"
                )
                desc_lbl.pack(fill="x", padx=32, pady=(0, 8))
                desc_lbl.bind("<Button-1>", lambda e, t=task_name: self.on_task_toggle(t))

            card.bind("<Button-1>", lambda e, t=task_name: self.on_task_toggle(t))

            self.task_card_map[task_name] = {
                "card": card,
                "chk": chk,
                "var": chk_var,
                "desc": desc_lbl,
                "is_packed": False
            }

    def _on_search_change_debounced(self, event=None) -> None:
        if self._search_debounce_job:
            self.after_cancel(self._search_debounce_job)
        self._search_debounce_job = self.after(80, self._apply_task_filters)

    def select_category(self, cat_name: str) -> None:
        self.current_category = cat_name
        for name, btn in self.category_buttons.items():
            is_act = (name == cat_name)
            btn.configure(
                fg_color=PALETTE["accent"] if is_act else PALETTE["inner_bg"],
                text_color=PALETTE["text_main"] if is_act else PALETTE["text_muted"],
                font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold" if is_act else "normal")
            )
        self._apply_task_filters()

    def _apply_task_filters(self) -> None:
        self.search_query = self.search_entry.get().strip().lower() if hasattr(self, "search_entry") else ""
        visible_count = 0

        for task_name, task in TASKS.items():
            card_info = self.task_card_map.get(task_name)
            if not card_info: continue

            cat_match = (self.current_category == "Tümü" or task.get("category") == self.current_category)
            search_match = True
            if self.search_query:
                q = self.search_query
                search_match = (q in task_name.lower() or q in task.get("description", "").lower())

            should_show = (cat_match and search_match)

            if should_show:
                if not card_info["is_packed"]:
                    card_info["card"].pack(fill="x", pady=3, padx=2)
                    card_info["is_packed"] = True
                visible_count += 1
            else:
                if card_info["is_packed"]:
                    card_info["card"].pack_forget()
                    card_info["is_packed"] = False

        cat_icon = CATEGORY_ICONS.get(self.current_category, "📋")
        self.list_info_label.configure(text=f"{cat_icon} {self.current_category} ({visible_count} Görev)")
        self._update_selection_badges()

    def on_task_toggle(self, task_name: str) -> None:
        if task_name in self.selected_task_names:
            self.selected_task_names.remove(task_name)
        else:
            self.selected_task_names.add(task_name)
        
        self._update_task_card_visual(task_name)
        self._update_selection_badges()

    def _update_task_card_visual(self, task_name: str) -> None:
        card_info = self.task_card_map.get(task_name)
        if not card_info: return

        is_sel = (task_name in self.selected_task_names)
        card_info["var"].set(is_sel)
        card_info["card"].configure(
            fg_color=PALETTE["card_selected"] if is_sel else PALETTE["card_bg"],
            border_color=PALETTE["card_border_sel"] if is_sel else PALETTE["card_border"]
        )
        card_info["chk"].configure(
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold" if is_sel else "normal"),
            text_color=PALETTE["text_main"] if is_sel else "#cbd5e1"
        )
        if card_info["desc"]:
            card_info["desc"].configure(
                text_color=PALETTE["accent"] if is_sel else PALETTE["text_muted"]
            )

    def _update_selection_badges(self) -> None:
        count = len(self.selected_task_names)
        self.sel_count_badge.configure(
            text=f"{count} Seçili",
            fg_color=PALETTE["accent"] if count > 0 else PALETTE["card_bg"],
            text_color="#ffffff" if count > 0 else PALETTE["accent"]
        )

    def select_visible_tasks(self) -> None:
        for task_name, task in TASKS.items():
            card_info = self.task_card_map.get(task_name)
            if card_info and card_info["is_packed"]:
                self.selected_task_names.add(task_name)
                self._update_task_card_visual(task_name)
        self._update_selection_badges()
        self.show_toast(f"✅ {len(self.selected_task_names)} görev seçildi")

    def clear_all_tasks(self) -> None:
        for task_name in list(self.selected_task_names):
            self.selected_task_names.remove(task_name)
            self._update_task_card_visual(task_name)
        self._update_selection_badges()
        self.show_toast("🧹 Görev seçimleri temizlendi")

    def append_output(self, message: str) -> None:
        short_msg = message.split('\n')[0][:50]
        if len(message.split('\n')[0]) > 50:
            short_msg += "..."
        self.status_label.configure(text=f"Durum: {short_msg}")
        self.output_box.insert("end", message + "\n")
        self.output_box.see("end")

    def copy_output_to_clipboard(self) -> None:
        text = self.output_box.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(text)
        self.show_toast("📋 Konsol çıktısı kopyalandı")

    def set_controls(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        cancel_state = "disabled" if enabled else "normal"

        self.run_btn.configure(state=state)
        self.winget_btn.configure(state=state)
        self.quick_maint_btn.configure(state=state)
        self.cancel_btn.configure(state=cancel_state)
        if hasattr(self, "diag_start_btn"):
            self.diag_start_btn.configure(state=state)

        if enabled:
            self.progress_bar.set(0)
            self.status_label.configure(text="Durum: Bekleniyor...")

    def request_cancel(self) -> None:
        self.cancel_requested = True
        if self.current_process:
            try:
                self.current_process.kill()
            except Exception:
                pass
        self.append_output("⚠️ İptal isteği alındı. İşlemler durduruluyor...")

    # ══════════════════════════════════════════════════════════════════════════
    # TASK RUNNERS
    # ══════════════════════════════════════════════════════════════════════════
    def _get_selected_tasks(self) -> list:
        return [(task_name, TASKS[task_name]) for task_name in sorted(self.selected_task_names)]

    def run_selected_tasks(self) -> None:
        selected_tasks = self._get_selected_tasks()
        if not selected_tasks:
            messagebox.showwarning("Uyarı", "Lütfen çalıştırmak için en az bir görev seçin.")
            return

        if any(task.get("requires_admin") for _, task in selected_tasks) and not is_admin():
            if messagebox.askyesno("Yönetici İzni Gerekli", "Seçili görevlerden bazıları yönetici yetkisi gerektiriyor.\n\nUygulamayı yönetici olarak yeniden başlatmak ister misiniz?"):
                self.restart_as_admin()
            return

        if not messagebox.askyesno("Onay", f"Seçilen {len(selected_tasks)} görevi çalıştırmak istediğinize emin misiniz?"):
            return

        self.output_box.delete("1.0", "end")
        self.append_output(f"🚀 Toplu görev başlatıldı. Toplam görev: {len(selected_tasks)}")
        self.set_controls(False)
        thread = threading.Thread(target=self._run_batch_worker, args=(selected_tasks,), daemon=True)
        thread.start()

    def run_winget_upgrade_all(self) -> None:
        if not is_admin():
            if messagebox.askyesno("Yönetici İzni Gerekli", "Winget güncellemesi yönetici yetkisi gerektiriyor.\n\nUygulamayı yönetici olarak yeniden başlatmak ister misiniz?"):
                self.restart_as_admin()
            return

        if not messagebox.askyesno("Onay", "Winget ile tüm sistem paketlerini güncellemek istediğinize emin misiniz?"):
            return

        self.switch_tab("tasks")
        self.output_box.delete("1.0", "end")
        self.append_output("📦 Winget tüm paketler güncelleniyor...")
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
            if messagebox.askyesno("Yönetici İzni Gerekli", "Hızlı bakım işlemleri yönetici yetkisi gerektiriyor.\n\nUygulamayı yönetici olarak yeniden başlatmak ister misiniz?"):
                self.restart_as_admin()
            return

        if not messagebox.askyesno("Onay", "Hızlı bakım işlemlerini başlatmak istediğinize emin misiniz?"):
            return

        self.switch_tab("tasks")
        self.output_box.delete("1.0", "end")
        self.append_output("⚡ Hızlı bakım başlatıldı...")
        self.set_controls(False)
        thread = threading.Thread(target=self._run_batch_worker, args=(quick_tasks,), daemon=True)
        thread.start()

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
                messagebox.showerror("Hata", "Yönetici izni alınamadı veya işlem reddedildi.")
        except Exception as e:
            messagebox.showerror("Hata", f"Yeniden başlatma sırasında bir hata oluştu: {e}")

    def _run_batch_worker(self, tasks: list) -> None:
        self.cancel_requested = False
        total_tasks = len(tasks)
        
        for index, (task_name, task) in enumerate(tasks, start=1):
            if self.cancel_requested:
                self.task_queue.put({"action": "append_output", "message": "⚠️ İşlemler kullanıcı tarafından iptal edildi!"})
                break
                
            progress_val = ((index - 1) / total_tasks) * 100
            self.task_queue.put({"action": "update_progress", "value": progress_val})
            self.task_queue.put({"action": "append_output", "message": f"\n[{index}/{total_tasks}] ⚙️ Çalışıyor: {task_name}"})
            
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
                
                # Use raw bytes pipe and decode_subprocess_output to preserve Turkish characters
                self.current_process = subprocess.Popen(
                    command, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                
                stdout_bytes, stderr_bytes = self.current_process.communicate(timeout=300)
                stdout = decode_subprocess_output(stdout_bytes).strip()
                stderr = decode_subprocess_output(stderr_bytes).strip()
                
                if self.cancel_requested:
                    self.task_queue.put({"action": "append_output", "message": "Görev iptal edildi."})
                    self.task_queue.put({"action": "add_log", "task_name": task_name, "status": "Uyarı", "details": "Kullanıcı işlemi iptal etti."})
                    return

                output = stdout if stdout else "(çıktı yok)"
                if stderr:
                    output += f"\nHata çıktısı: {stderr}"

                status = "OK" if self.current_process.returncode == 0 else "Hata"
                self.task_queue.put({"action": "append_output", "message": output})
                self.task_queue.put({"action": "add_log", "task_name": task_name, "status": status, "details": output})
        except subprocess.TimeoutExpired:
            error_msg = "Komut zaman aşımına uğradı (5 dakika)."
            self.task_queue.put({"action": "append_output", "message": error_msg})
            self.task_queue.put({"action": "add_log", "task_name": task_name, "status": "Hata", "details": error_msg})
        except Exception as e:
            error_msg = f"Hata: {e}"
            status = "İptal Edildi" if self.cancel_requested else "Hata"
            self.task_queue.put({"action": "append_output", "message": error_msg})
            self.task_queue.put({"action": "add_log", "task_name": task_name, "status": status, "details": error_msg})
        finally:
            self.current_process = None

    # ══════════════════════════════════════════════════════════════════════════
    # VIEW 2: GELİŞMİŞ AĞ TANILAMA
    # ══════════════════════════════════════════════════════════════════════════
    def _create_diagnostics_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.main_container, fg_color="transparent")
        view.grid_rowconfigure(1, weight=1)
        view.grid_columnconfigure(0, weight=1)

        # Header Bar
        hdr = ctk.CTkFrame(view, fg_color=PALETTE["card_bg"], corner_radius=10, border_width=1, border_color=PALETTE["card_border"])
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        hdr_inner = ctk.CTkFrame(hdr, fg_color="transparent")
        hdr_inner.pack(fill="x", padx=16, pady=12)

        info_box = ctk.CTkFrame(hdr_inner, fg_color="transparent")
        info_box.pack(side="left")

        ctk.CTkLabel(
            info_box,
            text="🔍 Gelişmiş Ağ Tanılama & Sağlık Analizi",
            font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"),
            text_color=PALETTE["text_main"]
        ).pack(anchor="w")

        ctk.CTkLabel(
            info_box,
            text="12 farklı parametrede bağlantı, DNS, gecikme, ISP ve güvenlik kontrolleri yapar.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=PALETTE["text_muted"]
        ).pack(anchor="w")

        self.diag_start_btn = ctk.CTkButton(
            hdr_inner,
            text="🚀  Tanılamayı Başlat",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            fg_color=PALETTE["accent"],
            hover_color=PALETTE["accent_hover"],
            height=38,
            corner_radius=8,
            command=self.run_network_diagnostics
        )
        self.diag_start_btn.pack(side="right")

        # Split Body: Left Info Cards / Right Console Report (Uniform proportion locked)
        body = ctk.CTkFrame(view, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=38, uniform="diag_split_group") # Left Info Cards
        body.grid_columnconfigure(1, weight=62, uniform="diag_split_group") # Right Report Console

        # Left Info Cards Frame
        left_cards_scroll = ctk.CTkScrollableFrame(
            body,
            fg_color=PALETTE["card_bg"],
            corner_radius=10,
            border_width=1,
            border_color=PALETTE["card_border"]
        )
        left_cards_scroll.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        ctk.CTkLabel(
            left_cards_scroll,
            text="📡 Ağ Durum Kartları",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=PALETTE["text_main"]
        ).pack(anchor="w", padx=10, pady=(8, 12))

        self.diag_cards = {}
        card_specs = [
            ("adapter", "🔌 Aktif Ağ Adaptörü", "Henüz taranmadı"),
            ("local_ip", "💻 Yerel IP & Ağ Geçidi", "Henüz taranmadı"),
            ("public_ip", "🌐 Dış IP & Servis Sağlayıcı (ISP)", "Henüz taranmadı"),
            ("wifi", "📶 Wi-Fi Sinyal & Kanal", "Henüz taranmadı"),
            ("vpn", "🔐 VPN & Proxy Durumu", "Henüz taranmadı"),
        ]

        for key, title, def_val in card_specs:
            c = ctk.CTkFrame(left_cards_scroll, fg_color=PALETTE["inner_bg"], corner_radius=8, border_width=1, border_color=PALETTE["card_border"])
            c.pack(fill="x", padx=6, pady=4)

            ctk.CTkLabel(
                c,
                text=title,
                font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
                text_color=PALETTE["accent"]
            ).pack(anchor="w", padx=10, pady=(6, 2))

            val_lbl = ctk.CTkLabel(
                c,
                text=def_val,
                font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                text_color=PALETTE["text_muted"],
                anchor="w",
                justify="left"
            )
            val_lbl.pack(fill="x", padx=10, pady=(0, 6))
            self.diag_cards[key] = (c, val_lbl)

        # Right Console Report Frame
        right_report = ctk.CTkFrame(body, fg_color="transparent")
        right_report.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right_report.grid_rowconfigure(1, weight=1)
        right_report.grid_columnconfigure(0, weight=1)

        rep_hdr = ctk.CTkFrame(right_report, fg_color="transparent")
        rep_hdr.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        ctk.CTkLabel(
            rep_hdr,
            text="📑 Tanılama Raporu & Çözüm Önerileri",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=PALETTE["text_main"]
        ).pack(side="left")

        ctk.CTkButton(
            rep_hdr,
            text="📋 Raporu Kopyala",
            width=100,
            height=26,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            fg_color=PALETTE["card_bg"],
            hover_color=PALETTE["card_hover"],
            command=lambda: self._copy_diag_report()
        ).pack(side="right")

        self.diag_text = ctk.CTkTextbox(
            right_report,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=PALETTE["inner_bg"],
            text_color="#e2e8f0",
            corner_radius=10,
            border_width=1,
            border_color=PALETTE["card_border"],
            wrap="char"
        )
        self.diag_text.grid(row=1, column=0, sticky="nsew")

        return view

    def _copy_diag_report(self) -> None:
        text = self.diag_text.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(text)
        self.show_toast("📋 Ağ tanılama raporu kopyalandı")

    def run_network_diagnostics(self) -> None:
        self.diag_text.delete("1.0", "end")
        self.set_controls(False)
        thread = threading.Thread(target=self._network_diagnostics_worker, daemon=True)
        thread.start()

    def _network_diagnostics_worker(self) -> None:
        self.cancel_requested = False
        results = []
        recommendations = []
        net_info = {}
        total_tests = 12
        passed = 0
        warnings = 0
        failed = 0

        def _out(msg):
            self.task_queue.put({"action": "append_diag", "message": msg})

        def _progress(step):
            self.task_queue.put({"action": "update_progress", "value": (step / total_tests) * 100})

        def _run_cmd(cmd, timeout=15):
            try:
                proc = subprocess.Popen(
                    cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                stdout_bytes, stderr_bytes = proc.communicate(timeout=timeout)
                stdout = decode_subprocess_output(stdout_bytes).strip()
                stderr = decode_subprocess_output(stderr_bytes).strip()
                return proc.returncode, stdout, stderr
            except subprocess.TimeoutExpired:
                try: proc.kill()
                except Exception: pass
                return -1, "", "Zaman aşımı"
            except Exception as ex:
                return -1, "", str(ex)

        def _cancelled():
            return self.cancel_requested

        _out("═" * 58)
        _out("          🔍 OYAX - KAPSAMLI AĞ SAĞLIK VE TANILAMA RAPORU")
        _out("═" * 58)
        _out("")

        # ── Bilgi Paneli ──
        code, stdout, _ = _run_cmd(["powershell", "-Command",
            "$a = Get-NetAdapter | Where-Object { $_.Status -eq 'Up' } | Select-Object -First 1; "
            "$ip = (Get-NetIPAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress; "
            "$gw = (Get-NetRoute -InterfaceIndex $a.ifIndex -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue).NextHop; "
            "$dns = (Get-DnsClientServerAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue).ServerAddresses -join ', '; "
            "$mac = $a.MacAddress; "
            "Write-Host \"ADAPTER:$($a.Name)\"; "
            "Write-Host \"TYPE:$($a.InterfaceDescription)\"; "
            "Write-Host \"SPEED:$($a.LinkSpeed)\"; "
            "Write-Host \"IP:$ip\"; "
            "Write-Host \"GATEWAY:$gw\"; "
            "Write-Host \"DNS:$dns\"; "
            "Write-Host \"MAC:$mac\""
        ])
        if code == 0:
            for line in stdout.split("\n"):
                if "ADAPTER:" in line: net_info["adapter"] = line.split(":", 1)[1].strip()
                elif "TYPE:" in line: net_info["type"] = line.split(":", 1)[1].strip()
                elif "SPEED:" in line: net_info["speed"] = line.split(":", 1)[1].strip()
                elif "IP:" in line: net_info["ip"] = line.split(":", 1)[1].strip()
                elif "GATEWAY:" in line: net_info["gateway"] = line.split(":", 1)[1].strip()
                elif "DNS:" in line: net_info["dns"] = line.split(":", 1)[1].strip()
                elif "MAC:" in line: net_info["mac"] = line.split(":", 1)[1].strip()

            self.after(0, lambda: self._update_diag_card("adapter", f"{net_info.get('adapter','?')} ({net_info.get('type','?')})\nHız: {net_info.get('speed','?')}", is_ok=True))
            self.after(0, lambda: self._update_diag_card("local_ip", f"IPv4: {net_info.get('ip','?')}\nAğ Geçidi: {net_info.get('gateway','?')}\nDNS: {net_info.get('dns','?')}", is_ok=True))

        # Test 1: İnternet Bağlantısı
        if _cancelled(): return self._finish_diagnostics(results, passed, warnings, failed, recommendations, net_info)
        _progress(1)
        _out("[1/12] İnternet Bağlantısı")
        code, stdout, _ = _run_cmd(["ping", "8.8.8.8", "-n", "4", "-w", "3000"])
        if code == 0:
            avg_m = re.search(r'(?:Ortalama|Average)\s*=\s*(\d+)ms', stdout)
            avg_ms = avg_m.group(1) if avg_m else "?"
            loss_m = re.search(r'\((\d+)%.*(?:kay|loss)', stdout, re.IGNORECASE)
            loss_pct = loss_m.group(1) if loss_m else "0"
            if int(loss_pct) == 0:
                _out(f"  ✅ BAŞARILI — Gecikme: {avg_ms}ms, Kayıp: %0")
                results.append(("İnternet Bağlantısı", "OK")); passed += 1
            else:
                _out(f"  ⚠️ UYARI — Paket kaybı: %{loss_pct}, Gecikme: {avg_ms}ms")
                results.append(("İnternet Bağlantısı", "Uyarı")); warnings += 1
                recommendations.append("⚡ Paket kaybı tespit edildi. Router'ınızı yeniden başlatmayı veya kablolu bağlantıya geçmeyi deneyin.")
        else:
            _out("  ❌ BAŞARISIZ — İnternet bağlantısı kurulamıyor")
            results.append(("İnternet Bağlantısı", "Hata")); failed += 1
            recommendations.append("🔌 İnternet bağlantınız yok. Kablo ve Wi-Fi bağlantınızı kontrol edin.")
        _out("")

        # Test 2: DNS Çözümleme
        if _cancelled(): return self._finish_diagnostics(results, passed, warnings, failed, recommendations, net_info)
        _progress(2)
        _out("[2/12] DNS Çözümleme")
        code, stdout, _ = _run_cmd(["nslookup", "google.com"])
        if code == 0 and "Address" in stdout:
            resolved_ip = ""
            for line in reversed(stdout.split("\n")):
                ip_m = re.search(r'Address[:\s]+([\d.]+)', line)
                if ip_m and not ip_m.group(1).endswith(".1"):
                    resolved_ip = ip_m.group(1); break
            _out(f"  ✅ BAŞARILI — Çözümlenen: {resolved_ip or 'mevcut'}")
            results.append(("DNS Çözümleme", "OK")); passed += 1
        else:
            _out("  ❌ BAŞARISIZ — DNS alan adını çözümleyemiyor")
            results.append(("DNS Çözümleme", "Hata")); failed += 1
            recommendations.append("🌐 DNS çözümleme başarısız. 'DNS Önbelleğini Temizle' görevini çalıştırın.")
        _out("")

        # Test 3: Ağ Geçidi
        if _cancelled(): return self._finish_diagnostics(results, passed, warnings, failed, recommendations, net_info)
        _progress(3)
        _out("[3/12] Varsayılan Ağ Geçidi (Router)")
        gateway_ip = net_info.get("gateway", "")
        if gateway_ip and gateway_ip != "None":
            code, stdout, _ = _run_cmd(["ping", gateway_ip, "-n", "2", "-w", "2000"])
            gw_ping = re.search(r'(?:Ortalama|Average)\s*=\s*(\d+)ms', stdout)
            gw_lat = gw_ping.group(1) if gw_ping else "?"
            if code == 0:
                _out(f"  ✅ BAŞARILI — Gateway: {gateway_ip}, Gecikme: {gw_lat}ms")
                results.append(("Ağ Geçidi", "OK")); passed += 1
            else:
                _out(f"  ⚠️ UYARI — Gateway {gateway_ip} yanıt vermiyor")
                results.append(("Ağ Geçidi", "Uyarı")); warnings += 1
                recommendations.append("🏠 Router/modem yanıt vermiyor. Cihazı yeniden başlatmayı deneyin.")
        else:
            _out("  ❌ BAŞARISIZ — Ağ geçidi bulunamadı")
            results.append(("Ağ Geçidi", "Hata")); failed += 1
        _out("")

        # Test 4: Ağ Adaptörü
        if _cancelled(): return self._finish_diagnostics(results, passed, warnings, failed, recommendations, net_info)
        _progress(4)
        _out("[4/12] Ağ Adaptörü Durumu")
        code, stdout, _ = _run_cmd(["powershell", "-Command", "Get-NetAdapter | Where-Object { $_.Status -eq 'Up' } | Select-Object Name, LinkSpeed | Format-Table -AutoSize"])
        if code == 0 and ("Up" in stdout or stdout.strip()):
            _out(f"  ✅ BAŞARILI — Adaptörler aktif ve çalışır durumda")
            results.append(("Ağ Adaptörü", "OK")); passed += 1
        else:
            _out("  ❌ BAŞARISIZ — Aktif ağ adaptörü bulunamadı")
            results.append(("Ağ Adaptörü", "Hata")); failed += 1
        _out("")

        # Test 5: DNS Kıyaslama
        if _cancelled(): return self._finish_diagnostics(results, passed, warnings, failed, recommendations, net_info)
        _progress(5)
        _out("[5/12] DNS Performans Kıyaslaması")
        dns_list = [("Yerel DNS", []), ("Google (8.8.8.8)", ["8.8.8.8"]), ("Cloudflare (1.1.1.1)", ["1.1.1.1"])]
        dns_times = {}
        for dname, dargs in dns_list:
            t0 = time.time()
            c, out, _ = _run_cmd(["nslookup", "example.com"] + dargs, timeout=6)
            elapsed = int((time.time() - t0) * 1000)
            if c == 0 and "Address" in out:
                dns_times[dname] = elapsed
                _out(f"  ✅ {dname:<22} : {elapsed}ms")
            else:
                _out(f"  ❌ {dname:<22} : yanıt yok")
        if dns_times:
            best_dns = min(dns_times, key=dns_times.get)
            _out(f"  → En hızlı DNS: {best_dns} ({dns_times[best_dns]}ms)")
            results.append(("DNS Kıyaslama", "OK")); passed += 1
        else:
            results.append(("DNS Kıyaslama", "Hata")); failed += 1
        _out("")

        # Test 6: Jitter
        if _cancelled(): return self._finish_diagnostics(results, passed, warnings, failed, recommendations, net_info)
        _progress(6)
        _out("[6/12] Gecikme Kararlılığı (Jitter)")
        code, stdout, _ = _run_cmd(["ping", "8.8.8.8", "-n", "6", "-w", "3000"])
        if code == 0:
            times = [int(m) for m in re.findall(r'(?:süre|time)[=<](\d+)ms', stdout, re.IGNORECASE)]
            if len(times) >= 2:
                avg_t = sum(times) / len(times)
                jitter = max(times) - min(times)
                if jitter < 25:
                    _out(f"  ✅ BAŞARILI — Ort: {avg_t:.0f}ms, Jitter: {jitter}ms (kararlı)")
                    results.append(("Jitter", "OK")); passed += 1
                else:
                    _out(f"  ⚠️ UYARI — Ort: {avg_t:.0f}ms, Jitter: {jitter}ms (dalgalanma var)")
                    results.append(("Jitter", "Uyarı")); warnings += 1
            else:
                results.append(("Jitter", "Uyarı")); warnings += 1
        else:
            results.append(("Jitter", "Hata")); failed += 1
        _out("")

        # Test 7: HTTPS Testi
        if _cancelled(): return self._finish_diagnostics(results, passed, warnings, failed, recommendations, net_info)
        _progress(7)
        _out("[7/12] HTTPS Bağlantı & SSL Testi")
        code, stdout, _ = _run_cmd(["powershell", "-Command", "try { $r = Invoke-WebRequest -Uri 'https://www.google.com' -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop; Write-Host \"STATUS:$($r.StatusCode)\" } catch { Write-Host \"FAIL\" }"], timeout=15)
        if "STATUS:200" in stdout:
            _out("  ✅ BAŞARILI — HTTPS (SSL/TLS) bağlantısı kusursuz")
            results.append(("HTTPS", "OK")); passed += 1
        else:
            _out("  ❌ BAŞARISIZ — Web güvenli bağlantı hatası")
            results.append(("HTTPS", "Hata")); failed += 1
        _out("")

        # Test 8: Port Erişimi
        if _cancelled(): return self._finish_diagnostics(results, passed, warnings, failed, recommendations, net_info)
        _progress(8)
        _out("[8/12] Port Erişilebilirliği (80, 443, 53, 587)")
        code, stdout, _ = _run_cmd(["powershell", "-Command",
            "$ports = @(@{H='google.com';P=80},@{H='google.com';P=443},@{H='8.8.8.8';P=53},@{H='smtp.gmail.com';P=587}); "
            "$ok=0; foreach($p in $ports){ try{ $tcp = New-Object System.Net.Sockets.TcpClient; "
            "$r = $tcp.BeginConnect($p.H,$p.P,$null,$null); if($r.AsyncWaitHandle.WaitOne(2500,$false) -and $tcp.Connected){ $ok++ }; $tcp.Close() }catch{} }; "
            "Write-Host \"PORT_OK:$ok/4\""
        ], timeout=20)
        p_match = re.search(r'PORT_OK:(\d+)/4', stdout)
        if p_match and int(p_match.group(1)) >= 3:
            _out(f"  ✅ BAŞARILI — {p_match.group(1)}/4 port erişilebilir")
            results.append(("Port Erişimi", "OK")); passed += 1
        else:
            _out("  ⚠️ UYARI — Bazı önemli portlar engelleniyor")
            results.append(("Port Erişimi", "Uyarı")); warnings += 1
        _out("")

        # Test 9: Public IP & ISP
        if _cancelled(): return self._finish_diagnostics(results, passed, warnings, failed, recommendations, net_info)
        _progress(9)
        _out("[9/12] Public IP & ISP Tespiti")
        code, stdout, _ = _run_cmd(["powershell", "-Command",
            "try { $r = Invoke-RestMethod -Uri 'http://ip-api.com/json/?fields=query,isp,org,city,country' -TimeoutSec 8 -ErrorAction Stop; "
            "Write-Host \"IP:$($r.query)\"; Write-Host \"ISP:$($r.isp)\"; Write-Host \"LOC:$($r.city), $($r.country)\" } catch { Write-Host 'FAIL' }"
        ], timeout=15)
        if "IP:" in stdout:
            p_ip = re.search(r'IP:(.*)', stdout).group(1).strip()
            p_isp = re.search(r'ISP:(.*)', stdout).group(1).strip()
            p_loc = re.search(r'LOC:(.*)', stdout).group(1).strip()
            _out(f"  ✅ Dış IP : {p_ip}\n     ISP    : {p_isp}\n     Konum  : {p_loc}")
            self.after(0, lambda: self._update_diag_card("public_ip", f"Dış IP: {p_ip}\nISP: {p_isp}\nKonum: {p_loc}", is_ok=True))
            results.append(("Public IP", "OK")); passed += 1
        else:
            _out("  ⚠️ UYARI — Dış IP bilgisi alınamadı")
            results.append(("Public IP", "Uyarı")); warnings += 1
        _out("")

        # Test 10: VPN / Proxy
        if _cancelled(): return self._finish_diagnostics(results, passed, warnings, failed, recommendations, net_info)
        _progress(10)
        _out("[10/12] VPN / Proxy Tespiti")
        code, stdout, _ = _run_cmd(["powershell", "-Command",
            "$vpn = Get-NetAdapter | Where-Object { $_.InterfaceDescription -match 'TAP|TUN|VPN|WireGuard|Wintun|Windscribe|Nord' -and $_.Status -eq 'Up' }; "
            "if($vpn){ Write-Host \"VPN:$($vpn.Name)\" } else { Write-Host 'NO_VPN' }"
        ])
        if "VPN:" in stdout:
            vpn_n = re.search(r'VPN:(.*)', stdout).group(1).strip()
            _out(f"  🔐 Aktif VPN bulundu: {vpn_n}")
            self.after(0, lambda: self._update_diag_card("vpn", f"Aktif VPN: {vpn_n}", is_ok=True))
        else:
            _out("  ℹ️  VPN veya proxy tespit edilmedi (Doğrudan bağlantı)")
            self.after(0, lambda: self._update_diag_card("vpn", "VPN/Proxy Yok (Doğrudan Bağlantı)", is_ok=True))
        results.append(("VPN/Proxy", "OK")); passed += 1
        _out("")

        # Test 11: Wi-Fi Sinyal
        if _cancelled(): return self._finish_diagnostics(results, passed, warnings, failed, recommendations, net_info)
        _progress(11)
        _out("[11/12] Wi-Fi Sinyal & Bağlantı Kalitesi")
        code, stdout, _ = _run_cmd(["netsh", "wlan", "show", "interfaces"])
        if code == 0 and "SSID" in stdout:
            sig_m = re.search(r'(?:Signal|Sinyal)\s*:\s*(\d+)%', stdout)
            ssid_m = re.search(r'SSID\s*:\s*(.+)', stdout)
            chan_m = re.search(r'(?:Channel|Kanal)\s*:\s*(\d+)', stdout)
            sig = sig_m.group(1) if sig_m else "?"
            ssid = ssid_m.group(1).strip() if ssid_m else "?"
            chan = chan_m.group(1).strip() if chan_m else "?"
            _out(f"  SSID: {ssid} | Sinyal: %{sig} | Kanal: {chan}")
            self.after(0, lambda: self._update_diag_card("wifi", f"SSID: {ssid}\nSinyal Gücü: %{sig}\nKanal: {chan}", is_ok=True))
            results.append(("Wi-Fi Sinyal", "OK")); passed += 1
        else:
            _out("  ℹ️  Kablolu (Ethernet) bağlantı aktif")
            self.after(0, lambda: self._update_diag_card("wifi", "Kablolu Bağlantı (Ethernet)", is_ok=True))
            results.append(("Wi-Fi Sinyal", "OK")); passed += 1
        _out("")

        # Test 12: İndirme Hızı
        if _cancelled(): return self._finish_diagnostics(results, passed, warnings, failed, recommendations, net_info)
        _progress(12)
        _out("[12/12] İndirme Hızı Tahmini")
        code, stdout, _ = _run_cmd(["powershell", "-Command",
            "try { $sw = [System.Diagnostics.Stopwatch]::StartNew(); "
            "$wc = New-Object System.Net.WebClient; $data = $wc.DownloadData('http://speed.cloudflare.com/__down?bytes=2000000'); "
            "$sw.Stop(); $mbps = [math]::Round(($data.Length * 8) / ($sw.Elapsed.TotalSeconds * 1000000), 2); "
            "Write-Host \"SPEED:$mbps\" } catch { Write-Host 'FAIL' }"
        ], timeout=25)
        spd_m = re.search(r'SPEED:([\d.]+)', stdout)
        if spd_m:
            _out(f"  ✅ BAŞARILI — Ölçülen Hız: ~{spd_m.group(1)} Mbps")
            results.append(("Hız Testi", "OK")); passed += 1
        else:
            _out("  ⚠️ Hız ölçümü tamamlanamadı")
            results.append(("Hız Testi", "Uyarı")); warnings += 1
        _out("")

        self._finish_diagnostics(results, passed, warnings, failed, recommendations, net_info)

    def _update_diag_card(self, key: str, value: str, is_ok: bool = True) -> None:
        if key in self.diag_cards:
            frame, lbl = self.diag_cards[key]
            lbl.configure(text=value, text_color=PALETTE["text_main"])
            if is_ok:
                frame.configure(border_color=PALETTE["accent"])

    def _finish_diagnostics(self, results, passed, warnings, failed, recommendations=None, net_info=None) -> None:
        def _out(msg):
            self.task_queue.put({"action": "append_diag", "message": msg})

        total = passed + warnings + failed
        _out("═" * 58)
        _out("                    SONUÇ TABLOSU")
        _out("─" * 58)
        for tname, status in results:
            icon = "✅" if status == "OK" else ("⚠️" if status == "Uyarı" else "❌")
            _out(f"  {icon}  {tname:<32} {status}")
        _out("─" * 58)
        _out(f"  📊 {passed} Başarılı  |  {warnings} Uyarı  |  {failed} Başarısız")
        _out("")

        if failed == 0 and warnings == 0:
            verdict = "✅ Ağ bağlantınız kusursuz çalışıyor!"
            db_status = "OK"
        elif failed == 0:
            verdict = f"⚠️ Ağ çoğunlukla sağlıklı ({warnings} uyarı var)."
            db_status = "Uyarı"
        else:
            verdict = f"❌ Ağda problemler tespit edildi ({failed} başarısız)."
            db_status = "Hata"

        _out(f"  Sonuç: {verdict}")

        if recommendations:
            _out("")
            _out("═" * 58)
            _out("  💡 ÖNERİLEN ÇÖZÜMLER")
            _out("─" * 58)
            for i, rec in enumerate(set(recommendations), 1):
                _out(f"  {i}. {rec}")

        _out("═" * 58)

        detail_text = f"Tanılama: {passed} OK, {warnings} Uyarı, {failed} Hata\n" + "\n".join([f"{n}: {s}" for n, s in results])
        self.task_queue.put({"action": "add_log", "task_name": "Gelişmiş Ağ Tanılama", "status": db_status, "details": detail_text})
        self.task_queue.put({"action": "update_progress", "value": 100})
        self.task_queue.put({"action": "finish_batch"})

    # ══════════════════════════════════════════════════════════════════════════
    # VIEW 3: İŞLEM GÜNLÜĞÜ (LOGS)
    # ══════════════════════════════════════════════════════════════════════════
    def _create_logs_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.main_container, fg_color="transparent")
        view.grid_rowconfigure(1, weight=1)
        view.grid_columnconfigure(0, weight=1)

        # Controls Header
        top_hdr = ctk.CTkFrame(view, fg_color=PALETTE["card_bg"], corner_radius=10, border_width=1, border_color=PALETTE["card_border"])
        top_hdr.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        top_inner = ctk.CTkFrame(top_hdr, fg_color="transparent")
        top_inner.pack(fill="x", padx=12, pady=10)

        # Search box
        self.log_search_entry = ctk.CTkEntry(
            top_inner,
            placeholder_text="🔍 Log ara...",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            height=34,
            width=200,
            fg_color=PALETTE["inner_bg"],
            border_color=PALETTE["card_border"],
            corner_radius=6
        )
        self.log_search_entry.pack(side="left", padx=(0, 8))
        self.log_search_entry.bind("<KeyRelease>", lambda e: self.refresh_logs())

        # Status Filter Segment
        self.log_filter_var = ctk.StringVar(value="Tümü")
        self.log_seg_btn = ctk.CTkSegmentedButton(
            top_inner,
            values=["Tümü", "OK", "Uyarı", "Hata"],
            variable=self.log_filter_var,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            selected_color=PALETTE["accent"],
            selected_hover_color=PALETTE["accent_hover"],
            height=32,
            command=lambda v: self.refresh_logs()
        )
        self.log_seg_btn.pack(side="left", padx=4)

        # Action Buttons
        act_box = ctk.CTkFrame(top_inner, fg_color="transparent")
        act_box.pack(side="right")

        ctk.CTkButton(
            act_box,
            text="🔄 Yenile",
            width=75,
            height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=PALETTE["inner_bg"],
            hover_color=PALETTE["card_hover"],
            corner_radius=6,
            command=self.refresh_logs
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            act_box,
            text="📥 CSV İndir",
            width=85,
            height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=PALETTE["inner_bg"],
            hover_color=PALETTE["card_hover"],
            corner_radius=6,
            command=self.export_logs_to_csv
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            act_box,
            text="🗑️ Temizle",
            width=75,
            height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=PALETTE["danger"],
            hover_color=PALETTE["danger_hover"],
            corner_radius=6,
            command=self.clear_logs_with_confirm
        ).pack(side="left", padx=2)

        # Logs Scrollable Card List
        self.logs_scroll = ctk.CTkScrollableFrame(
            view,
            fg_color=PALETTE["card_bg"],
            corner_radius=10,
            border_width=1,
            border_color=PALETTE["card_border"]
        )
        self.logs_scroll.grid(row=1, column=0, sticky="nsew")

        return view

    def refresh_logs(self) -> None:
        if not hasattr(self, "logs_scroll"):
            return

        for widget in self.logs_scroll.winfo_children():
            widget.destroy()

        filter_status = self.log_filter_var.get() if hasattr(self, "log_filter_var") else "Tümü"
        search_kw = self.log_search_entry.get().strip() if hasattr(self, "log_search_entry") else ""
        
        rows, _ = self.db.get_logs(date_filter="Tümü", status_filter=filter_status, search_text=search_kw)

        if not rows:
            ctk.CTkLabel(
                self.logs_scroll,
                text="Henüz kaydedilmiş bir işlem günlüğü bulunamadı.",
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                text_color=PALETTE["text_dim"],
                pady=40
            ).pack(fill="x")
            return

        for row in rows:
            ts, task, status, details = row[0], row[1], row[2], row[3]
            
            # Status colors
            if status == "OK":
                st_color = PALETTE["success"]
                st_bg = PALETTE["success_bg"]
            elif status == "Uyarı":
                st_color = PALETTE["warning"]
                st_bg = PALETTE["warning_bg"]
            else:
                st_color = PALETTE["danger"]
                st_bg = "#450a0a"

            row_card = ctk.CTkFrame(
                self.logs_scroll,
                fg_color=PALETTE["inner_bg"],
                corner_radius=8,
                border_width=1,
                border_color=PALETTE["card_border"],
                height=46
            )
            row_card.pack(fill="x", padx=4, pady=3)

            # Status Badge
            badge = ctk.CTkLabel(
                row_card,
                text=status,
                font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
                fg_color=st_bg,
                text_color=st_color,
                corner_radius=6,
                width=54,
                height=24
            )
            badge.pack(side="left", padx=10, pady=8)

            # Task Title
            title_lbl = ctk.CTkLabel(
                row_card,
                text=task,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                text_color=PALETTE["text_main"],
                anchor="w"
            )
            title_lbl.pack(side="left", padx=6)

            # Timestamp & Details Button
            det_btn = ctk.CTkButton(
                row_card,
                text="Detayları Gör",
                width=90,
                height=26,
                font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                fg_color=PALETTE["card_bg"],
                hover_color=PALETTE["card_hover"],
                command=lambda r=row: self.open_log_detail_popup(r)
            )
            det_btn.pack(side="right", padx=10, pady=8)

            time_lbl = ctk.CTkLabel(
                row_card,
                text=ts,
                font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                text_color=PALETTE["text_dim"]
            )
            time_lbl.pack(side="right", padx=8)

    def open_log_detail_popup(self, row: tuple) -> None:
        ts, task, status, details = row[0], row[1], row[2], row[3]
        
        dialog = ctk.CTkToplevel(self)
        dialog.title("OYAX - İşlem Detayları")
        dialog.geometry("700x520")
        dialog.configure(fg_color=PALETTE["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()

        container = ctk.CTkFrame(dialog, fg_color=PALETTE["card_bg"], corner_radius=12, border_width=1, border_color=PALETTE["card_border"])
        container.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            container,
            text=f"📋 {task}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color=PALETTE["text_main"]
        ).pack(anchor="w", padx=16, pady=(16, 4))

        ctk.CTkLabel(
            container,
            text=f"Tarih: {ts}   |   Durum: {status}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=PALETTE["text_muted"]
        ).pack(anchor="w", padx=16, pady=(0, 12))

        txt = ctk.CTkTextbox(
            container,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=PALETTE["inner_bg"],
            text_color="#f8fafc",
            corner_radius=8,
            wrap="word"
        )
        txt.pack(fill="both", expand=True, padx=16, pady=(0, 14))
        txt.insert("1.0", str(details).replace("\\n", "\n"))
        txt.configure(state="disabled")

        act_row = ctk.CTkFrame(container, fg_color="transparent")
        act_row.pack(fill="x", padx=16, pady=(0, 16))

        def copy_log():
            dialog.clipboard_clear()
            dialog.clipboard_append(f"Görev: {task}\nTarih: {ts}\nDurum: {status}\n\nDetaylar:\n{details}")
            self.show_toast("📋 Log detayı kopyalandı")

        def export_log_txt():
            safe_time = str(ts).replace(":", "-").replace(" ", "_")
            p = filedialog.asksaveasfilename(parent=dialog, title="Log TXT Kaydet", defaultextension=".txt", initialfile=f"oyax_log_{safe_time}.txt")
            if p:
                with open(p, "w", encoding="utf-8") as f:
                    f.write(f"Görev: {task}\nTarih: {ts}\nDurum: {status}\n\nDetaylar:\n{details}")
                self.show_toast("💾 TXT dosyası kaydedildi")

        ctk.CTkButton(act_row, text="📋 Kopyala", width=90, height=32, font=ctk.CTkFont(family=FONT_FAMILY, size=11), fg_color=PALETTE["inner_bg"], hover_color=PALETTE["card_hover"], command=copy_log).pack(side="left", padx=2)
        ctk.CTkButton(act_row, text="💾 TXT İndir", width=90, height=32, font=ctk.CTkFont(family=FONT_FAMILY, size=11), fg_color=PALETTE["inner_bg"], hover_color=PALETTE["card_hover"], command=export_log_txt).pack(side="left", padx=4)
        ctk.CTkButton(act_row, text="Kapat", width=80, height=32, font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"), fg_color=PALETTE["accent"], hover_color=PALETTE["accent_hover"], command=dialog.destroy).pack(side="right")

    def export_logs_to_csv(self) -> None:
        save_path = filedialog.asksaveasfilename(title="Logları CSV Olarak Kaydet", defaultextension=".csv", filetypes=[("CSV dosyası", "*.csv")])
        if not save_path: return
        try:
            self.db.export_to_csv(save_path)
            self.show_toast("📥 Loglar CSV olarak kaydedildi")
        except Exception as ex:
            messagebox.showerror("Hata", f"Dışa aktarma hatası: {ex}")

    def clear_logs_with_confirm(self) -> None:
        if not messagebox.askyesno("Onay", "Tüm log geçmişini silmek istediğinize emin misiniz?\nBu işlem geri alınamaz."):
            return
        self.db.clear_logs()
        self.refresh_logs()
        self.show_toast("🗑️ Log geçmişi temizlendi")

    # ══════════════════════════════════════════════════════════════════════════
    # VIEW 4: AYARLAR & HAKKINDA
    # ══════════════════════════════════════════════════════════════════════════
    def _create_about_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.main_container, fg_color="transparent")
        view.grid_rowconfigure(0, weight=1)
        view.grid_columnconfigure(0, weight=1)

        center_card = ctk.CTkFrame(view, fg_color=PALETTE["card_bg"], corner_radius=12, border_width=1, border_color=PALETTE["card_border"])
        center_card.pack(fill="both", expand=True, padx=20, pady=20)

        inner = ctk.CTkFrame(center_card, fg_color="transparent")
        inner.pack(padx=30, pady=30, fill="both", expand=True)

        ctk.CTkLabel(
            inner,
            text="⚡ OYAX - Windows Sistem & Ağ Bakım Aracı",
            font=ctk.CTkFont(family=FONT_FAMILY, size=20, weight="bold"),
            text_color=PALETTE["text_main"]
        ).pack(anchor="w", pady=(0, 6))

        info_row = ctk.CTkFrame(inner, fg_color="transparent")
        info_row.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            info_row,
            text=f"Sürüm: v{APP_VERSION}   |   Geliştirici: {AUTHOR_NAME}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=PALETTE["text_muted"]
        ).pack(side="left")

        eula_btn = ctk.CTkButton(
            info_row,
            text="📜 EULA Koşulları",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, underline=True),
            fg_color="transparent",
            text_color=PALETTE["accent"],
            hover_color=PALETTE["card_hover"],
            height=24,
            command=lambda: webbrowser.open_new("https://github.com/furkanyasarr0/OYAX/blob/main/EULA.md")
        )
        eula_btn.pack(side="right")

        desc_text = (
            "OYAX, Windows işletim sisteminiz için geçici dosya temizliği, disk optimizasyonu,\n"
            "derinlemesine ağ tanılama ve onarım işlemlerini tek çatı altında sunan modern bir açık kaynak bakım aracıdır."
        )
        ctk.CTkLabel(
            inner,
            text=desc_text,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=PALETTE["text_muted"],
            justify="left",
            anchor="w"
        ).pack(anchor="w", pady=(0, 20))

        # Update Card
        upd_card = ctk.CTkFrame(inner, fg_color=PALETTE["inner_bg"], corner_radius=10, border_width=1, border_color=PALETTE["card_border"])
        upd_card.pack(fill="x", pady=(0, 20))

        upd_inner = ctk.CTkFrame(upd_card, fg_color="transparent")
        upd_inner.pack(fill="x", padx=16, pady=16)

        ctk.CTkLabel(
            upd_inner,
            text="🔄 GitHub Sürüm Kontrolü",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=PALETTE["text_main"]
        ).pack(anchor="w", pady=(0, 4))

        self.upd_status_lbl = ctk.CTkLabel(
            upd_inner,
            text="Durum: Kontrol edilmedi",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=PALETTE["text_muted"]
        )
        self.upd_status_lbl.pack(anchor="w", pady=(0, 10))

        self.check_upd_btn = ctk.CTkButton(
            upd_inner,
            text="Güncellemeleri Kontrol Et",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=PALETTE["accent"],
            hover_color=PALETTE["accent_hover"],
            height=34,
            corner_radius=6,
            command=self.start_update_check
        )
        self.check_upd_btn.pack(anchor="w")

        # Appearance Settings
        app_card = ctk.CTkFrame(inner, fg_color=PALETTE["inner_bg"], corner_radius=10, border_width=1, border_color=PALETTE["card_border"])
        app_card.pack(fill="x")

        app_inner = ctk.CTkFrame(app_card, fg_color="transparent")
        app_inner.pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(
            app_inner,
            text="🎨 Görünüm Teması",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=PALETTE["text_main"]
        ).pack(side="left")

        theme_menu = ctk.CTkOptionMenu(
            app_inner,
            values=["Dark", "Light", "System"],
            command=lambda m: ctk.set_appearance_mode(m),
            height=30,
            corner_radius=6,
            fg_color=PALETTE["card_bg"],
            button_color=PALETTE["accent"]
        )
        theme_menu.pack(side="right")
        theme_menu.set("Dark")

        return view

    # ══════════════════════════════════════════════════════════════════════════
    # AUTO-UPDATER ENGINE & DIALOG
    # ══════════════════════════════════════════════════════════════════════════
    def _auto_check_update_on_startup(self) -> None:
        """Silently checks for updates in background on launch; prompts if a newer version is found."""
        threading.Thread(target=self._startup_update_worker, daemon=True).start()

    def _startup_update_worker(self) -> None:
        repo = "furkanyasarr0/OYAX"
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "OyaxAutoUpdater"})
            with urllib.request.urlopen(req, timeout=6) as res:
                data = json.loads(res.read().decode("utf-8"))
            
            tag = str(data.get("tag_name", "")).strip().lstrip("vV")
            if tag and is_newer_version(tag, APP_VERSION):
                notes = data.get("body", "Yeni özellikler ve hata düzeltmeleri içerir.")
                html_url = data.get("html_url", f"https://github.com/{repo}/releases")
                self.after(0, lambda: self._show_update_available_dialog(tag, notes, html_url, data))
        except Exception:
            pass

    def start_update_check(self) -> None:
        self.upd_status_lbl.configure(text="Durum: GitHub üzerinden kontrol ediliyor...")
        self.check_upd_btn.configure(state="disabled")
        threading.Thread(target=self._update_check_worker, daemon=True).start()

    def _update_check_worker(self) -> None:
        repo = "furkanyasarr0/OYAX"
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "OyaxUpdater"})
            with urllib.request.urlopen(req, timeout=8) as res:
                data = json.loads(res.read().decode("utf-8"))
            
            tag = str(data.get("tag_name", "")).strip().lstrip("vV")
            if tag and is_newer_version(tag, APP_VERSION):
                msg = f"✨ Yeni sürüm mevcut: v{tag} (Mevcut: v{APP_VERSION})"
                notes = data.get("body", "Yeni özellikler ve hata düzeltmeleri içerir.")
                html_url = data.get("html_url", f"https://github.com/{repo}/releases")
                self.after(0, lambda: self._show_update_available_dialog(tag, notes, html_url, data))
            else:
                msg = f"✅ En güncel sürümü kullanıyorsunuz (v{APP_VERSION})"
        except Exception as ex:
            msg = f"Güncelleme kontrolü başarısız: {ex}"

        self.after(0, lambda: self.upd_status_lbl.configure(text=msg))
        self.after(0, lambda: self.check_upd_btn.configure(state="normal"))

    def _show_update_available_dialog(self, new_version: str, notes: str, release_url: str, release_data: dict) -> None:
        """Displays an interactive update modal dialog with one-click direct update button."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("OYAX - Yeni Güncelleme")
        dialog.geometry("560x420")
        dialog.minsize(500, 380)
        dialog.configure(fg_color=PALETTE["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()

        container = ctk.CTkFrame(dialog, fg_color=PALETTE["card_bg"], corner_radius=12, border_width=1, border_color=PALETTE["card_border"])
        container.pack(fill="both", expand=True, padx=16, pady=16)

        # Header Badge & Title
        hdr_box = ctk.CTkFrame(container, fg_color="transparent")
        hdr_box.pack(fill="x", padx=16, pady=(16, 6))

        ctk.CTkLabel(
            hdr_box,
            text=f"✨ Yeni Güncelleme Mevcut!",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color=PALETTE["text_main"]
        ).pack(side="left")

        ctk.CTkLabel(
            hdr_box,
            text=f"v{new_version}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=PALETTE["accent"],
            text_color="#ffffff",
            corner_radius=6,
            padx=8,
            pady=2
        ).pack(side="right")

        ctk.CTkLabel(
            container,
            text=f"Mevcut sürüm: v{APP_VERSION}  ➔  Yeni sürüm: v{new_version}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=PALETTE["text_muted"]
        ).pack(anchor="w", padx=16, pady=(0, 8))

        # Release notes text
        ctk.CTkLabel(container, text="Sürüm Notları:", font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"), text_color=PALETTE["text_main"]).pack(anchor="w", padx=16, pady=(4, 2))
        
        notes_box = ctk.CTkTextbox(container, font=ctk.CTkFont(family=FONT_FAMILY, size=11), fg_color=PALETTE["inner_bg"], text_color="#cbd5e1", corner_radius=8, height=130, wrap="word")
        notes_box.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        notes_box.insert("1.0", notes.strip() if notes else "Yeni özellikler ve hata düzeltmeleri.")
        notes_box.configure(state="disabled")

        # In-Dialog Update Status
        upd_status_lbl = ctk.CTkLabel(container, text="", font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=PALETTE["text_muted"])
        upd_status_lbl.pack(fill="x", padx=16, pady=(0, 6))

        upd_prog = ctk.CTkProgressBar(container, height=6, corner_radius=3, progress_color=PALETTE["accent"], fg_color=PALETTE["inner_bg"])
        upd_prog.set(0)

        # Action Buttons
        btn_box = ctk.CTkFrame(container, fg_color="transparent")
        btn_box.pack(fill="x", padx=16, pady=(0, 16))

        def on_direct_update():
            upd_prog.pack(fill="x", padx=16, pady=(0, 10))
            upd_status_lbl.configure(text="🚀 Güncelleme başlatılıyor, dosyalar indiriliyor...")
            update_now_btn.configure(state="disabled")
            later_btn.configure(state="disabled")
            threading.Thread(target=self._perform_direct_update, args=(dialog, upd_status_lbl, upd_prog, new_version, release_url), daemon=True).start()

        update_now_btn = ctk.CTkButton(
            btn_box,
            text="🚀  Şimdi Güncelle",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=PALETTE["accent"],
            hover_color=PALETTE["accent_hover"],
            height=36,
            corner_radius=8,
            command=on_direct_update
        )
        update_now_btn.pack(side="left", padx=(0, 6))

        github_btn = ctk.CTkButton(
            btn_box,
            text="🌐 GitHub",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=PALETTE["inner_bg"],
            hover_color=PALETTE["card_hover"],
            height=36,
            width=80,
            corner_radius=8,
            command=lambda: webbrowser.open_new(release_url)
        )
        github_btn.pack(side="left")

        later_btn = ctk.CTkButton(
            btn_box,
            text="Daha Sonra",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color="transparent",
            hover_color=PALETTE["card_hover"],
            text_color=PALETTE["text_muted"],
            height=36,
            width=80,
            corner_radius=8,
            command=dialog.destroy
        )
        later_btn.pack(side="right")

    def _perform_direct_update(self, dialog: ctk.CTkToplevel, status_lbl: ctk.CTkLabel, prog_bar: ctk.CTkProgressBar, new_version: str, release_url: str) -> None:
        """Direct in-app auto updater: Downloads latest code zip, extracts, and restarts app seamlessly."""
        try:
            self.after(0, lambda: prog_bar.set(0.2))
            self.after(0, lambda: status_lbl.configure(text="📥 GitHub üzerinden son sürüm indiriliyor..."))

            repo_zip_url = "https://github.com/furkanyasarr0/OYAX/archive/refs/heads/main.zip"
            temp_dir = os.path.join(os.environ.get("TEMP", os.getcwd()), "oyax_updater_temp")
            os.makedirs(temp_dir, exist_ok=True)
            zip_path = os.path.join(temp_dir, "latest.zip")

            # Download zip with User-Agent
            req = urllib.request.Request(repo_zip_url, headers={"User-Agent": "OyaxDirectUpdater"})
            with urllib.request.urlopen(req, timeout=20) as resp, open(zip_path, "wb") as out_f:
                out_f.write(resp.read())

            self.after(0, lambda: prog_bar.set(0.6))
            self.after(0, lambda: status_lbl.configure(text="📦 Dosyalar ayıklanıyor ve güncelleniyor..."))

            extract_folder = os.path.join(temp_dir, "extracted")
            if os.path.exists(extract_folder):
                shutil.rmtree(extract_folder, ignore_errors=True)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_folder)

            # Locate root extracted repo directory (typically OYAX-main)
            source_root = None
            for root, dirs, files in os.walk(extract_folder):
                if "OYAX.py" in files:
                    source_root = root
                    break

            if not source_root:
                raise Exception("Güncelleme arşivinde OYAX.py bulunamadı.")

            current_dir = os.path.abspath(os.path.dirname(sys.argv[0]))

            # Copy updated files over current directory
            for item in os.listdir(source_root):
                s = os.path.join(source_root, item)
                d = os.path.join(current_dir, item)
                if os.path.isdir(s):
                    if os.path.exists(d):
                        shutil.rmtree(d, ignore_errors=True)
                    shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)

            self.after(0, lambda: prog_bar.set(1.0))
            self.after(0, lambda: status_lbl.configure(text="✅ Güncelleme tamamlandı! Uygulama yeniden başlatılıyor..."))
            time.sleep(1.2)

            # Restart the updated application
            if getattr(sys, 'frozen', False):
                subprocess.Popen([sys.executable])
            else:
                subprocess.Popen([sys.executable, os.path.abspath(sys.argv[0])])

            self.after(0, self.destroy)
            sys.exit(0)

        except Exception as ex:
            self.after(0, lambda: status_lbl.configure(text=f"❌ Güncelleme hatası: {ex}"))
            self.after(0, lambda: messagebox.showerror("Güncelleme Hatası", f"Otomatik güncelleme tamamlanamadı:\n{ex}\n\nGitHub indirme sayfası açılıyor..."))
            self.after(0, lambda: webbrowser.open_new(release_url))
            if dialog:
                self.after(0, dialog.destroy)


if __name__ == "__main__":
    app = OyaxApp()
    app.mainloop()