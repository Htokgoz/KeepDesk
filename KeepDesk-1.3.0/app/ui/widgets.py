"""Reusable little widgets and helpers."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from .. import theme


def make_font(spec: tuple) -> tkfont.Font:
    return tkfont.Font(font=spec)


def wrap_text(text: str, fnt: tkfont.Font, width: int, max_lines: int) -> list[str]:
    """Greedy wrap that respects pixel width and clips to ``max_lines``."""
    text = " ".join(text.split())
    if not text:
        return []
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if fnt.measure(candidate) <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
            if len(lines) == max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines:
        # Anything left over?
        joined = " ".join(lines)
        if len(joined) < len(text):
            last = lines[-1]
            while last and fnt.measure(last + "…") > width:
                last = last[:-1]
            lines[-1] = last.rstrip() + "…"
    return lines


def center_on_parent(window: tk.Toplevel, parent: tk.Misc | None = None,
                     width: int | None = None, height: int | None = None) -> None:
    window.update_idletasks()
    w = width or window.winfo_width()
    h = height or window.winfo_height()
    if parent is not None and parent.winfo_exists():
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 3)
    else:
        x = (window.winfo_screenwidth() - w) // 2
        y = (window.winfo_screenheight() - h) // 3
    window.geometry(f"{w}x{h}+{x}+{y}")


class PlaceholderEntry(ttk.Entry):
    """Entry that paints a hint while empty and unfocused."""

    def __init__(self, master, placeholder: str = "", **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._placeholder = placeholder
        self._showing = False
        self._fg = theme.TEXT
        self._hint_fg = theme.FAINT
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        self._show_hint()

    def _show_hint(self) -> None:
        if not self._placeholder:
            return
        if not super().get():
            self._showing = True
            self.configure(foreground=self._hint_fg)
            self.insert(0, self._placeholder)

    def _on_focus_in(self, _event=None) -> None:
        if self._showing:
            self._showing = False
            self.delete(0, "end")
            self.configure(foreground=self._fg)

    def _on_focus_out(self, _event=None) -> None:
        if not super().get():
            self._show_hint()

    def value(self) -> str:
        if self._showing:
            return ""
        return self.get()


class Toast:
    """Transient message anchored to the bottom of a container."""

    def __init__(self, host: tk.Misc) -> None:
        self.host = host
        self._label: tk.Label | None = None
        self._after_id: str | None = None

    def show(self, message: str, kind: str = "info", timeout: int = 2800) -> None:
        self.hide()
        bg = {"info": theme.TEXT, "error": theme.RED, "ok": theme.GREEN}.get(kind, theme.TEXT)
        label = tk.Label(
            self.host,
            text=message,
            bg=bg,
            fg="#FFFFFF",
            font=theme.font(theme._SIZE_SMALL),
            padx=14,
            pady=7,
        )
        label.place(relx=0.5, rely=1.0, y=-18, anchor="s")
        label.lift()
        self._label = label
        self._after_id = self.host.after(timeout, self.hide)

    def hide(self) -> None:
        if self._after_id is not None:
            try:
                self.host.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        if self._label is not None:
            self._label.destroy()
            self._label = None


class ScrollFrame(ttk.Frame):
    """Canvas-backed vertical scroller."""

    def __init__(self, master, bg: str = theme.BG, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self.configure(style="TFrame")
        self.canvas = tk.Canvas(
            self, bg=bg, highlightthickness=0, bd=0, yscrollincrement=24
        )
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.bar.pack(side="right", fill="y", padx=(2, 0))

        self.body = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", self._on_body_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind_mousewheel(self.canvas)

    def _on_scroll(self, first: str, last: str) -> None:
        self.bar.set(first, last)

    def _on_body_configure(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._sync_bar()

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)
        self._sync_bar()

    def _sync_bar(self) -> None:
        """Hide the scrollbar while everything fits."""
        if not self.canvas.winfo_exists() or not self.bar.winfo_exists():
            return
        box = self.canvas.bbox("all")
        needed = bool(box) and (box[3] - box[1]) > self.canvas.winfo_height() + 1
        mapped = self.bar.winfo_ismapped()
        if needed and not mapped:
            self.bar.pack(side="right", fill="y", padx=(2, 0))
        elif not needed and mapped:
            self.bar.pack_forget()

    def bind_mousewheel(self, widget: tk.Misc) -> None:
        def on_wheel(event):
            if not self.canvas.winfo_exists():
                return
            delta = -1 if event.delta > 0 else 1
            self.canvas.yview_scroll(delta * 3, "units")
            return "break"

        def on_enter(_e=None):
            widget.bind_all("<MouseWheel>", on_wheel)

        def on_leave(_e=None):
            widget.unbind_all("<MouseWheel>")

        widget.bind("<Enter>", on_enter, add="+")
        widget.bind("<Leave>", on_leave, add="+")

    def scroll_top(self) -> None:
        self.canvas.yview_moveto(0)


class CheckCircle(tk.Canvas):
    """Round checkbox used by checklist rows."""

    def __init__(self, master, checked: bool = False, command=None,
                 bg: str = theme.SURFACE, size: int = 20, **kwargs) -> None:
        super().__init__(master, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2", **kwargs)
        self._checked = checked
        self._command = command
        self._size = size
        self._bg = bg
        self._draw()
        self.bind("<Button-1>", self._toggle)

    def _draw(self) -> None:
        self.delete("all")
        s = self._size
        pad = 2
        if self._checked:
            self.create_oval(pad, pad, s - pad, s - pad, fill=theme.ACCENT,
                             outline=theme.ACCENT)
            w = 1.8
            self.create_line(s * 0.27, s * 0.52, s * 0.44, s * 0.69, s * 0.74, s * 0.33,
                             fill="#3A2C05", width=w, capstyle="round",
                             joinstyle="round")
        else:
            self.create_oval(pad, pad, s - pad, s - pad, outline="#B8B2A6", width=1.5)

    def set(self, checked: bool) -> None:
        self._checked = bool(checked)
        self._draw()

    def get(self) -> bool:
        return self._checked

    def _toggle(self, _event=None) -> None:
        self.set(not self._checked)
        if self._command:
            self._command(self._checked)


class SearchBox(tk.Frame):
    """Rounded-looking search field with icon."""

    def __init__(self, master, placeholder: str = "Ara", on_change=None,
                 bg: str = theme.SURFACE, **kwargs) -> None:
        super().__init__(master, bg=bg, highlightthickness=1,
                         highlightbackground=theme.BORDER,
                         highlightcolor=theme.BORDER, **kwargs)
        from . import icons

        self._icon = tk.Canvas(self, width=26, height=26, bg=bg,
                               highlightthickness=0, bd=0)
        self._icon.pack(side="left", padx=(10, 0))
        icons.draw(self._icon, "search", 6, 5, 16, color=theme.MUTED)

        self.var = tk.StringVar()
        self.entry = tk.Entry(
            self, textvariable=self.var, bd=0, bg=bg, fg=theme.TEXT,
            insertbackground=theme.TEXT, font=theme.font(theme._SIZE_BASE),
            highlightthickness=0,
        )
        self.entry.pack(side="left", fill="both", expand=True, padx=(6, 10), pady=9)
        self._placeholder = placeholder
        self._hint_visible = True
        self.entry.insert(0, placeholder)
        self.entry.configure(fg=theme.FAINT)
        self._on_change = on_change

        self.entry.bind("<FocusIn>", self._focus_in)
        self.entry.bind("<FocusOut>", self._focus_out)
        self.var.trace_add("write", self._changed)

    def _focus_in(self, _event=None) -> None:
        if self._hint_visible:
            self._hint_visible = False
            self.entry.delete(0, "end")
            self.entry.configure(fg=theme.TEXT)

    def _focus_out(self, _event=None) -> None:
        if not self.entry.get():
            self._hint_visible = True
            self.entry.insert(0, self._placeholder)
            self.entry.configure(fg=theme.FAINT)

    def _changed(self, *_args) -> None:
        if self._on_change and not self._hint_visible:
            self._on_change(self.value())

    def value(self) -> str:
        if self._hint_visible:
            return ""
        return self.entry.get()

    def clear(self) -> None:
        self.entry.delete(0, "end")

    def focus(self) -> None:  # noqa: A003 - tk naming
        self.entry.focus_set()

    def bind_escape(self, callback) -> None:
        self.entry.bind("<Escape>", lambda _e: callback())


class Pill(tk.Label):
    """Small rounded-ish tag chip."""

    def __init__(self, master, text: str, bg: str = theme.ACCENT_TINT,
                 fg: str = theme.TEXT, **kwargs) -> None:
        super().__init__(master, text=text, bg=bg, fg=fg,
                         font=theme.font(theme._SIZE_SMALL), padx=7, pady=2, **kwargs)


class CheckToggle(tk.Frame):
    """Checkbox with a hand-drawn box (keeps the flat look consistent)."""

    def __init__(self, master, text: str, variable: tk.BooleanVar | None = None,
                 bg: str = theme.SURFACE, command=None) -> None:
        super().__init__(master, bg=bg, cursor="hand2")
        self.var = variable if variable is not None else tk.BooleanVar(value=False)
        self._bg = bg
        self._command = command

        self._box = tk.Canvas(self, width=18, height=18, bg=bg,
                              highlightthickness=0, bd=0, cursor="hand2")
        self._box.pack(side="left")
        self._label = tk.Label(self, text=text, bg=bg, fg=theme.TEXT_SOFT,
                               font=theme.font(theme._SIZE_BASE), cursor="hand2")
        self._label.pack(side="left", padx=(8, 0))

        for widget in (self, self._box, self._label):
            widget.bind("<Button-1>", self._toggle)
        self._draw()

    def _draw(self) -> None:
        self._box.delete("all")
        if self.var.get():
            self._box.create_rectangle(1, 1, 17, 17, fill=theme.ACCENT,
                                       outline=theme.ACCENT)
            self._box.create_line(4.5, 9, 7.4, 12.2, 13.5, 5.4, fill=theme.ACCENT_TEXT,
                                  width=2.0, capstyle="round", joinstyle="round")
        else:
            self._box.create_rectangle(1, 1, 17, 17, fill=self._bg,
                                       outline="#B8B2A6", width=1.4)

    def _toggle(self, _event=None) -> None:
        self.var.set(not self.var.get())
        self._draw()
        if self._command:
            self._command(self.var.get())

    def get(self) -> bool:
        return bool(self.var.get())

