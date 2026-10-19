"""Tiny vector icons drawn on a tkinter Canvas (no image assets, no emoji)."""

from __future__ import annotations

import tkinter as tk

from .. import theme


def _scale(x, y, ox, oy, s):
    return ox + x * s, oy + y * s


def draw(canvas: tk.Canvas, name: str, x: int, y: int, size: int = 20,
         color: str = theme.TEXT, width: float = 1.7, tags: str | None = None) -> None:
    """Draw icon ``name`` in a 24x24 box whose top-left corner is (x, y)."""
    s = size / 24.0
    w = max(1.0, width * s * 1.1)
    kw = {"tags": tags} if tags else {}
    c = canvas

    def line(points, fill=color, w_=w, smooth=False):
        coords = []
        for px, py in points:
            coords.extend(_scale(px, py, x, y, s))
        return c.create_line(
            *coords, fill=fill, width=w_, capstyle="round", joinstyle="round",
            smooth=smooth, **kw,
        )

    def rect(x1, y1, x2, y2, outline=color, w_=w, fill=""):
        return c.create_rectangle(
            *_scale(x1, y1, x, y, s), *_scale(x2, y2, x, y, s),
            outline=outline, width=w_, fill=fill, **kw,
        )

    def oval(cx, cy, r, outline=color, w_=w, fill=""):
        return c.create_oval(
            *_scale(cx - r, cy - r, x, y, s), *_scale(cx + r, cy + r, x, y, s),
            outline=outline, width=w_, fill=fill, **kw,
        )

    if name == "search":
        oval(10.5, 10.5, 6.3)
        line([(15.3, 15.3), (20, 20)])
    elif name == "plus":
        line([(12, 5.5), (12, 18.5)])
        line([(5.5, 12), (18.5, 12)])
    elif name == "close":
        line([(6.5, 6.5), (17.5, 17.5)])
        line([(17.5, 6.5), (6.5, 17.5)])
    elif name == "check":
        line([(5.5, 12.5), (10, 17), (18.5, 7)])
    elif name == "notes":
        line([(5, 7), (19, 7)])
        line([(5, 12), (16.5, 12)])
        line([(5, 17), (13, 17)])
    elif name == "archive":
        rect(4, 4.2, 20, 8)
        rect(5.6, 8, 18.4, 19.6)
        line([(9.8, 12.4), (14.2, 12.4)])
    elif name == "trash":
        line([(4, 6.6), (20, 6.6)])
        line([(9.4, 4.2), (14.6, 4.2)])
        line([(6.4, 6.6), (7.4, 19.6)])
        line([(17.6, 6.6), (16.6, 19.6)])
        line([(7.4, 19.6), (16.6, 19.6)])
        line([(10, 10), (10, 16.6)], w_=w * 0.85)
        line([(14, 10), (14, 16.6)], w_=w * 0.85)
    elif name == "tag":
        line([(4.2, 10.4), (10.4, 4.2), (19.6, 4.2), (19.6, 13.4), (13.4, 19.6), (4.2, 10.4)])
        oval(15.6, 8.2, 1.4)
    elif name == "pin":
        oval(12, 8.6, 4.6)
        line([(12, 13.2), (12, 19.6)])
        line([(9.2, 19.6), (14.8, 19.6)])
    elif name == "pin-filled":
        oval(12, 8.6, 4.6, fill=color)
        line([(12, 13.2), (12, 19.6)])
        line([(9.2, 19.6), (14.8, 19.6)])
    elif name == "refresh":
        c.create_arc(
            *_scale(5, 5, x, y, s), *_scale(19, 19, x, y, s),
            start=60, extent=280, style="arc", outline=color, width=w, **kw,
        )
        line([(18.4, 5.2), (18.9, 10.2), (14.2, 8.9)], w_=w * 0.9)
    elif name == "more":
        for cx in (6, 12, 18):
            oval(cx, 12, 1.35, fill=color, w_=0.5)
    elif name == "menu":
        line([(4, 7), (20, 7)])
        line([(4, 12), (20, 12)])
        line([(4, 17), (20, 17)])
    elif name == "chevron-left":
        line([(15, 5.5), (8.5, 12), (15, 18.5)])
    elif name == "chevron-down":
        line([(5.5, 9.5), (12, 16), (18.5, 9.5)])
    elif name == "list":
        line([(5, 7), (6.6, 7)])
        line([(5, 12), (6.6, 12)])
        line([(5, 17), (6.6, 17)])
        line([(9.6, 7), (19, 7)])
        line([(9.6, 12), (19, 12)])
        line([(9.6, 17), (19, 17)])
    elif name == "note":
        rect(4.6, 4.6, 19.4, 19.4)
        line([(8, 9), (16, 9)])
        line([(8, 13), (16, 13)])
        line([(8, 16.6), (12.5, 16.6)])
    elif name == "logout":
        line([(14, 5.4), (6.4, 5.4), (6.4, 18.6), (14, 18.6)])
        line([(11, 12), (20, 12)])
        line([(16.6, 8.6), (20, 12), (16.6, 15.4)])
    elif name == "grip":
        for cx in (9, 15):
            for cy in (7, 12, 17):
                oval(cx, cy, 1.5, fill=color, w_=0.4)
    elif name == "check-small":
        line([(6, 12.5), (10.5, 17), (18, 7.5)])
    else:  # pragma: no cover - unknown icon
        oval(12, 12, 7)


class IconButton(tk.Canvas):
    """Flat, hoverable icon button."""

    def __init__(
        self,
        master,
        icon: str,
        command=None,
        size: int = 32,
        icon_size: int = 18,
        bg: str = theme.SURFACE,
        hover_bg: str = "#EFEBE1",
        fg: str = theme.TEXT_SOFT,
        tooltip: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            width=size,
            height=size,
            bg=bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            **kwargs,
        )
        self._icon = icon
        self._icon_size = icon_size
        self._bg = bg
        self._hover_bg = hover_bg
        self._fg = fg
        self._command = command
        self._size = size
        self._tooltip = tooltip
        self._tip = None
        self._hovering = False
        self._draw()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _draw(self) -> None:
        self.delete("all")
        offset = (self._size - self._icon_size) // 2
        draw(self, self._icon, offset, offset, self._icon_size, color=self._fg)

    def set_icon(self, icon: str, fg: str | None = None) -> None:
        self._icon = icon
        if fg:
            self._fg = fg
        self._draw()

    def _on_enter(self, _event=None) -> None:
        self._hovering = True
        self.configure(bg=self._hover_bg)
        if self._tooltip and self._tip is None:
            self.after(550, self._show_tip)

    def _on_leave(self, _event=None) -> None:
        self._hovering = False
        self.configure(bg=self._bg)
        self._hide_tip()

    def _on_click(self, _event=None) -> None:
        if self._command:
            self._command()

    def _show_tip(self) -> None:
        if self._tip is not None or not self._tooltip or not self._hovering:
            return
        try:
            x = self.winfo_rootx() + self.winfo_width() // 2
            y = self.winfo_rooty() + self.winfo_height() + 6
        except tk.TclError:
            return
        tip = tk.Toplevel(self)
        tip.wm_overrideredirect(True)
        tip.configure(bg=theme.TEXT)
        label = tk.Label(
            tip,
            text=self._tooltip,
            bg=theme.TEXT,
            fg=theme.INVERSE,
            font=theme.font(theme._SIZE_SMALL),
            padx=8,
            pady=3,
        )
        label.pack()
        tip.update_idletasks()
        tip.wm_geometry(f"+{x - tip.winfo_width() // 2}+{y}")
        self._tip = tip

    def _hide_tip(self) -> None:
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None
