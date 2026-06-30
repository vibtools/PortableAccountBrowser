from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tkinter as tk
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

from epb.app_icon import apply_window_icon
from epb.browser import BrowserManager, session_status
from epb.config import (
    APP_NAME,
    APP_VERSION,
    BASE_DIR,
    CRASH_DIR,
    DATA_DIR,
    DOWNLOADS_DIR,
    TEMP_DIR,
    assert_portable_root_writable,
)
from epb.database import Database
from epb.diagnostics import collect_diagnostics, report_as_text
from epb.models import EmailProfile
from epb.providers import (
    CATEGORIES,
    CATEGORY_ALL,
    CATEGORY_CUSTOM,
    CATEGORY_MAILBOX,
    account_hint_for,
    account_label_for,
    category_for_provider,
    default_service_for_category,
    default_url_for,
    service_names_for_category,
    validate_start_url,
)
from epb.settings import load_window_geometry, save_window_geometry
from epb.windows_ui import schedule_dark_title_bar

COLORS = {
    "bg": "#08111F",
    "panel": "#0E1B2E",
    "panel_alt": "#13243B",
    "field": "#0A1728",
    "border": "#243A58",
    "accent": "#2F80ED",
    "accent_hover": "#3F8FFF",
    "accent_pressed": "#2569C7",
    "text": "#EDF5FF",
    "muted": "#91A6C1",
    "danger": "#D8616D",
    "danger_hover": "#E2737F",
    "success": "#35B987",
}


def format_timestamp(value: str | None) -> str:
    if not value:
        return "Never"
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.astimezone().strftime("%Y-%m-%d %I:%M %p")
    except ValueError:
        return value


def normalize_add_category(active_category: str) -> str:
    """Return the category used when creating a new profile."""
    return active_category if active_category in CATEGORIES else CATEGORY_MAILBOX


def empty_state_messages(category: str, query: str) -> tuple[str, str]:
    """Return concise empty-list guidance for the current filter state."""
    if query.strip():
        return "No matching profiles", "Try a different search term."
    if category == CATEGORY_ALL:
        return "No profiles yet", "Click + Add to create your first portable profile."
    return (
        f"No {category} profiles",
        f"Click + Add to create a {category.lower()} profile.",
    )


def search_placeholder_visible(search_text: str, has_focus: bool) -> bool:
    return not search_text and not has_focus


def configure_dark_styles(root: tk.Misc) -> None:
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    style.configure("App.TFrame", background=COLORS["bg"])
    style.configure("Panel.TFrame", background=COLORS["panel"])
    style.configure("PanelAlt.TFrame", background=COLORS["panel_alt"])
    style.configure(
        "Title.TLabel",
        background=COLORS["bg"],
        foreground=COLORS["text"],
        font=("Segoe UI", 14, "bold"),
    )
    style.configure(
        "DialogTitle.TLabel",
        background=COLORS["panel"],
        foreground=COLORS["text"],
        font=("Segoe UI", 12, "bold"),
    )
    style.configure(
        "Body.TLabel",
        background=COLORS["panel"],
        foreground=COLORS["text"],
        font=("Segoe UI", 9),
    )
    style.configure(
        "Muted.TLabel",
        background=COLORS["panel"],
        foreground=COLORS["muted"],
        font=("Segoe UI", 8),
    )
    style.configure(
        "HeaderMuted.TLabel",
        background=COLORS["bg"],
        foreground=COLORS["muted"],
        font=("Segoe UI", 8),
    )
    style.configure(
        "Status.TLabel",
        background=COLORS["bg"],
        foreground=COLORS["muted"],
        font=("Segoe UI", 8),
    )

    style.configure(
        "EmptyTitle.TLabel",
        background=COLORS["panel"],
        foreground=COLORS["text"],
        font=("Segoe UI", 11, "bold"),
    )
    style.configure(
        "EmptyHint.TLabel",
        background=COLORS["panel"],
        foreground=COLORS["muted"],
        font=("Segoe UI", 9),
    )

    style.configure(
        "TButton",
        background=COLORS["panel_alt"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["panel_alt"],
        darkcolor=COLORS["panel_alt"],
        padding=(10, 6),
        font=("Segoe UI", 9),
        relief="flat",
    )
    style.map(
        "TButton",
        background=[("active", "#1A3150"), ("pressed", "#0C1A2D"), ("disabled", "#101A29")],
        foreground=[("disabled", "#596B82")],
        bordercolor=[("focus", COLORS["accent"]), ("active", "#34547B")],
    )
    style.configure(
        "Accent.TButton",
        background=COLORS["accent"],
        foreground="#FFFFFF",
        bordercolor=COLORS["accent"],
        lightcolor=COLORS["accent"],
        darkcolor=COLORS["accent"],
        font=("Segoe UI", 9, "bold"),
    )
    style.map(
        "Accent.TButton",
        background=[
            ("active", COLORS["accent_hover"]),
            ("pressed", COLORS["accent_pressed"]),
            ("disabled", "#294A70"),
        ],
        foreground=[("disabled", "#8395AA")],
    )
    style.configure(
        "Danger.TButton",
        background="#3A1C28",
        foreground="#FFB9C1",
        bordercolor="#673040",
    )
    style.map(
        "Danger.TButton",
        background=[("active", "#552438"), ("pressed", "#2B1520")],
        foreground=[("active", "#FFFFFF"), ("disabled", "#72515A")],
    )
    style.configure(
        "Sidebar.TButton",
        anchor="w",
        background=COLORS["panel"],
        foreground=COLORS["muted"],
        bordercolor=COLORS["panel"],
        padding=(11, 8),
    )
    style.map(
        "Sidebar.TButton",
        background=[("active", COLORS["panel_alt"]), ("pressed", "#162A44")],
        foreground=[("active", COLORS["text"])],
    )
    style.configure(
        "SidebarActive.TButton",
        anchor="w",
        background=COLORS["accent"],
        foreground="#FFFFFF",
        bordercolor=COLORS["accent"],
        padding=(11, 8),
        font=("Segoe UI", 9, "bold"),
    )
    style.map(
        "SidebarActive.TButton",
        background=[("active", COLORS["accent_hover"]), ("pressed", COLORS["accent_pressed"])],
    )

    style.configure(
        "TEntry",
        fieldbackground=COLORS["field"],
        foreground=COLORS["text"],
        insertcolor=COLORS["text"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["border"],
        darkcolor=COLORS["border"],
        padding=6,
    )
    style.map("TEntry", bordercolor=[("focus", COLORS["accent"])])
    style.configure(
        "TCombobox",
        fieldbackground=COLORS["field"],
        background=COLORS["panel_alt"],
        foreground=COLORS["text"],
        arrowcolor=COLORS["text"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["border"],
        darkcolor=COLORS["border"],
        padding=5,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", COLORS["field"])],
        foreground=[("readonly", COLORS["text"])],
        bordercolor=[("focus", COLORS["accent"])],
    )

    style.configure(
        "Treeview",
        background=COLORS["panel"],
        fieldbackground=COLORS["panel"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["border"],
        darkcolor=COLORS["border"],
        rowheight=30,
        font=("Segoe UI", 9),
    )
    style.map(
        "Treeview",
        background=[("selected", COLORS["accent"])],
        foreground=[("selected", "#FFFFFF")],
    )
    style.configure(
        "Treeview.Heading",
        background=COLORS["panel_alt"],
        foreground=COLORS["muted"],
        bordercolor=COLORS["border"],
        font=("Segoe UI", 8, "bold"),
        padding=(6, 6),
        relief="flat",
    )
    style.map("Treeview.Heading", background=[("active", "#1A3150")])
    style.configure(
        "Vertical.TScrollbar",
        background=COLORS["panel_alt"],
        troughcolor=COLORS["panel"],
        bordercolor=COLORS["panel"],
        arrowcolor=COLORS["muted"],
    )


class TextReportDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, title: str, content: str):
        super().__init__(parent)
        self.title(title)
        self.configure(background=COLORS["bg"])
        self.geometry("680x450")
        self.minsize(540, 340)
        self.transient(parent)
        apply_window_icon(self)
        schedule_dark_title_bar(self)

        frame = ttk.Frame(self, padding=12, style="App.TFrame")
        frame.pack(fill="both", expand=True)

        text_frame = ttk.Frame(frame, style="Panel.TFrame")
        text_frame.pack(fill="both", expand=True)
        text = tk.Text(
            text_frame,
            wrap="word",
            font=("Consolas", 9),
            padx=10,
            pady=10,
            background=COLORS["field"],
            foreground=COLORS["text"],
            insertbackground=COLORS["text"],
            selectbackground=COLORS["accent"],
            relief="flat",
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        text.insert("1.0", content)
        text.configure(state="disabled")

        ttk.Button(frame, text="Close", command=self.destroy).pack(side="right", pady=(10, 0))
        self.bind("<Escape>", lambda _event: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)


class ProfileDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        profile: EmailProfile | None = None,
        *,
        initial_category: str | None = None,
    ):
        super().__init__(parent)
        self.profile = profile
        self.result: dict[str, str] | None = None

        self.title("Edit account" if profile else "Add account")
        self.configure(background=COLORS["bg"])
        self.geometry("500x410")
        self.minsize(470, 385)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()
        apply_window_icon(self)
        schedule_dark_title_bar(self)

        if profile is not None:
            resolved_category = profile.category
            resolved_provider = profile.provider
        else:
            resolved_category = normalize_add_category(initial_category or CATEGORY_MAILBOX)
            resolved_provider = default_service_for_category(resolved_category)

        if resolved_category not in CATEGORIES:
            resolved_category = category_for_provider(resolved_provider)
        if resolved_provider not in service_names_for_category(resolved_category):
            resolved_category = CATEGORY_CUSTOM
            resolved_provider = "Custom Website"

        self.name_var = tk.StringVar(value=profile.display_name if profile else "")
        self.account_var = tk.StringVar(value=profile.email_address if profile else "")
        self.category_var = tk.StringVar(value=resolved_category)
        self.provider_var = tk.StringVar(value=resolved_provider)
        self.url_var = tk.StringVar(
            value=profile.start_url if profile else default_url_for(resolved_provider)
        )
        self.account_label_var = tk.StringVar(value=account_label_for(resolved_provider))
        self.account_hint_var = tk.StringVar(value=account_hint_for(resolved_provider))

        panel = ttk.Frame(self, padding=18, style="Panel.TFrame")
        panel.pack(fill="both", expand=True, padx=10, pady=10)
        panel.columnconfigure(1, weight=1)

        ttk.Label(
            panel,
            text="Account profile",
            style="DialogTitle.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))

        ttk.Label(panel, text="Display name", style="Body.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 12), pady=6
        )
        name_entry = ttk.Entry(panel, textvariable=self.name_var)
        name_entry.grid(row=1, column=1, sticky="ew", pady=6)

        ttk.Label(panel, text="Group", style="Body.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 12), pady=6
        )
        category_combo = ttk.Combobox(
            panel,
            textvariable=self.category_var,
            values=CATEGORIES,
            state="readonly",
        )
        category_combo.grid(row=2, column=1, sticky="ew", pady=6)
        category_combo.bind("<<ComboboxSelected>>", self._category_changed)

        ttk.Label(panel, text="Service", style="Body.TLabel").grid(
            row=3, column=0, sticky="w", padx=(0, 12), pady=6
        )
        self.provider_combo = ttk.Combobox(
            panel,
            textvariable=self.provider_var,
            values=service_names_for_category(resolved_category),
            state="readonly",
        )
        self.provider_combo.grid(row=3, column=1, sticky="ew", pady=6)
        self.provider_combo.bind("<<ComboboxSelected>>", self._provider_changed)

        ttk.Label(
            panel,
            textvariable=self.account_label_var,
            style="Body.TLabel",
        ).grid(row=4, column=0, sticky="w", padx=(0, 12), pady=6)
        account_frame = ttk.Frame(panel, style="Panel.TFrame")
        account_frame.grid(row=4, column=1, sticky="ew", pady=6)
        account_frame.columnconfigure(0, weight=1)
        ttk.Entry(account_frame, textvariable=self.account_var).grid(row=0, column=0, sticky="ew")
        ttk.Label(
            account_frame,
            textvariable=self.account_hint_var,
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        ttk.Label(panel, text="Start URL", style="Body.TLabel").grid(
            row=5, column=0, sticky="nw", padx=(0, 12), pady=6
        )
        url_frame = ttk.Frame(panel, style="Panel.TFrame")
        url_frame.grid(row=5, column=1, sticky="ew", pady=6)
        url_frame.columnconfigure(0, weight=1)
        ttk.Entry(url_frame, textvariable=self.url_var).grid(row=0, column=0, sticky="ew")
        ttk.Label(
            url_frame,
            text="HTTPS only. Passwords are entered in the website, never in this app.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        actions = ttk.Frame(panel, style="Panel.TFrame")
        actions.grid(row=6, column=0, columnspan=2, sticky="e", pady=(18, 0))
        ttk.Button(actions, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(actions, text="Save", style="Accent.TButton", command=self._save).pack(
            side="right", padx=(0, 8)
        )

        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Control-Return>", lambda _event: self._save())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.after(80, name_entry.focus_set)

    def _category_changed(self, _event: object | None = None) -> None:
        services = service_names_for_category(self.category_var.get())
        self.provider_combo.configure(values=services)
        if not services:
            return
        self.provider_var.set(services[0])
        self._provider_changed()

    def _provider_changed(self, _event: object | None = None) -> None:
        provider = self.provider_var.get()
        self.account_label_var.set(account_label_for(provider))
        self.account_hint_var.set(account_hint_for(provider))
        default_url = default_url_for(provider)
        if default_url:
            self.url_var.set(default_url)
        else:
            self.url_var.set("")

    def _save(self) -> None:
        display_name = self.name_var.get().strip()
        account = self.account_var.get().strip()
        category = self.category_var.get().strip()
        provider = self.provider_var.get().strip()

        if not display_name:
            messagebox.showerror(APP_NAME, "Enter a display name.", parent=self)
            return
        if len(display_name) > 80:
            messagebox.showerror(APP_NAME, "Display name must be 80 characters or fewer.", parent=self)
            return
        if len(account) > 254:
            messagebox.showerror(APP_NAME, "Account label must be 254 characters or fewer.", parent=self)
            return
        if category not in CATEGORIES:
            messagebox.showerror(APP_NAME, "Choose a valid group.", parent=self)
            return
        if provider not in service_names_for_category(category):
            messagebox.showerror(APP_NAME, "Choose a valid service.", parent=self)
            return

        try:
            start_url = validate_start_url(self.url_var.get())
        except ValueError as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return

        self.result = {
            "display_name": display_name,
            "email_address": account,
            "provider": provider,
            "category": category,
            "start_url": start_url,
        }
        self.destroy()


class EmailProfileBrowserApp:
    """Compact launcher UI retained under its historical class name."""

    def __init__(self, root: tk.Tk, database: Database, logger: logging.Logger):
        self.root = root
        self.database = database
        self.logger = logger
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="BrowserWorker")
        self.browser = BrowserManager(logger=logger, on_exit=self._browser_exit_callback)
        self._busy = False
        self._closing = False
        self._profiles: list[EmailProfile] = []
        self._active_category = CATEGORY_ALL

        assert_portable_root_writable()
        self._configure_window()
        self._build_ui()
        self._load_profiles()
        self.root.protocol("WM_DELETE_WINDOW", self._request_exit)

        self._run_task(
            self.browser.cleanup_orphans,
            success_message=None,
            refresh=False,
            show_busy=False,
        )

    def _configure_window(self) -> None:
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.configure(background=COLORS["bg"])
        self.root.geometry(load_window_geometry())
        self.root.minsize(640, 400)
        self.root.resizable(True, True)
        configure_dark_styles(self.root)
        apply_window_icon(self.root)
        schedule_dark_title_bar(self.root)

    def _build_ui(self) -> None:
        shell = ttk.Frame(self.root, padding=12, style="App.TFrame")
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(1, weight=1)
        shell.rowconfigure(1, weight=1)

        header = ttk.Frame(shell, style="App.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=APP_NAME, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Isolated portable sessions for mail, messaging, social media, and web apps",
            style="HeaderMuted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(1, 0))
        self.active_var = tk.StringVar(value="No active session")
        ttk.Label(header, textvariable=self.active_var, style="HeaderMuted.TLabel").grid(
            row=0, column=1, rowspan=2, sticky="e", padx=(12, 0)
        )

        sidebar = ttk.Frame(shell, padding=(8, 10), style="Panel.TFrame")
        sidebar.grid(row=1, column=0, sticky="ns", padx=(0, 10))
        ttk.Label(sidebar, text="GROUPS", style="Muted.TLabel").pack(anchor="w", padx=7, pady=(0, 6))
        self.category_buttons: dict[str, ttk.Button] = {}
        for category in (CATEGORY_ALL, *CATEGORIES):
            button = ttk.Button(
                sidebar,
                text=category,
                style="Sidebar.TButton",
                command=lambda value=category: self._set_category(value),
                width=19,
            )
            button.pack(fill="x", pady=1)
            self.category_buttons[category] = button

        ttk.Separator(sidebar, orient="horizontal").pack(fill="x", pady=10)
        ttk.Button(sidebar, text="Data folder", command=self._open_data_folder).pack(fill="x", pady=2)
        self.diagnostics_button = ttk.Button(
            sidebar,
            text="Verify portability",
            command=self._show_diagnostics,
        )
        self.diagnostics_button.pack(fill="x", pady=2)

        content = ttk.Frame(shell, padding=10, style="Panel.TFrame")
        content.grid(row=1, column=1, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)

        topbar = ttk.Frame(content, style="Panel.TFrame")
        topbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        topbar.columnconfigure(0, weight=1)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._search_changed)
        self.search_entry = ttk.Entry(topbar, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.search_entry.bind("<FocusIn>", self._search_focus_changed)
        self.search_entry.bind("<FocusOut>", self._search_focus_changed)
        self.search_placeholder = tk.Label(
            topbar,
            text="Search profiles…",
            background=COLORS["field"],
            foreground=COLORS["muted"],
            font=("Segoe UI", 9),
            cursor="xterm",
            borderwidth=0,
            padx=0,
            pady=0,
        )
        self.search_placeholder.place(
            in_=self.search_entry, x=9, rely=0.5, anchor="w"
        )
        self.search_placeholder.bind(
            "<Button-1>", lambda _event: self.search_entry.focus_set()
        )
        self.add_button = ttk.Button(topbar, text="+ Add", command=self._add_profile)
        self.add_button.grid(row=0, column=1)

        tree_frame = ttk.Frame(content, style="Panel.TFrame")
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        columns = ("name", "account", "service", "session")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("name", text="PROFILE")
        self.tree.heading("account", text="ACCOUNT")
        self.tree.heading("service", text="SERVICE")
        self.tree.heading("session", text="SESSION")
        self.tree.column("name", width=170, minwidth=120, stretch=True)
        self.tree.column("account", width=190, minwidth=120, stretch=True)
        self.tree.column("service", width=150, minwidth=110, stretch=True)
        self.tree.column("session", width=110, minwidth=100, stretch=False)

        scrollbar = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=self.tree.yview,
            style="Vertical.TScrollbar",
        )
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.empty_panel = ttk.Frame(tree_frame, style="Panel.TFrame")
        self.empty_panel.grid(row=0, column=0, sticky="nsew")
        self.empty_panel.columnconfigure(0, weight=1)
        self.empty_panel.rowconfigure(0, weight=1)
        empty_content = ttk.Frame(self.empty_panel, style="Panel.TFrame")
        empty_content.grid(row=0, column=0)
        self.empty_title_var = tk.StringVar(value="No profiles yet")
        self.empty_hint_var = tk.StringVar(
            value="Click + Add to create your first portable profile."
        )
        ttk.Label(
            empty_content,
            textvariable=self.empty_title_var,
            style="EmptyTitle.TLabel",
        ).pack()
        ttk.Label(
            empty_content,
            textvariable=self.empty_hint_var,
            style="EmptyHint.TLabel",
        ).pack(pady=(5, 0))
        self.empty_panel.grid_remove()

        self.tree.bind("<Double-1>", lambda _event: self._open_selected())
        self.tree.bind("<Return>", lambda _event: self._open_selected())
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._selection_changed())

        self.details_var = tk.StringVar(value="Select a profile")
        ttk.Label(content, textvariable=self.details_var, style="Muted.TLabel").grid(
            row=2, column=0, sticky="w", pady=(7, 0)
        )

        actions = ttk.Frame(content, style="Panel.TFrame")
        actions.grid(row=3, column=0, sticky="ew", pady=(9, 0))
        self.open_button = ttk.Button(
            actions,
            text="Open selected",
            style="Accent.TButton",
            command=self._open_selected,
        )
        self.open_button.pack(side="left")
        self.close_button = ttk.Button(actions, text="Close browser", command=self._close_browser)
        self.close_button.pack(side="left", padx=(7, 0))
        self.edit_button = ttk.Button(actions, text="Edit", command=self._edit_profile)
        self.edit_button.pack(side="right", padx=(7, 0))
        self.delete_button = ttk.Button(
            actions,
            text="Delete",
            style="Danger.TButton",
            command=self._delete_profile,
        )
        self.delete_button.pack(side="right")

        footer = ttk.Frame(shell, style="App.TFrame")
        footer.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        footer.columnconfigure(0, weight=1)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(footer, textvariable=self.status_var, style="Status.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            footer,
            text=f"v{APP_VERSION}  •  portable root: {BASE_DIR.name}",
            style="Status.TLabel",
        ).grid(row=0, column=1, sticky="e", padx=(12, 0))

        self.root.bind("<Control-n>", lambda _event: self._add_profile())
        self.root.bind("<Control-f>", lambda _event: self.search_entry.focus_set())
        self.root.bind("<Delete>", lambda _event: self._delete_profile())
        self._refresh_category_buttons()
        self._update_search_placeholder()
        self._update_controls()

    def _search_changed(self, *_args: object) -> None:
        self._update_search_placeholder()
        self._apply_filter()

    def _search_focus_changed(self, _event: object | None = None) -> None:
        self._update_search_placeholder()

    def _update_search_placeholder(self) -> None:
        if not hasattr(self, "search_placeholder"):
            return
        has_focus = self.root.focus_get() == self.search_entry
        if search_placeholder_visible(self.search_var.get(), has_focus):
            self.search_placeholder.place(
                in_=self.search_entry, x=9, rely=0.5, anchor="w"
            )
            self.search_placeholder.lift()
        else:
            self.search_placeholder.place_forget()

    def _sync_active_status(self) -> None:
        profile_id = self.browser.active_profile_id
        if profile_id is None:
            self.active_var.set("No active session")
            return
        profile = self.database.get_profile(profile_id)
        name = profile.display_name if profile else "Browser"
        self.active_var.set(f"Active: {name}")

    def _set_category(self, category: str) -> None:
        if category not in (CATEGORY_ALL, *CATEGORIES):
            return
        self._active_category = category
        self._refresh_category_buttons()
        self._apply_filter()

    def _refresh_category_buttons(self) -> None:
        counts = {category: 0 for category in CATEGORIES}
        for profile in self._profiles:
            counts[profile.category] = counts.get(profile.category, 0) + 1
        total = len(self._profiles)
        for category, button in self.category_buttons.items():
            count = total if category == CATEGORY_ALL else counts.get(category, 0)
            button.configure(
                text=f"{category}  {count}",
                style="SidebarActive.TButton" if category == self._active_category else "Sidebar.TButton",
            )

    def _load_profiles(self, select_id: str | None = None) -> None:
        self._profiles = self.database.list_profiles()
        self._refresh_category_buttons()
        self._apply_filter(select_id=select_id)

    def _apply_filter(self, select_id: str | None = None) -> None:
        if not hasattr(self, "tree"):
            return
        previous = select_id
        if previous is None:
            selection = self.tree.selection()
            previous = selection[0] if selection else None

        query = self.search_var.get().strip().casefold() if hasattr(self, "search_var") else ""
        visible: list[EmailProfile] = []
        for profile in self._profiles:
            if self._active_category != CATEGORY_ALL and profile.category != self._active_category:
                continue
            haystack = " ".join(
                (
                    profile.display_name,
                    profile.email_address,
                    profile.provider,
                    profile.category,
                )
            ).casefold()
            if query and query not in haystack:
                continue
            visible.append(profile)

        for item in self.tree.get_children():
            self.tree.delete(item)

        for profile in visible:
            self.tree.insert(
                "",
                "end",
                iid=profile.id,
                values=(
                    profile.display_name,
                    profile.email_address or "—",
                    profile.provider,
                    session_status(self.database.profile_data_dir(profile.id)),
                ),
            )

        if visible:
            self.empty_panel.grid_remove()
        else:
            title, hint = empty_state_messages(self._active_category, query)
            self.empty_title_var.set(title)
            self.empty_hint_var.set(hint)
            self.empty_panel.grid()
            self.empty_panel.tkraise()

        if previous and self.tree.exists(previous):
            self.tree.selection_set(previous)
            self.tree.focus(previous)
            self.tree.see(previous)
        elif visible:
            self.tree.selection_set(visible[0].id)
            self.tree.focus(visible[0].id)

        self._selection_changed()
        self._update_controls()

    def _selected_profile(self) -> EmailProfile | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return self.database.get_profile(selection[0])

    def _selection_changed(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            self.details_var.set("No profile selected")
        else:
            self.details_var.set(
                f"{profile.category}  •  {profile.provider}  •  Last opened: "
                f"{format_timestamp(profile.last_opened_at)}"
            )
        self._update_controls()

    def _add_profile(self) -> None:
        if self._busy:
            return
        dialog = ProfileDialog(
            self.root,
            initial_category=normalize_add_category(self._active_category),
        )
        self.root.wait_window(dialog)
        if not dialog.result:
            return
        try:
            profile = self.database.create_profile(**dialog.result)
            self._active_category = profile.category
            self._load_profiles(select_id=profile.id)
            self.status_var.set("Profile added. Open it once and sign in on the website.")
        except Exception as exc:
            self.logger.exception("Could not add profile")
            messagebox.showerror(APP_NAME, f"Could not add profile: {exc}")

    def _edit_profile(self) -> None:
        if self._busy:
            return
        profile = self._selected_profile()
        if profile is None:
            return
        dialog = ProfileDialog(self.root, profile=profile)
        self.root.wait_window(dialog)
        if not dialog.result:
            return
        try:
            self.database.update_profile(profile.id, **dialog.result)
            self._active_category = dialog.result["category"]
            self._load_profiles(select_id=profile.id)
            self.status_var.set("Profile updated.")
        except Exception as exc:
            self.logger.exception("Could not update profile")
            messagebox.showerror(APP_NAME, f"Could not update profile: {exc}")

    def _open_selected(self) -> None:
        profile = self._selected_profile()
        if profile is None or self._busy:
            return
        profile_dir = self.database.profile_data_dir(profile.id)

        def task() -> int:
            pid = self.browser.open_profile(profile, profile_dir)
            self.database.mark_opened(profile.id)
            return pid

        self._run_task(
            task,
            success_message=f"Opened {profile.display_name}. The isolated session stays in data/profiles.",
            refresh=True,
            select_id=profile.id,
        )
        self.active_var.set(f"Opening: {profile.display_name}")

    def _close_browser(self) -> None:
        active_profile_id = self.browser.active_profile_id
        if self._busy or active_profile_id is None:
            return
        active_profile = self.database.get_profile(active_profile_id)
        active_name = active_profile.display_name if active_profile else "browser"
        self.active_var.set(f"Closing: {active_name}")
        self._run_task(
            self.browser.close_current,
            success_message="Browser closed safely. Cookies and local session files were retained.",
            refresh=True,
            select_id=active_profile_id,
        )

    def _delete_profile(self) -> None:
        profile = self._selected_profile()
        if profile is None or self._busy:
            return

        confirmed = messagebox.askyesno(
            "Delete profile",
            (
                f"Delete '{profile.display_name}' and all of its local browser data?\n\n"
                "This removes cookies, cache, history, downloads, and site storage for this profile."
            ),
            icon="warning",
        )
        if not confirmed:
            return

        profile_dir = self.database.profile_data_dir(profile.id)
        download_dir = DOWNLOADS_DIR / profile.id
        crash_dir = CRASH_DIR / profile.id

        def task() -> None:
            if self.browser.active_profile_id == profile.id:
                self.browser.close_current()

            quarantine = TEMP_DIR / f"delete-{profile.id}-{uuid.uuid4().hex}"
            quarantine.mkdir(parents=True, exist_ok=False)
            moved: list[tuple[Path, Path]] = []
            try:
                for source, name in (
                    (profile_dir, "profile"),
                    (download_dir, "downloads"),
                    (crash_dir, "crash"),
                ):
                    if source.exists():
                        target = quarantine / name
                        shutil.move(str(source), str(target))
                        moved.append((target, source))
                self.database.delete_profile_record(profile.id)
            except Exception:
                for target, source in reversed(moved):
                    if target.exists() and not source.exists():
                        source.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(target), str(source))
                raise
            finally:
                shutil.rmtree(quarantine, ignore_errors=True)

        self._run_task(
            task,
            success_message=f"Deleted {profile.display_name} and its portable session data.",
            refresh=True,
        )

    def _show_diagnostics(self) -> None:
        if self._busy:
            return
        report = collect_diagnostics()
        TextReportDialog(self.root, "Portability diagnostics", report_as_text(report))

    def _open_data_folder(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(DATA_DIR)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(DATA_DIR)])
            else:
                subprocess.Popen(["xdg-open", str(DATA_DIR)])
        except Exception as exc:
            self.logger.exception("Could not open data folder")
            messagebox.showerror(APP_NAME, f"Could not open data folder: {exc}")

    def _run_task(
        self,
        function,
        *,
        success_message: str | None,
        refresh: bool,
        select_id: str | None = None,
        show_busy: bool = True,
    ) -> None:
        if self._busy and show_busy:
            return
        if show_busy:
            self._set_busy(True)
            self.status_var.set("Working…")

        future = self.executor.submit(function)

        def completed(done: Future) -> None:
            if self._closing:
                return
            try:
                self.root.after(
                    0,
                    lambda: self._finish_task(
                        done,
                        success_message=success_message,
                        refresh=refresh,
                        select_id=select_id,
                        show_busy=show_busy,
                    ),
                )
            except (RuntimeError, tk.TclError):
                # The Tk interpreter may already be closing; the worker result
                # must not resurrect or crash the launcher during shutdown.
                return

        future.add_done_callback(completed)

    def _finish_task(
        self,
        future: Future,
        *,
        success_message: str | None,
        refresh: bool,
        select_id: str | None,
        show_busy: bool,
    ) -> None:
        if self._closing:
            return
        try:
            future.result()
            self._sync_active_status()
            if refresh:
                self._load_profiles(select_id=select_id)
            if success_message:
                self.status_var.set(success_message)
            elif show_busy:
                self.status_var.set("Ready")
        except Exception as exc:
            self.logger.exception("Background operation failed")
            self.status_var.set("Operation failed.")
            self.active_var.set("No active session")
            messagebox.showerror(APP_NAME, str(exc))
        finally:
            if show_busy:
                self._set_busy(False)
            else:
                self._update_controls()

    def _set_busy(self, value: bool) -> None:
        self._busy = value
        self._update_controls()

    def _update_controls(self) -> None:
        has_selection = bool(self.tree.selection()) if hasattr(self, "tree") else False
        busy_state = "disabled" if self._busy else "normal"
        selected_state = "normal" if has_selection and not self._busy else "disabled"

        if hasattr(self, "open_button"):
            self.open_button.configure(state=selected_state)
            self.add_button.configure(state=busy_state)
            self.edit_button.configure(state=selected_state)
            self.delete_button.configure(state=selected_state)
            self.close_button.configure(
                state="normal"
                if self.browser.active_profile_id is not None and not self._busy
                else "disabled"
            )
            self.diagnostics_button.configure(state=busy_state)

    def _browser_exit_callback(self, profile_id: str, exit_code: int) -> None:
        def update() -> None:
            if self._closing:
                return
            profile = self.database.get_profile(profile_id)
            name = profile.display_name if profile else "Browser"
            self.active_var.set("No active session")
            self.status_var.set(
                f"{name} closed (exit code {exit_code}). Portable session files remain saved."
            )
            self._load_profiles(select_id=profile_id)

        self.root.after(0, update)

    def _request_exit(self) -> None:
        if self._closing:
            return
        self._closing = True
        try:
            if self.root.state() == "normal":
                save_window_geometry(self.root.winfo_geometry())
        except Exception:
            self.logger.exception("Could not save window geometry")

        self.status_var.set("Closing browser and saving session…")
        self._set_busy(True)
        future = self.executor.submit(self.browser.shutdown)

        def finish(done: Future) -> None:
            try:
                done.result()
            except Exception:
                self.logger.exception("Browser shutdown failed during application exit")
            finally:
                self.executor.shutdown(wait=False, cancel_futures=True)
                self.root.after(0, self.root.destroy)

        future.add_done_callback(finish)
