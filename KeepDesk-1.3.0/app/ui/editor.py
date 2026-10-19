"""Note / checklist editor window."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

from .. import theme
from ..service import ServiceError
from . import icons
from .widgets import CheckCircle, ScrollFrame, center_on_parent


def _contrast_on(bg: str) -> str:
    """Pick dark or light text for a coloured background."""
    bg = bg.lstrip("#")
    r, g, b = (int(bg[i:i + 2], 16) for i in (0, 2, 4))
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return theme.TEXT if luminance > 0.62 else "#202124"


class LabelPicker(tk.Toplevel):
    """Small popup with a checklist of labels."""

    def __init__(self, master, service, note: dict, on_done) -> None:
        super().__init__(master)
        self.service = service
        self.note = note
        self.on_done = on_done
        self.overrideredirect(True)
        self.configure(bg=theme.BORDER)
        self._vars: dict[str, tk.BooleanVar] = {}

        frame = tk.Frame(self, bg=theme.SURFACE, padx=12, pady=10)
        frame.pack(padx=1, pady=1)
        tk.Label(frame, text="Etiketler", bg=theme.SURFACE, fg=theme.TEXT,
                 font=theme.font(theme._SIZE_SMALL, "bold")).pack(anchor="w", pady=(0, 6))

        selected = {name.casefold() for name in note.get("labels", [])}
        labels = service.cached_labels()
        if not labels:
            tk.Label(frame, text="Henüz etiket yok.", bg=theme.SURFACE, fg=theme.MUTED,
                     font=theme.font(theme._SIZE_SMALL)).pack(anchor="w")
        for label in labels:
            var = tk.BooleanVar(value=label["name"].casefold() in selected)
            self._vars[label["name"]] = var
            cb = ttk.Checkbutton(frame, text=label["name"], variable=var,
                                 command=self._commit)
            cb.pack(anchor="w")

        tk.Frame(frame, bg=theme.BORDER, height=1).pack(fill="x", pady=6)
        row = tk.Frame(frame, bg=theme.SURFACE)
        row.pack(fill="x")
        self.new_var = tk.StringVar()
        entry = ttk.Entry(row, textvariable=self.new_var, width=18)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda _e: self._add_label())
        tk.Button(row, text="+", bd=0, bg=theme.ACCENT_TINT, fg=theme.ACCENT_TEXT,
                  activebackground=theme.ACCENT, relief="flat", cursor="hand2",
                  font=theme.font(theme._SIZE_SMALL, "bold"), width=3,
                  command=self._add_label).pack(side="left", padx=(6, 0))

        tk.Frame(frame, bg=theme.BORDER, height=1).pack(fill="x", pady=6)
        ttk.Button(frame, text="Tamam", command=self._close).pack(anchor="e")

        self.bind("<Escape>", lambda _e: self._close())
        self.update_idletasks()
        x = master.winfo_rootx()
        y = master.winfo_rooty() + master.winfo_height() + 6
        # keep the popup on screen
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        if x + width > self.winfo_screenwidth():
            x = max(0, self.winfo_screenwidth() - width - 8)
        if y + height > self.winfo_screenheight():
            y = max(0, master.winfo_rooty() - height - 6)
        self.geometry(f"+{x}+{y}")
        self.transient(master.winfo_toplevel())

    def _add_label(self) -> None:
        name = self.new_var.get().strip()
        if not name:
            return
        self.new_var.set("")
        self.service.create_label(name, lambda result, error: self._created(result, error, name))

    def _created(self, _result, error, name: str) -> None:
        if error:
            return
        var = tk.BooleanVar(value=True)
        self._vars[name] = var
        self._commit()
        self._close()

    def _commit(self) -> None:
        names = [name for name, var in self._vars.items() if var.get()]
        self.service.set_labels(self.note["id"], names)
        self.on_done(names)

    def _close(self) -> None:
        try:
            self.destroy()
        except tk.TclError:
            pass


class NoteEditor(tk.Toplevel):
    def __init__(self, master, service, note: dict, on_closed=None) -> None:
        super().__init__(master)
        self.service = service
        self.note = dict(note)
        self.note_id = note["id"]
        self.kind = note.get("kind", "note")
        self.on_closed = on_closed
        self._dirty = False
        self._save_job = None
        self._rows: list[dict] = []
        self._closing = False
        self._bg, self._border = theme.note_color(note.get("color", "DEFAULT"))

        self.title(("Liste: " if self.kind == "list" else "Not: ") + (note.get("title") or "Başlıksız"))
        self.configure(bg=self._bg)
        self.geometry("580x640")
        self.minsize(440, 420)
        self.transient(master)

        self._build()
        self._refresh_actions()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _e: self._close())
        self.bind("<Control-s>", lambda _e: self._flush())
        center_on_parent(self, master, 580, 640)
        self.after(80, self._focus_start)

    # -- construction ----------------------------------------------------
    def _build(self) -> None:
        self._surface = tk.Frame(self, bg=self._bg, padx=16, pady=12)
        self._surface.pack(fill="both", expand=True)

        top = tk.Frame(self._surface, bg=self._bg)
        top.pack(fill="x")

        self._kind_icon = tk.Canvas(top, width=24, height=24, bg=self._bg,
                                    highlightthickness=0, bd=0)
        self._kind_icon.pack(side="left")
        self._saved_label = tk.Label(top, text="", bg=self._bg, fg=theme.MUTED,
                                     font=theme.font(8))
        self._saved_label.pack(side="left", padx=(8, 0))

        self._btn_delete = icons.IconButton(top, "trash", command=self._trash,
                                            bg=self._bg, hover_bg=self._shade(),
                                            fg=theme.TEXT_SOFT, tooltip="Sil")
        self._btn_delete.pack(side="right", padx=(2, 0))
        self._btn_archive = icons.IconButton(top, "archive", command=self._archive,
                                             bg=self._bg, hover_bg=self._shade(),
                                             fg=theme.TEXT_SOFT, tooltip="Arşivle")
        self._btn_archive.pack(side="right", padx=(2, 0))
        self._btn_pin = icons.IconButton(top, "pin", command=self._toggle_pin,
                                         bg=self._bg, hover_bg=self._shade(),
                                         fg=theme.TEXT_SOFT, tooltip="Sabitle")
        self._btn_pin.pack(side="right", padx=(2, 0))

        self.title_var = tk.StringVar(value=self.note.get("title", ""))
        self.title_entry = tk.Entry(
            self._surface, textvariable=self.title_var, bd=0, bg=self._bg,
            fg=theme.TEXT, insertbackground=theme.TEXT,
            font=theme.font(15, "bold"), highlightthickness=0,
        )
        self.title_entry.pack(fill="x", pady=(10, 2))
        self.title_entry.bind("<KeyRelease>", lambda _e: self._touch())
        self._title_hint = not self.note.get("title")

        self._body_frame = tk.Frame(self._surface, bg=self._bg)
        if self.kind == "list":
            self._build_list()
        else:
            self._build_note()

        # Footer -------------------------------------------------------
        footer = tk.Frame(self._surface, bg=self._bg, pady=6)
        footer.pack(side="bottom", fill="x")

        palette = tk.Frame(footer, bg=self._bg)
        palette.pack(side="left")
        for value in theme.NOTE_COLOR_ORDER:
            swatch_bg, swatch_border = theme.note_color(value)
            dot = tk.Canvas(palette, width=22, height=22, bg=self._bg,
                            highlightthickness=0, bd=0, cursor="hand2")
            dot.pack(side="left", padx=1)
            dot.create_oval(3, 3, 19, 19, fill=swatch_bg, outline=swatch_border, width=1)
            dot.bind("<Button-1>", lambda _e, v=value: self._set_color(v))
            dot.bind("<Enter>", lambda _e, d=dot: d.create_oval(2, 2, 20, 20,
                                                               outline=theme.ACCENT, width=1,
                                                               tags="ring"))
            dot.bind("<Leave>", lambda _e, d=dot: d.delete("ring"))

        self._btn_label = icons.IconButton(footer, "tag", command=self._pick_labels,
                                           bg=self._bg, hover_bg=self._shade(),
                                           fg=theme.TEXT_SOFT, tooltip="Etiketle")
        self._btn_label.pack(side="right")
        self._btn_convert = icons.IconButton(
            footer, "list" if self.kind == "note" else "note",
            command=self._convert, bg=self._bg, hover_bg=self._shade(),
            fg=theme.TEXT_SOFT,
            tooltip="Kontrol listesine dönüştür" if self.kind == "note" else "Nota dönüştür")
        self._btn_convert.pack(side="right")
        icons.draw(self._kind_icon, "list" if self.kind == "list" else "note",
                   3, 3, 18, color=theme.TEXT_SOFT)

        self._labels_row = tk.Frame(self._surface, bg=self._bg)
        self._labels_row.pack(side="bottom", fill="x", pady=(2, 0))
        self._render_label_chips()

        self._body_frame.pack(fill="both", expand=True, pady=(6, 6))

    def _build_note(self) -> None:
        self.text = tk.Text(
            self._body_frame, bd=0, bg=self._bg, fg=theme.TEXT,
            insertbackground=theme.TEXT, font=theme.font(theme._SIZE_BASE + 1),
            wrap="word", highlightthickness=0, padx=0, pady=0,
            spacing1=2, spacing3=4, undo=True,
        )
        self.text.pack(fill="both", expand=True)
        body = self.note.get("text", "")
        if body:
            self.text.insert("1.0", body)
        else:
            self._placeholder = True
            self.text.insert("1.0", "Not yaz…")
            self.text.configure(fg=theme.FAINT)
            self.text.bind("<FocusIn>", self._clear_placeholder, add="+")
        self.text.bind("<KeyRelease>", lambda _e: self._touch())

    def _clear_placeholder(self, _event=None) -> None:
        if getattr(self, "_placeholder", False):
            self._placeholder = False
            self.text.delete("1.0", "end")
            self.text.configure(fg=theme.TEXT)

    def _build_list(self) -> None:
        self._list_scroll = ScrollFrame(self._body_frame, bg=self._bg)
        self._list_scroll.pack(fill="both", expand=True)
        holder = self._list_scroll.body
        holder.configure(bg=self._bg)

        self._items_holder = tk.Frame(holder, bg=self._bg)
        self._items_holder.pack(fill="x")

        self._add_row = tk.Frame(holder, bg=self._bg)
        self._add_row.pack(fill="x", pady=(4, 0))
        plus = icons.IconButton(self._add_row, "plus", command=lambda: self._append_item(focus=True),
                                bg=self._bg, hover_bg=self._shade(), fg=theme.TEXT_SOFT,
                                size=24, icon_size=14)
        plus.pack(side="left")
        self._add_label = tk.Label(self._add_row, text="Liste öğesi ekle", bg=self._bg,
                                   fg=theme.MUTED, font=theme.font(theme._SIZE_BASE),
                                   cursor="hand2")
        self._add_label.pack(side="left", padx=(4, 0))
        self._add_label.bind("<Button-1>", lambda _e: self._append_item(focus=True))

        for item in self.note.get("items", []):
            self._append_item(item.get("text", ""), item.get("checked", False),
                              item_id=item.get("id"), focus=False, focus_last=False,
                              mark_dirty=False)

    # -- helpers ---------------------------------------------------------
    def _shade(self) -> str:
        bg = self._bg.lstrip("#")
        r, g, b = (int(bg[i:i + 2], 16) for i in (0, 2, 4))
        shade = tuple(max(0, int(v * 0.94)) for v in (r, g, b))
        return "#%02x%02x%02x" % shade

    def _focus_start(self) -> None:
        if self.kind == "note":
            self.text.focus_set()
        elif not self._rows:
            self._append_item(focus=True)
        if self._title_hint:
            self.title_entry.focus_set()

    def _touch(self) -> None:
        if not self.winfo_exists():
            return
        self._dirty = True
        self._saved_label.configure(text="kaydediliyor…")
        if self._save_job is not None:
            try:
                self.after_cancel(self._save_job)
            except tk.TclError:
                pass
        self._save_job = self.after(900, self._flush)

    def _flush(self, then=None) -> None:
        if self._save_job is not None:
            try:
                self.after_cancel(self._save_job)
            except tk.TclError:
                pass
            self._save_job = None
        if not self._dirty:
            if then:
                then()
            return
        self._dirty = False
        title = self.title_var.get().strip()
        if self.kind == "note":
            body = "" if getattr(self, "_placeholder", False) else self.text.get("1.0", "end-1c")
            self.service.update(
                self.note_id, {"title": title, "text": body},
                lambda result, error: self._saved(result, error, then),
            )
        else:
            rows = [row for row in self._rows if row["var"].get().strip()]
            payload = [{"id": row["id"], "text": row["var"].get(), "checked": row["checked"]}
                       for row in rows]
            self.service.update(self.note_id, {"title": title})
            self.service.set_items(
                self.note_id, payload,
                lambda result, error: self._saved(result, error, then, rows=rows),
            )

    def _saved(self, result, error, then=None, rows=None) -> None:
        if not self.winfo_exists():
            if then:
                then()
            return
        if error is not None:
            self._saved_label.configure(text="kaydedilemedi")
            if then:
                then()
            return
        if rows and isinstance(result, dict):
            items = [item for item in result.get("items", []) if item.get("text", "").strip()]
            for row, item in zip(rows, items):
                row["id"] = item["id"]
        self._saved_label.configure(text="kaydedildi")
        try:
            self.after(1600, self._clear_saved_label)
        except tk.TclError:
            pass
        if then:
            then()

    def _clear_saved_label(self) -> None:
        if self.winfo_exists():
            self._saved_label.configure(text="")

    def _refresh_actions(self) -> None:
        self._btn_pin.set_icon("pin-filled" if self.note.get("pinned") else "pin",
                               theme.ACCENT_TEXT if self.note.get("pinned") else theme.TEXT_SOFT)
        self._btn_archive.set_icon("archive")

    # -- list rows -------------------------------------------------------
    def _append_item(self, text: str = "", checked: bool = False, item_id: str | None = None,
                     focus: bool = True, focus_last: bool = True,
                     mark_dirty: bool = True) -> None:
        row = {"id": item_id, "checked": checked}
        holder = tk.Frame(self._items_holder, bg=self._bg)
        holder.pack(fill="x", pady=1)

        circle = CheckCircle(holder, checked=checked, bg=self._bg, size=20,
                             command=lambda value, r=row: self._set_checked(r, value))
        circle.pack(side="left", pady=2)

        var = tk.StringVar(value=text)
        entry = tk.Entry(holder, textvariable=var, bd=0, bg=self._bg, fg=theme.TEXT,
                         insertbackground=theme.TEXT, font=theme.font(theme._SIZE_BASE),
                         highlightthickness=0)
        entry.pack(side="left", fill="x", expand=True, padx=(8, 4), pady=2)
        row.update({"var": var, "entry": entry, "circle": circle, "frame": holder})

        remove = tk.Label(holder, text="×", bg=self._bg, fg=theme.MUTED,
                          font=theme.font(12), cursor="hand2", padx=4)
        remove.pack(side="right")
        remove.bind("<Button-1>", lambda _e, r=row: self._remove_item(r))
        row["remove"] = remove

        var.trace_add("write", lambda *_a, r=row: self._item_changed(r))
        entry.bind("<Return>", lambda _e, r=row: self._append_item(focus=True))
        entry.bind("<BackSpace>", lambda _e, r=row: self._backspace(r))
        entry.bind("<FocusIn>", lambda _e, r=row: self._focus_row(r))

        self._rows.append(row)
        if checked:
            self._paint_checked(row)
        if focus:
            self.after(10, entry.focus_set)
        if mark_dirty:
            self._touch()

    def _focus_row(self, row) -> None:
        self._current_row = row

    def _item_changed(self, row) -> None:
        self._touch()

    def _set_checked(self, row, value: bool) -> None:
        row["checked"] = bool(value)
        self._paint_checked(row)
        self._touch()

    def _paint_checked(self, row) -> None:
        if row["checked"]:
            row["entry"].configure(fg="#8C8C86")
        else:
            row["entry"].configure(fg=theme.TEXT)

    def _backspace(self, row) -> None:
        if row["var"].get():
            return "break"
        if len(self._rows) <= 1:
            return "break"
        self._remove_item(row)
        return "break"

    def _remove_item(self, row) -> None:
        row["frame"].destroy()
        if row in self._rows:
            self._rows.remove(row)
        self._touch()

    # -- actions ---------------------------------------------------------
    def _set_color(self, value: str) -> None:
        self.note["color"] = value
        self.service.update(self.note_id, {"color": value})
        self._bg, self._border = theme.note_color(value)
        self.configure(bg=self._bg)
        for widget in self._walk(self):
            try:
                widget.configure(bg=self._bg)
            except tk.TclError:
                pass
        self._list_bg_fix()

    def _list_bg_fix(self) -> None:
        if self.kind == "list":
            for widget in self._walk(self._items_holder):
                try:
                    widget.configure(bg=self._bg)
                except tk.TclError:
                    pass

    def _walk(self, widget):
        yield widget
        for child in widget.winfo_children():
            yield from self._walk(child)

    def _toggle_pin(self) -> None:
        self.note["pinned"] = not self.note.get("pinned")
        self.service.update(self.note_id, {"pinned": self.note["pinned"]})
        self._refresh_actions()

    def _archive(self) -> None:
        self._flush()
        self.service.update(self.note_id, {"archived": not self.note.get("archived")})
        self._close(after_save=False)

    def _trash(self) -> None:
        self._flush()
        trashed = self.note.get("trashed")
        if trashed:
            if not messagebox.askyesno("Kalıcı olarak sil", "Bu not kalıcı olarak silinsin mi?",
                                       parent=self):
                return
            self.service.delete_forever(self.note_id)
        else:
            self.service.trash(self.note_id)
        self._close(after_save=False)

    def _convert(self) -> None:
        target = "list" if self.kind == "note" else "note"
        self._flush(lambda: self._do_convert(target))

    def _do_convert(self, target: str) -> None:
        def done(result, error) -> None:
            if error is not None:
                messagebox.showerror("Dönüştürülemedi", str(error), parent=self)
                return
            self._close(after_save=False)
            if self.on_closed:
                self.on_closed()

        self.service.convert(self.note_id, target, done)

    def _pick_labels(self) -> None:
        self._flush()
        LabelPicker(self, self.service, self.note, self._labels_changed)

    def _labels_changed(self, names: list[str]) -> None:
        self.note["labels"] = names
        self._render_label_chips()

    def _render_label_chips(self) -> None:
        for child in self._labels_row.winfo_children():
            child.destroy()
        names = self.note.get("labels", [])
        if not names:
            return
        for name in names:
            chip = tk.Label(self._labels_row, text=name, bg=self._shade(), fg=theme.TEXT_SOFT,
                            font=theme.font(8), padx=8, pady=2)
            chip.pack(side="left", padx=(0, 4))

    # -- lifecycle -------------------------------------------------------
    def _close(self, after_save: bool = True) -> None:
        if self._closing:
            return
        self._closing = True
        if after_save:
            self._flush()
        try:
            self.destroy()
        except tk.TclError:
            pass
        if self.on_closed:
            self.on_closed()

