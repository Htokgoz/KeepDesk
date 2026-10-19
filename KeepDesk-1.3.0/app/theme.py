"""Visual language: palette, fonts and ttk styling."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# Surfaces ---------------------------------------------------------------
BG = "#F4F3EF"
SIDEBAR = "#FCFBF7"
SURFACE = "#FFFFFF"
BORDER = "#E5E2DA"
BORDER_STRONG = "#D6D2C7"

# Text -------------------------------------------------------------------
TEXT = "#1F2023"
TEXT_SOFT = "#4A4D52"
MUTED = "#73767C"
FAINT = "#9CA0A6"
INVERSE = "#FFFFFF"

# Brand ------------------------------------------------------------------
ACCENT = "#F7B733"
ACCENT_HOVER = "#F2AB1C"
ACCENT_TINT = "#FDF1D6"
ACCENT_TEXT = "#3A2C05"

RED = "#C5372C"
RED_TINT = "#FBE9E7"
GREEN = "#2E7D4F"
GREEN_TINT = "#E8F5EC"

SHADOW = "#E9E6DE"

# Note colours (Google Keep palette) -------------------------------------
NOTE_COLORS: dict[str, tuple[str, str]] = {
    # value: (background, border)
    "DEFAULT": ("#FFFFFF", "#E8E5DC"),
    "RED": ("#F6B3AC", "#E9A29A"),
    "ORANGE": ("#F8C471", "#EBB55B"),
    "YELLOW": ("#FFEE9B", "#EFDC82"),
    "GREEN": ("#C9F0A3", "#B4DE8B"),
    "TEAL": ("#A9EFE2", "#8FDCCE"),
    "BLUE": ("#BFE6F7", "#A5D5EA"),
    "CERULEAN": ("#B4CBF7", "#9DB6E8"),
    "PURPLE": ("#DCC0F7", "#C9A8EB"),
    "PINK": ("#F8C6DF", "#E8AECB"),
    "BROWN": ("#E3C6A4", "#D2B28C"),
    "GRAY": ("#E4E4E0", "#D2D2CD"),
}

NOTE_COLOR_ORDER = [
    "DEFAULT",
    "RED",
    "ORANGE",
    "YELLOW",
    "GREEN",
    "TEAL",
    "BLUE",
    "CERULEAN",
    "PURPLE",
    "PINK",
    "BROWN",
    "GRAY",
]

COLOR_LABELS = {
    "DEFAULT": "Varsayılan",
    "RED": "Kırmızı",
    "ORANGE": "Turuncu",
    "YELLOW": "Sarı",
    "GREEN": "Yeşil",
    "TEAL": "Turkuaz",
    "BLUE": "Mavi",
    "CERULEAN": "Gök mavisi",
    "PURPLE": "Mor",
    "PINK": "Pembe",
    "BROWN": "Kahverengi",
    "GRAY": "Gri",
}


def note_color(value: str) -> tuple[str, str]:
    return NOTE_COLORS.get(value or "DEFAULT", NOTE_COLORS["DEFAULT"])


# Fonts ------------------------------------------------------------------
_FAMILY = "Segoe UI"
_SEMIBOLD = "Segoe UI Semibold"

_SIZE_BASE = 10
_SIZE_SMALL = 9
_SIZE_TITLE = 22
_SIZE_H1 = 13
_SIZE_H2 = 11


def font(size: int = _SIZE_BASE, weight: str = "normal", family: str | None = None) -> tuple:
    fam = family or (_SEMIBOLD if weight in ("bold", "semibold") else _FAMILY)
    return (fam, size, "normal")


def apply_theme(root: tk.Misc) -> ttk.Style:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    root.option_add("*Font", font(_SIZE_BASE))
    root.option_add("*TearOff", 0)
    root.option_add("*Menu.font", font(_SIZE_BASE))
    root.option_add("*Menu.background", SURFACE)
    root.option_add("*Menu.foreground", TEXT)
    root.option_add("*Menu.activeBackground", ACCENT_TINT)
    root.option_add("*Menu.activeForeground", TEXT)
    root.option_add("*Menu.borderWidth", 1)

    style.configure(".", background=BG, foreground=TEXT, font=font(_SIZE_BASE), borderwidth=0)
    style.configure("TFrame", background=BG)
    style.configure("Surface.TFrame", background=SURFACE)
    style.configure("Sidebar.TFrame", background=SIDEBAR)
    style.configure("TLabel", background=BG, foreground=TEXT, font=font(_SIZE_BASE))
    style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=font(_SIZE_SMALL))
    style.configure("H1.TLabel", background=BG, foreground=TEXT, font=font(_SIZE_H1, "bold"))
    style.configure("Card.TLabel", background=SURFACE, foreground=TEXT, font=font(_SIZE_BASE))

    style.configure(
        "TButton",
        background=SURFACE,
        foreground=TEXT,
        borderwidth=1,
        bordercolor=BORDER,
        padding=(12, 7),
        font=font(_SIZE_BASE),
        relief="flat",
        focusthickness=0,
    )
    style.map(
        "TButton",
        background=[("pressed", "#EFEBE2"), ("active", "#F7F4EC")],
        bordercolor=[("active", BORDER_STRONG)],
    )

    style.configure(
        "Accent.TButton",
        background=ACCENT,
        foreground=ACCENT_TEXT,
        bordercolor=ACCENT,
        padding=(14, 8),
        font=font(_SIZE_BASE, "bold"),
    )
    style.map(
        "Accent.TButton",
        background=[("pressed", ACCENT_HOVER), ("active", ACCENT_HOVER)],
        bordercolor=[("active", ACCENT_HOVER)],
    )

    style.configure(
        "Ghost.TButton",
        background=BG,
        foreground=TEXT_SOFT,
        borderwidth=0,
        padding=(8, 6),
    )
    style.map("Ghost.TButton", background=[("active", "#EAE7DE")])

    style.configure(
        "Nav.TButton",
        background=SIDEBAR,
        foreground=TEXT,
        borderwidth=0,
        padding=(10, 8),
        anchor="w",
        font=font(_SIZE_BASE),
    )
    style.map("Nav.TButton", background=[("active", "#F1EDE3")])

    style.configure(
        "NavActive.TButton",
        background=ACCENT_TINT,
        foreground=TEXT,
        borderwidth=0,
        padding=(10, 8),
        anchor="w",
        font=font(_SIZE_BASE, "bold"),
    )
    style.map("NavActive.TButton", background=[("active", ACCENT_TINT)])

    style.configure(
        "TEntry",
        fieldbackground=SURFACE,
        foreground=TEXT,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        insertcolor=TEXT,
        padding=(10, 8),
        relief="flat",
    )
    style.map("TEntry", bordercolor=[("focus", ACCENT)])

    style.configure(
        "Search.TEntry",
        fieldbackground=SURFACE,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        padding=(10, 8),
    )
    style.map("Search.TEntry", bordercolor=[("focus", ACCENT)])

    style.configure("TSeparator", background=BORDER)
    style.configure(
        "Vertical.TScrollbar",
        background="#D9D5CB",
        troughcolor=BG,
        bordercolor=BG,
        arrowcolor=MUTED,
        arrowsize=12,
        width=10,
        relief="flat",
    )
    style.map("Vertical.TScrollbar", background=[("active", "#C4BFB3")])

    style.configure("TCheckbutton", background=BG, foreground=TEXT, focuscolor=BG)
    style.map("TCheckbutton", background=[("active", BG)])

    return style
