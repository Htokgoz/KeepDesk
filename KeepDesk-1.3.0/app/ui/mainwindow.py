"""Main window: sidebar, search bar and the note board."""

from __future__ import annotations

import logging
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .. import theme
from . import icons
from .editor import NoteEditor
from .widgets import Toast, make_font, wrap_text

log = logging.getLogger("keepdesk.ui")

CARD_WIDTH = 268
GAP = 14
PAD = 24
PAGE = 150


def _fold(text: str) -> str:
    """Case/diacritic tolerant haystack (Turkish dotted & dotless i included)."""
    return (
        (text or "")
        .replace("İ", "i")
        .replace("I", "i")
        .replace("ı", "i")
        .lower()
    )


class NavItem(tk.Frame):
    """Sidebar row with an icon, a label and an optional counter.

    ``command_mode`` decides whether the row opens on a single click (views) or
    only on a double click (labels, which can also be dragged to reorder).
    """

    def __init__(self, master, text: str, icon: str, command=None, count: int = 0,
                 command_mode: str = "single", draggable: bool = False,
                 show_grip: bool = False) -> None:
        super().__init__(master, bg=theme.SIDEBAR, cursor="hand2")
        self._command = command
        self._icon_name = icon
        self._active = False
        self._dragging = False
        self._selected = False
        self.command_mode = command_mode
        self.draggable = draggable

        self._icon = tk.Canvas(self, width=30, height=26, bg=theme.SIDEBAR,
                               highlightthickness=0, bd=0)
        self._icon.pack(side="left", padx=(6, 0))

        self._label = tk.Label(self, text=text, bg=theme.SIDEBAR, fg=theme.TEXT,
                               font=theme.font(theme._SIZE_BASE), anchor="w")
        self._label.pack(side="left", fill="x", expand=True, padx=(2, 6), pady=6)

        self._count = tk.Label(self, text=str(count) if count else "", bg=theme.SIDEBAR,
                               fg=theme.MUTED, font=theme.font(theme._SIZE_SMALL))
        self._count.pack(side="right", padx=(0, 10))

        self._grip = None
        if show_grip:
            self._grip = tk.Canvas(self, width=18, height=26, bg=theme.SIDEBAR,
                                   highlightthickness=0, bd=0, cursor="fleur")
            self._grip.pack(side="right", padx=(0, 6))
            icons.draw(self._grip, "grip", 1, 5, 16, color="#B9B2A2")

        for widget in self.widgets():
            if command_mode == "single":
                widget.bind("<Button-1>", self._click)
            elif command_mode == "double":
                widget.bind("<Double-Button-1>", self._click)
            widget.bind("<Enter>", lambda _e: self._paint("#F1EDE3"))
            widget.bind("<Leave>", lambda _e: self._paint())
            if draggable:
                widget.configure(cursor="hand2")
        self._paint()

    def widgets(self) -> tuple:
        items = (self, self._icon, self._label, self._count)
        if self._grip is not None:
            items = items + (self._grip,)
        return items

    def _click(self, _event=None) -> None:
        if self._command:
            self._command()

    def _paint(self, bg: str | None = None) -> None:
        if bg is None and self._dragging:
            bg = "#E7DFCB"
        elif bg is None and self._selected:
            bg = "#EFE6CE"
        color = bg or (theme.ACCENT_TINT if self._active else theme.SIDEBAR)
        for widget in self.widgets():
            widget.configure(bg=color)
        self._label.configure(
            font=theme.font(theme._SIZE_BASE, "bold" if self._active else "normal"),
            fg=theme.ACCENT_TEXT if self._active else theme.TEXT,
        )
        self._icon.delete("all")
        icons.draw(self._icon, self._icon_name, 7, 4, 17,
                   color=theme.ACCENT_TEXT if self._active else theme.TEXT_SOFT)

    def set_active(self, active: bool) -> None:
        self._active = bool(active)
        self._paint()

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self._paint()

    def set_count(self, count: int) -> None:
        self._count.configure(text=str(count) if count else "")

    def set_dragging(self, dragging: bool) -> None:
        self._dragging = bool(dragging)
        self._paint()


class NoteCard(tk.Frame):
    def __init__(self, master, app, note: dict) -> None:
        bg, border = theme.note_color(note.get("color", "DEFAULT"))
        super().__init__(master, bg=bg, highlightthickness=1, highlightbackground=border,
                         width=CARD_WIDTH, padx=14, pady=12, cursor="hand2")
        self.app = app
        self.note = note
        self._bg = bg
        self._border = border
        self._hover_job = None

        inner_w = CARD_WIDTH - 30

        header = tk.Frame(self, bg=bg)
        header.pack(fill="x")

        title = (note.get("title") or "").strip()
        if title:
            fnt = make_font(theme.font(11, "bold"))
            lines = wrap_text(title, fnt, inner_w - 20, 3)
            tk.Label(header, text="\n".join(lines), bg=bg, fg=theme.TEXT, anchor="w",
                     justify="left", font=theme.font(11, "bold")).pack(
                side="left", fill="x", expand=True)

        if note.get("pinned"):
            pin = tk.Canvas(header, width=16, height=16, bg=bg, highlightthickness=0, bd=0)
            pin.pack(side="right", anchor="n")
            icons.draw(pin, "pin-filled", 0, 0, 15, color=theme.ACCENT_TEXT)

        if note.get("kind") == "list":
            self._list_body(note, bg, inner_w)
        else:
            body = (note.get("text") or "").strip()
            if body:
                fnt = make_font(theme.font(theme._SIZE_BASE))
                text = "\n".join(wrap_text(body, fnt, inner_w, 12))
                tk.Label(self, text=text, bg=bg, fg=theme.TEXT_SOFT, anchor="w",
                         justify="left", font=theme.font(theme._SIZE_BASE)).pack(
                    fill="x", pady=(6, 0))

        labels = note.get("labels") or []
        counter = ""
        if note.get("kind") == "list":
            items = note.get("items") or []
            done = sum(1 for item in items if item.get("checked"))
            if items:
                counter = f"{done}/{len(items)}"
        if counter or labels:
            footer = tk.Frame(self, bg=bg)
            footer.pack(fill="x", pady=(8, 0))
            if counter:
                tk.Label(footer, text=counter, bg=bg, fg="#6C6A62",
                         font=theme.font(8)).pack(side="left", padx=(0, 8))
            for name in labels:
                chip = tk.Label(footer, text=name, bg=self._shade(), fg="#5E5A50",
                                font=theme.font(8), padx=6, pady=1, cursor="hand2")
                chip.pack(side="left", padx=(0, 4))
                # filter by this label instead of opening the note
                chip.bind("<Button-1>", lambda _e, n=name: self._filter_label(n))
                chip.bind("<Enter>", lambda _e, c=chip: c.configure(bg=theme.ACCENT_TINT))
                chip.bind("<Leave>", lambda _e, c=chip: c.configure(bg=self._shade()))

        self._actions = tk.Frame(self, bg=bg)
        for icon, tip, command in (
            ("pin" if not note.get("pinned") else "pin-filled", "Sabitle", self._toggle_pin),
            ("archive", "Arşivle", self._archive),
            ("trash", "Sil", self._trash),
        ):
            icons.IconButton(self._actions, icon, command=command, bg=bg,
                             hover_bg=self._shade(), fg=theme.TEXT_SOFT,
                             size=27, icon_size=15, tooltip=tip).pack(side="left")

        self._bind_tree(self)

    # -- painting helpers ------------------------------------------------
    def _shade(self) -> str:
        raw = self._bg.lstrip("#")
        r, g, b = (int(raw[i:i + 2], 16) for i in (0, 2, 4))
        return "#%02x%02x%02x" % tuple(max(0, int(v * 0.94)) for v in (r, g, b))

    def _list_body(self, note: dict, bg: str, inner_w: int) -> None:
        items = note.get("items") or []
        if not items:
            return
        fnt = make_font(theme.font(theme._SIZE_BASE))
        lines: list[tuple[bool, str]] = []
        for item in items[:7]:
            wrapped = wrap_text(item.get("text") or "—", fnt, inner_w - 24, 2)
            for index, line in enumerate(wrapped):
                lines.append((bool(item.get("checked")), line if index == 0 else "   " + line))
            if len(lines) >= 8:
                break
        row_h = 20
        canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0,
                           height=max(20, len(lines) * row_h), width=inner_w)
        canvas.pack(fill="x", pady=(6, 0))
        for index, (checked, text) in enumerate(lines):
            y = index * row_h + 9
            if checked:
                canvas.create_oval(2, y - 5, 12, y + 5, fill=theme.ACCENT, outline=theme.ACCENT)
                canvas.create_line(4.4, y, 6.6, y + 2.4, 9.8, y - 2.6, fill="#3A2C05",
                                   width=1.4, capstyle="round", joinstyle="round")
            else:
                canvas.create_oval(2, y - 5, 12, y + 5, outline="#9C978C", width=1.3)
            canvas.create_text(20, y, text=text, anchor="w",
                               fill="#8C8A82" if checked else theme.TEXT,
                               font=theme.font(theme._SIZE_BASE))

    def _bind_tree(self, widget) -> None:
        widget.bind("<Enter>", self._enter, add="+")
        widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<ButtonPress-1>", self._press, add="+")
        widget.bind("<B1-Motion>", self._drag_move, add="+")
        widget.bind("<ButtonRelease-1>", self._release, add="+")
        widget.bind("<Button-3>", self._context, add="+")
        for child in widget.winfo_children():
            if child is self._actions:
                continue
            self._bind_tree(child)

    # -- hover ------------------------------------------------------------
    def _enter(self, _event=None) -> None:
        if self._hover_job is not None:
            try:
                self.after_cancel(self._hover_job)
            except tk.TclError:
                pass
            self._hover_job = None
        self._actions.place(relx=1.0, rely=0.0, x=-3, y=3, anchor="ne")
        self._actions.lift()
        self.configure(highlightbackground=theme.BORDER_STRONG)

    def _leave(self, _event=None) -> None:
        if self._hover_job is None:
            self._hover_job = self.after(90, self._maybe_hide)

    def _maybe_hide(self) -> None:
        self._hover_job = None
        if not self._inside():
            self._actions.place_forget()
            self.configure(highlightbackground=self._border)

    def _inside(self) -> bool:
        try:
            widget = self.winfo_containing(*self.winfo_pointerxy())
        except (tk.TclError, KeyError):
            return False
        while widget is not None:
            if widget is self:
                return True
            widget = getattr(widget, "master", None)
        return False

    # -- actions -----------------------------------------------------------
    def _open(self, _event=None) -> None:
        self.app.open_note(self.note["id"])

    def _press(self, event) -> None:
        """Arm the card: a release without movement opens, movement drags."""
        self._press_xy = (event.x_root, event.y_root)
        self._pressed = True
        self._moved = False

    def _drag_move(self, event) -> None:
        if not self._pressed:
            return
        if not self._moved:
            if abs(event.x_root - self._press_xy[0]) < 6 and abs(event.y_root - self._press_xy[1]) < 6:
                return
            self._moved = True
            self.app.begin_card_drag(self)
        self.app.update_card_drag(event.x_root, event.y_root)

    def _release(self, _event=None) -> None:
        was_pressed = getattr(self, "_pressed", False)
        moved = getattr(self, "_moved", False)
        self._pressed = False
        self._moved = False
        if not was_pressed:
            return
        if moved:
            self.app.end_card_drag()
        else:
            self._open()

    def _filter_label(self, name: str) -> str:
        """Label chips filter the board; they must not open or drag the note."""
        try:
            self.app.show_label(name)
        except Exception:  # pragma: no cover - defensive
            log.debug("label filter failed", exc_info=True)
        return "break"

    def _context(self, event) -> None:
        self.app.show_note_menu(self.note, event.x_root, event.y_root)

    def _toggle_pin(self) -> None:
        self.app.service.update(self.note["id"], {"pinned": not self.note.get("pinned")})

    def _archive(self) -> None:
        self.app.service.update(self.note["id"], {"archived": not self.note.get("archived")})

    def _trash(self) -> None:
        if self.note.get("trashed"):
            if not messagebox.askyesno("Kalıcı olarak sil", "Bu not kalıcı olarak silinsin mi?",
                                       parent=self):
                return
            self.app.service.delete_forever(self.note["id"])
        else:
            self.app.service.trash(self.note["id"])


class MainWindow(tk.Frame):
    def __init__(self, master, app, service) -> None:
        super().__init__(master, bg=theme.BG)
        self.app = app
        self.service = service
        self.view = "notes"
        self.label_name: str | None = None
        self._editors: dict[str, NoteEditor] = {}
        self._render_job = None
        self._layout_key = None
        self._limit = PAGE
        self._nav_items: dict[str, NavItem] = {}
        self._label_items: dict[str, NavItem] = {}
        self._selected_label: str | None = None
        self._label_names: tuple[str, ...] = ()
        self._label_order: list[str] = []
        self._drag_name: str | None = None
        self._drag_start_y = 0
        self._drag_moved = False
        self._card_widgets: list[tk.Widget] = []
        self._card_windows: dict[str, int] = {}
        self._card_rects: dict[str, tuple[int, int, int, int]] = {}
        self._card_order: list[str] = []
        self._order_index: dict[str, int] = {}
        self._dragging_card = None
        self._drag_last_xy: tuple[int, int] | None = None
        self._drop_note: str | None = None
        self._drop_after = False
        self._drop_card = None
        self._sync_card_order_from_settings()

        self._build_sidebar()
        self._build_content()
        self.toast = Toast(self)
        # backstop for drags whose mouse grab was lost before the release
        self.bind("<ButtonRelease-1>", self._label_release_anywhere, add="+")
        self.refresh(force=True)

    # -- layout -----------------------------------------------------------
    def _build_sidebar(self) -> None:
        side = tk.Frame(self, bg=theme.SIDEBAR, width=240)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Frame(self, bg=theme.BORDER, width=1).pack(side="left", fill="y")

        brand = tk.Frame(side, bg=theme.SIDEBAR, pady=14)
        brand.pack(fill="x", padx=16)
        logo = tk.Canvas(brand, width=28, height=28, bg=theme.SIDEBAR,
                         highlightthickness=0, bd=0)
        logo.pack(side="left")
        logo.create_rectangle(2, 2, 26, 26, fill=theme.ACCENT, outline="")
        for i, wdt in enumerate((16, 16, 10)):
            logo.create_line(7, 9 + i * 5, 7 + wdt, 9 + i * 5, fill=theme.ACCENT_TEXT,
                             width=2, capstyle="round")
        tk.Label(brand, text="KeepDesk", bg=theme.SIDEBAR, fg=theme.TEXT,
                 font=theme.font(14, "bold")).pack(side="left", padx=(10, 0))

        nav = tk.Frame(side, bg=theme.SIDEBAR, padx=8)
        nav.pack(fill="x", pady=(6, 0))
        for key, text, icon in (
            ("notes", "Notlar", "notes"),
            ("archive", "Arşiv", "archive"),
            ("trash", "Çöp kutusu", "trash"),
        ):
            item = NavItem(nav, text, icon, command=lambda k=key: self.set_view(k))
            item.pack(fill="x")
            self._nav_items[key] = item

        tk.Frame(side, bg=theme.BORDER, height=1).pack(fill="x", padx=16, pady=12)

        header = tk.Frame(side, bg=theme.SIDEBAR)
        header.pack(fill="x", padx=16)
        tk.Label(header, text="ETİKETLER", bg=theme.SIDEBAR, fg=theme.FAINT,
                 font=theme.font(8, "bold")).pack(side="left")
        icons.IconButton(header, "plus", command=self._create_label, bg=theme.SIDEBAR,
                         hover_bg="#F1EDE3", fg=theme.TEXT_SOFT, size=22, icon_size=14,
                         tooltip="Etiket ekle").pack(side="right")

        holder = tk.Frame(side, bg=theme.SIDEBAR)
        holder.pack(fill="both", expand=True)
        tk.Label(holder, text="çift tık: aç  ·  sürükle: sırala", bg=theme.SIDEBAR,
                 fg=theme.FAINT, font=theme.font(7), anchor="w").pack(
            fill="x", padx=18, pady=(0, 2))
        self._labels_host = tk.Frame(holder, bg=theme.SIDEBAR, padx=8)
        self._labels_host.pack(fill="x", pady=(0, 0))

        bottom = tk.Frame(side, bg=theme.SIDEBAR)
        bottom.pack(side="bottom", fill="x", pady=(0, 12))

        self._status = tk.Label(bottom, text="", bg=theme.SIDEBAR, fg=theme.MUTED,
                                font=theme.font(8), anchor="w")
        self._status.pack(fill="x", padx=18, pady=(0, 8))

        account = tk.Frame(bottom, bg=theme.SIDEBAR, cursor="hand2")
        account.pack(fill="x", padx=12)
        self._avatar = tk.Canvas(account, width=30, height=30, bg=theme.SIDEBAR,
                                 highlightthickness=0, bd=0)
        self._avatar.pack(side="left")
        self._account_label = tk.Label(account, text="", bg=theme.SIDEBAR, fg=theme.TEXT_SOFT,
                                       font=theme.font(8), anchor="w")
        self._account_label.pack(side="left", fill="x", expand=True, padx=(8, 0))
        icons.IconButton(account, "logout", command=self._logout, bg=theme.SIDEBAR,
                         hover_bg="#F1EDE3", fg=theme.MUTED, size=28, icon_size=16,
                         tooltip="Çıkış yap").pack(side="right")
        for widget in (account, self._account_label, self._avatar):
            widget.bind("<Button-1>", lambda _e: self._account_menu())

    def _build_content(self) -> None:
        from .widgets import SearchBox

        wrap = tk.Frame(self, bg=theme.BG)
        wrap.pack(side="left", fill="both", expand=True)

        top = tk.Frame(wrap, bg=theme.BG, pady=12, padx=20)
        top.pack(fill="x")

        self.search = SearchBox(top, placeholder="Notlarda ara",
                                on_change=lambda _v: self.refresh())
        self.search.pack(side="left", fill="x", expand=True)

        self._sync_label = tk.Label(top, text="", bg=theme.BG, fg=theme.MUTED,
                                    font=theme.font(8))
        self._sync_label.pack(side="left", padx=14)

        ttk.Button(top, text="＋  Yeni not", style="Accent.TButton",
                   command=self.new_note).pack(side="right")

        self._board_host = tk.Frame(wrap, bg=theme.BG)
        self._board_host.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(self._board_host, bg=theme.BG, highlightthickness=0, bd=0)
        self._scrollbar = ttk.Scrollbar(self._board_host, orient="vertical",
                                        command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._scrollbar.pack(side="right", fill="y", padx=(0, 4), pady=(0, 4))
        self._canvas.bind("<Configure>", self._on_resize)
        self._canvas.bind("<MouseWheel>", self._on_wheel)
        self._canvas.bind("<Enter>", lambda _e: self._canvas.bind_all("<MouseWheel>", self._on_wheel))
        self._canvas.bind("<Leave>", lambda _e: self._canvas.unbind_all("<MouseWheel>"))

        self._empty = tk.Frame(self._board_host, bg=theme.BG)
        icon = tk.Canvas(self._empty, width=64, height=64, bg=theme.BG,
                         highlightthickness=0, bd=0)
        icon.pack(pady=(0, 10))
        icons.draw(icon, "note", 8, 8, 48, color="#CFCABD", width=2.0)
        tk.Label(self._empty, text="Burada henüz bir şey yok", bg=theme.BG, fg=theme.MUTED,
                 font=theme.font(theme._SIZE_H1)).pack()
        self._empty_hint = tk.Label(self._empty, text="", bg=theme.BG, fg=theme.FAINT,
                                    font=theme.font(theme._SIZE_BASE))
        self._empty_hint.pack(pady=(4, 0))

    # -- view switching ----------------------------------------------------
    def set_view(self, view: str, label_name: str | None = None) -> None:
        self.view = view
        self.label_name = label_name
        self._limit = PAGE
        self._layout_key = None
        for key, item in self._nav_items.items():
            item.set_active(key == view)
        for name, item in self._label_items.items():
            item.set_active(label_name is not None and name == label_name)
        self._canvas.yview_moveto(0)
        self.refresh(force=True)

    # -- data --------------------------------------------------------------
    def _visible_notes(self) -> list[dict]:
        query = _fold(self.search.value())
        notes = []
        for note in self.service.cached_notes():
            if self.view == "notes" and (note["archived"] or note["trashed"]):
                continue
            if self.view == "archive" and (not note["archived"] or note["trashed"]):
                continue
            if self.view == "trash" and not note["trashed"]:
                continue
            if self.view == "label":
                if self.label_name not in (note.get("labels") or []):
                    continue
                if note["archived"] or note["trashed"]:
                    continue
            if query:
                haystack = _fold(" ".join(
                    [note.get("title", ""), note.get("text", "")]
                    + [item.get("text", "") for item in note.get("items") or []]
                    + list(note.get("labels") or [])
                ))
                if query not in haystack:
                    continue
            notes.append(note)

        def sort_key(note: dict):
            pinned = 1 if (note.get("pinned") and self.view in ("notes", "label")) else 0
            rank = self._order_index.get(note["id"])
            if rank is None:
                rank = len(self._card_order) + 100000
            return (-pinned, rank, -note.get("updated", 0.0))

        notes.sort(key=sort_key)
        return notes

    # -- manual card order -------------------------------------------------
    def _sync_card_order_from_settings(self) -> None:
        settings = self._settings()
        saved = settings.get("card_order") if settings is not None else None
        self._card_order = [str(item) for item in saved] if isinstance(saved, list) else []
        self._rebuild_order_index()

    def _rebuild_order_index(self) -> None:
        self._order_index = {note_id: index for index, note_id in enumerate(self._card_order)}

    def _save_card_order(self) -> None:
        settings = self._settings()
        if settings is not None:
            settings.set("card_order", list(self._card_order), save=True)

    # -- card dragging -----------------------------------------------------
    def begin_card_drag(self, card) -> None:
        self._dragging_card = card
        self._drag_last_xy = None
        self._drop_note = None
        self._drop_card = None
        self._canvas.configure(cursor="fleur")
        try:
            card.configure(highlightbackground=theme.ACCENT, highlightthickness=2)
        except tk.TclError:
            pass

    def update_card_drag(self, x_root: int, y_root: int) -> None:
        self._drag_last_xy = (x_root, y_root)
        target = self._card_at(x_root, y_root)
        note_id, after = (target or (None, False))
        dragged_id = self._dragging_card.note["id"] if self._dragging_card else None
        if note_id == dragged_id:
            note_id, after = None, False
        if (note_id, after) == (self._drop_note, self._drop_after):
            return
        self._drop_note, self._drop_after = note_id, after
        self._paint_drop_target()

    def _card_at(self, x_root: int, y_root: int) -> tuple[str, bool] | None:
        try:
            cx = x_root - self._canvas.winfo_rootx() + int(self._canvas.canvasx(0))
            cy = y_root - self._canvas.winfo_rooty() + int(self._canvas.canvasy(0))
        except tk.TclError:
            return None
        for note_id, (x, y, width, height) in self._card_rects.items():
            if x <= cx <= x + width and y <= cy <= y + height:
                return note_id, cx > x + width / 2
        return None

    def _paint_drop_target(self) -> None:
        for note_id, card in list(self._card_map().items()):
            try:
                if note_id == self._drop_note:
                    color = theme.GREEN if not self._drop_after else "#B26A00"
                    card.configure(highlightbackground=color, highlightthickness=2)
                elif card is not self._dragging_card:
                    card.configure(highlightthickness=1,
                                   highlightbackground=theme.note_color(
                                       card.note.get("color", "DEFAULT"))[1])
            except tk.TclError:
                pass

    def _card_map(self) -> dict[str, tk.Widget]:
        return {card.note["id"]: card for card in self._card_widgets
                if hasattr(card, "note")}

    def end_card_drag(self) -> None:
        card = self._dragging_card
        self._dragging_card = None
        try:
            self._canvas.configure(cursor="")
        except tk.TclError:
            pass
        if card is None:
            return
        dragged_id = card.note["id"]
        self._paint_drop_target()
        moved = False
        if self._drop_note and self._drop_note != dragged_id:
            order = [note["id"] for note in self._visible_notes()]
            order = [note_id for note_id in order if note_id != dragged_id]
            if self._drop_note in order:
                index = order.index(self._drop_note) + (1 if self._drop_after else 0)
                order.insert(index, dragged_id)
                extra = [nid for nid in self._card_order if nid not in order]
                self._card_order = order + extra
                self._rebuild_order_index()
                self._save_card_order()
                moved = True
        elif self._drop_note is None:
            # dropped on empty space -> send to the end, unless it never really
            # left its own card
            hit = self._card_at(*self._drag_last_xy) if self._drag_last_xy else None
            if not hit or hit[0] != dragged_id:
                order = [note["id"] for note in self._visible_notes()
                         if note["id"] != dragged_id]
                order.append(dragged_id)
                extra = [nid for nid in self._card_order if nid not in order]
                self._card_order = order + extra
                self._rebuild_order_index()
                self._save_card_order()
                moved = True
        self._drop_note = None
        self._drop_card = None
        self._layout_key = None
        if moved:
            self.refresh(force=True)
            try:
                self.toast.show("Kart sırası kaydedildi", timeout=1800)
            except Exception:
                pass

    def refresh(self, force: bool = False) -> None:
        if self._render_job is not None:
            try:
                self.after_cancel(self._render_job)
            except tk.TclError:
                pass
        self._render_job = self.after(50 if force else 130, self._render)

    def _render(self) -> None:
        self._render_job = None
        if not self.winfo_exists():
            return
        notes = self._visible_notes()
        width = max(320, self._canvas.winfo_width())
        columns = max(1, (width - 2 * PAD + GAP) // (CARD_WIDTH + GAP))
        key = (columns,
               tuple((n["id"], n.get("updated", 0.0)) for n in notes[: self._limit]),
               self.view, self.label_name, self.search.value())
        if key == self._layout_key and self._card_widgets:
            self._update_status()
            return
        self._layout_key = key
        self._paint_board(notes, width, columns)
        self._update_counts()

    def _clear_board(self) -> None:
        for widget in self._card_widgets:
            try:
                widget.destroy()
            except tk.TclError:
                pass
        self._card_widgets = []
        self._canvas.delete("all")

    def _paint_board(self, notes: list[dict], width: int, columns: int) -> None:
        self._clear_board()
        if not notes:
            self._empty.place(relx=0.5, rely=0.32, anchor="center")
            hint = {
                "notes": "Yeni bir not oluşturmak için ＋ Yeni not düğmesini kullanın.",
                "archive": "Arşivlediğiniz notlar burada görünür.",
                "trash": "Silinen notlar 30 gün boyunca burada bekler.",
                "label": "Bu etikete bağlı not yok.",
            }.get(self.view, "")
            if self.search.value().strip():
                hint = "Aramanızla eşleşen not bulunamadı."
            self._empty_hint.configure(text=hint)
            self._canvas.configure(
                scrollregion=(0, 0, width, max(520, self._canvas.winfo_height())))
            return
        self._empty.place_forget()

        self._card_windows = {}
        self._card_rects = {}
        col_heights = [0] * columns
        for note in notes[: self._limit]:
            card = NoteCard(self._canvas, self.app, note)
            self._card_widgets.append(card)

        self._canvas.update_idletasks()
        for card in list(self._card_widgets):
            if not isinstance(card, NoteCard):
                continue
            height = max(56, card.winfo_reqheight())
            column = col_heights.index(min(col_heights))
            x = PAD + column * (CARD_WIDTH + GAP)
            y = PAD + col_heights[column]
            window_id = self._canvas.create_window(x, y, window=card, anchor="nw",
                                                   width=CARD_WIDTH, height=height)
            note_id = card.note["id"]
            self._card_windows[note_id] = window_id
            self._card_rects[note_id] = (x, y, CARD_WIDTH, height)
            col_heights[column] += height + GAP

        total = max(col_heights) + PAD
        if len(notes) > self._limit:
            more = tk.Button(
                self._canvas, text=f"Daha fazla göster  ({len(notes) - self._limit})",
                bd=0, bg=theme.SURFACE, fg=theme.TEXT_SOFT, relief="flat",
                font=theme.font(theme._SIZE_BASE), cursor="hand2",
                highlightthickness=1, highlightbackground=theme.BORDER,
                command=self._show_more,
            )
            self._canvas.create_window(PAD, total, window=more, anchor="nw",
                                       width=230, height=38)
            self._card_widgets.append(more)
            total += 38 + PAD
        self._canvas.configure(scrollregion=(0, 0, width, total))

    def _show_more(self) -> None:
        self._limit += PAGE
        self._layout_key = None
        self._render()

    def _update_counts(self) -> None:
        everything = self.service.cached_notes()
        self._nav_items["notes"].set_count(
            sum(1 for n in everything if not n["archived"] and not n["trashed"]))
        self._nav_items["archive"].set_count(
            sum(1 for n in everything if n["archived"] and not n["trashed"]))
        self._nav_items["trash"].set_count(sum(1 for n in everything if n["trashed"]))
        self._sync_labels()
        email = self.service.email or ""
        if self._account_label.cget("text") != email:
            self._account_label.configure(text=email)
            self._draw_avatar(email)
        self._update_status()

    def _sync_labels(self) -> None:
        labels = self._ordered_labels(self.service.cached_labels())
        names = tuple(label["name"] for label in labels)
        if names == self._label_names:
            for name, item in self._label_items.items():
                item.set_active(self.view == "label" and self.label_name == name)
            return
        self._label_names = names
        self._label_order = list(names)
        for child in self._labels_host.winfo_children():
            child.destroy()
        self._label_items = {}
        for label in labels:
            name = label["name"]
            item = NavItem(self._labels_host, name, "tag",
                           command=lambda n=name: self.set_view("label", n),
                           command_mode="double", draggable=True, show_grip=True)
            item.pack(fill="x")
            item.set_active(self.view == "label" and self.label_name == name)
            item.set_selected(self._selected_label == name)
            for widget in item.widgets():
                widget.bind("<Button-3>", lambda e, l=label: self._label_menu(l, e), add="+")
                widget.bind("<ButtonPress-1>",
                            lambda e, n=name: self._label_drag_start(n, e), add="+")
                widget.bind("<B1-Motion>", self._label_drag_motion, add="+")
                widget.bind("<ButtonRelease-1>",
                            lambda e, n=name: self._label_drag_end(n, e), add="+")
                widget.bind("<Double-Button-1>",
                            lambda e, n=name: self._log_label("double", n), add="+")
            self._label_items[name] = item

    # -- label ordering (drag & drop) -------------------------------------
    def _settings(self):
        return getattr(self.app, "settings", None)

    def _ordered_labels(self, labels: list[dict]) -> list[dict]:
        settings = self._settings()
        saved = settings.get("label_order") if settings is not None else None
        saved = saved if isinstance(saved, list) else []
        rank = {name: index for index, name in enumerate(saved) if isinstance(name, str)}
        return sorted(labels,
                      key=lambda item: (rank.get(item["name"], len(rank)),
                                        item["name"].casefold()))

    def _log_label(self, kind: str, name: str) -> None:
        log.info("label %s: %s (view=%s)", kind, name, self.view)

    def _select_label(self, name: str) -> None:
        self._selected_label = name
        for other, item in self._label_items.items():
            item.set_selected(other == name)

    def _label_drag_start(self, name: str, event) -> None:
        self._log_label("press", name)
        self._drag_name = name
        self._drag_start_y = event.y_root
        self._drag_moved = False
        self._select_label(name)

    def _label_drag_motion(self, event) -> None:
        name = self._drag_name
        if not name or name not in self._label_items:
            return
        if not self._drag_moved:
            if abs(event.y_root - self._drag_start_y) < 5:
                return
            self._drag_moved = True
            self._label_items[name].set_dragging(True)
        target = self._label_drop_index(event.y_root, name)
        current = self._label_order.index(name) if name in self._label_order else None
        if current is None or target == current:
            return
        self._label_order.pop(current)
        self._label_order.insert(target, name)
        # keep the change-detection tuple in sync, otherwise the next refresh
        # would think the label set changed and rebuild (destroying the row we
        # are dragging)
        self._label_names = tuple(self._label_order)
        self._move_label_widget(name, target)

    def _label_drop_index(self, y_root: int, name: str) -> int:
        others = [item for item in self._label_order if item != name]
        y = y_root - self._labels_host.winfo_rooty()
        index = 0
        for position, other in enumerate(others):
            item = self._label_items.get(other)
            if item is None:
                continue
            if y > item.winfo_y() + item.winfo_height() / 2:
                index = position + 1
        return max(0, min(index, len(others)))

    def _move_label_widget(self, name: str, index: int) -> None:
        """Move one row without re-packing everything.

        ``pack_forget`` on the pressed row would drop Tk's implicit mouse grab,
        so the drop would never reach us and the order would not be saved.
        """
        item = self._label_items.get(name)
        if item is None:
            return
        others = [other for other in self._label_order if other != name]
        if not others:
            return
        if index <= 0:
            item.pack_configure(before=self._label_items[others[0]])
        elif index >= len(others):
            item.pack_configure(after=self._label_items[others[-1]])
        else:
            item.pack_configure(before=self._label_items[others[index]])

    def _repack_labels(self) -> None:
        for name in self._label_order:
            item = self._label_items.get(name)
            if item is not None:
                item.pack_forget()
        for name in self._label_order:
            item = self._label_items.get(name)
            if item is not None:
                item.pack(fill="x")

    def _label_drag_end(self, name: str, event) -> None:
        if self._drag_moved:
            self._log_label("drop", name)
            item = self._label_items.get(name)
            if item is not None:
                item.set_dragging(False)
            self._save_label_order()
        else:
            self._log_label("click", name)
            self._show_label_hint()
        self._drag_name = None
        self._drag_moved = False
        self.configure(cursor="")

    def _show_label_hint(self) -> None:
        if getattr(self, "_label_hint_shown", False):
            return
        self._label_hint_shown = True
        try:
            self.toast.show("Etiketi açmak için çift tıkla · sıralamak için tutup sürükle", timeout=4200)
        except Exception:
            pass

    def _label_release_anywhere(self, _event=None) -> None:
        """Safety net: finish a drag even if the widget lost the mouse grab."""
        if self._drag_name:
            self._label_drag_end(self._drag_name, _event)
        if self._dragging_card is not None:
            self.end_card_drag()

    def _save_label_order(self) -> None:
        self._label_names = tuple(self._label_order)
        settings = self._settings()
        if settings is not None:
            settings.set("label_order", list(self._label_order), save=True)

    def _draw_avatar(self, email: str) -> None:
        self._avatar.delete("all")
        self._avatar.create_oval(1, 1, 29, 29, fill=theme.ACCENT_TINT, outline="")
        self._avatar.create_text(15, 15, text=(email[:1] or "K").upper(),
                                 fill=theme.ACCENT_TEXT, font=theme.font(10, "bold"))

    def _update_status(self) -> None:
        status = self.service.status
        if status == "syncing":
            text, color = "Senkronize ediliyor…", theme.MUTED
        elif status == "ok":
            stamp = time.strftime("%H:%M", time.localtime(self.service.last_sync))
            text, color = f"Senkronize · {stamp}", theme.GREEN
        elif status == "auth":
            text, color = "Oturum yenilenmeli", theme.RED
        elif status == "error":
            text, color = "Bağlantı hatası · yeniden denenecek", theme.RED
        else:
            text, color = "Çevrimdışı", theme.MUTED
        self._status.configure(text="●  " + text, fg=color)
        self._sync_label.configure(text="" if status in ("ok", "syncing") else text)

    # -- actions ------------------------------------------------------------
    def new_note(self, kind: str = "note") -> None:
        self.service.create_note(kind, "", "",
                                 lambda result, error: self._created(result, error))

    def _created(self, result, error) -> None:
        if error is not None:
            self.toast.show(f"Not oluşturulamadı: {error}", "error")
            return
        if isinstance(result, dict) and result.get("id"):
            self.open_note(result["id"], fresh=result)

    def open_note(self, note_id: str, fresh: dict | None = None) -> None:
        editor = self._editors.get(note_id)
        if editor is not None and editor.winfo_exists():
            editor.lift()
            editor.focus_force()
            return
        note = fresh or self.service.note(note_id)
        if note is None:
            self.toast.show("Not bulunamadı.", "error")
            return
        editor = NoteEditor(self.winfo_toplevel(), self.service, note,
                            on_closed=lambda: self._editors.pop(note_id, None))
        self._editors[note_id] = editor

    def show_note_menu(self, note: dict, x: int, y: int) -> None:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="Sabitlemeyi kaldır" if note.get("pinned") else "Sabitle",
            command=lambda: self.service.update(note["id"], {"pinned": not note.get("pinned")}),
        )
        colors = tk.Menu(menu, tearoff=0)
        for value in theme.NOTE_COLOR_ORDER:
            colors.add_command(label=theme.COLOR_LABELS[value],
                               command=lambda v=value: self.service.update(note["id"], {"color": v}))
        menu.add_cascade(label="Renk", menu=colors)
        if note.get("trashed"):
            menu.add_command(label="Geri yükle", command=lambda: self.service.untrash(note["id"]))
            menu.add_command(label="Kalıcı olarak sil", command=lambda: self._confirm_delete(note))
        else:
            menu.add_command(
                label="Arşivden çıkar" if note.get("archived") else "Arşivle",
                command=lambda: self.service.update(note["id"],
                                                    {"archived": not note.get("archived")}))
            menu.add_command(label="Sil", command=lambda: self.service.trash(note["id"]))
        menu.add_separator()
        menu.add_command(label="Aç", command=lambda: self.open_note(note["id"]))
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _confirm_delete(self, note: dict) -> None:
        if messagebox.askyesno("Kalıcı olarak sil", "Bu not kalıcı olarak silinsin mi?",
                               parent=self):
            self.service.delete_forever(note["id"])

    def _label_menu(self, label: dict, event) -> None:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Etiketi aç",
                         command=lambda: self.set_view("label", label["name"]))
        menu.add_separator()
        menu.add_command(label="Yeniden adlandır", command=lambda: self._rename_label(label))
        menu.add_command(label="Sil", command=lambda: self._delete_label(label))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _rename_label(self, label: dict) -> None:
        name = simpledialog.askstring("Etiketi yeniden adlandır", "Yeni ad:",
                                      initialvalue=label["name"], parent=self)
        if name and name.strip() and name.strip() != label["name"]:
            self.service.rename_label(label["id"], name.strip())
            if label["name"] in self._label_order:
                position = self._label_order.index(label["name"])
                self._label_order[position] = name.strip()
                self._save_label_order()
            if self.view == "label" and self.label_name == label["name"]:
                self.label_name = name.strip()
            self.after(400, lambda: self.refresh(force=True))

    def _delete_label(self, label: dict) -> None:
        if messagebox.askyesno(
            "Etiketi sil",
            f"'{label['name']}' etiketi silinsin mi?\nNotlar silinmez, yalnızca etiket kaldırılır.",
            parent=self,
        ):
            self.service.delete_label(label["id"])
            if label["name"] in self._label_order:
                self._label_order.remove(label["name"])
                self._save_label_order()
            if self.view == "label" and self.label_name == label["name"]:
                self.set_view("notes")

    def _create_label(self) -> None:
        name = simpledialog.askstring("Yeni etiket", "Etiket adı:", parent=self)
        if name and name.strip():
            self.service.create_label(name.strip())
            self.after(400, lambda: self.refresh(force=True))

    def _account_menu(self) -> None:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=self.service.email or "Hesap", state="disabled")
        menu.add_separator()
        menu.add_command(label="Şimdi senkronize et",
                         command=lambda: self.service.request_sync(0.0))
        menu.add_command(label="Çıkış yap", command=self._logout)
        try:
            menu.tk_popup(self._avatar.winfo_rootx(), self._avatar.winfo_rooty() - 84)
        finally:
            menu.grab_release()

    def _logout(self) -> None:
        if messagebox.askyesno(
            "Çıkış yap",
            "Bu cihazdaki oturum kapatılsın mı?\nNotlarınız Google Keep'te kalır.",
            parent=self,
        ):
            self.app.logout()

    # -- events -------------------------------------------------------------
    def close_editors(self) -> None:
        for editor in list(self._editors.values()):
            try:
                editor.destroy()
            except tk.TclError:
                pass
        self._editors.clear()

    def _on_resize(self, _event) -> None:
        if self._render_job is not None:
            try:
                self.after_cancel(self._render_job)
            except tk.TclError:
                pass
        self._render_job = self.after(140, self._render)

    def _on_wheel(self, event) -> None:
        steps = int(-event.delta / 120) * 3
        self._canvas.yview_scroll(steps or (-3 if event.delta > 0 else 3), "units")
