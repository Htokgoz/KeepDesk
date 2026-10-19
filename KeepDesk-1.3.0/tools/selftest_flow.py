"""End-to-end flow check: build the real app, fake a session, click a card.

    python tools/selftest_flow.py
"""

from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "vendor"))

os.environ["APPDATA"] = os.path.join(ROOT, "tmp", "appdata-flow")
os.environ.setdefault("TMP", os.path.join(ROOT, "tmp"))
os.environ.setdefault("TEMP", os.path.join(ROOT, "tmp"))

import tkinter as tk  # noqa: E402

from app.main import KeepDeskApp  # noqa: E402

NOW = time.time()
SAMPLE = [
    {
        "id": "n1", "kind": "note", "title": "Akış testi", "text": "Kart tıklaması çalışıyor mu?",
        "items": [], "labels": ["test"], "color": "YELLOW", "pinned": True,
        "archived": False, "trashed": False, "updated": NOW - 60, "created": NOW - 600,
    },
    {
        "id": "n2", "kind": "list", "title": "Liste", "text": "",
        "items": [{"id": "i1", "text": "bir", "checked": True},
                  {"id": "i2", "text": "iki", "checked": False}],
        "labels": [], "color": "DEFAULT", "pinned": False, "archived": False,
        "trashed": False, "updated": NOW - 120, "created": NOW - 900,
    },
]

failures: list[str] = []


def check(label: str, condition: bool) -> None:
    print(("  OK   " if condition else "  FAIL ") + label)
    if not condition:
        failures.append(label)


def main() -> int:
    app = KeepDeskApp()
    app.service.prime_cache({
        "email": "ornek@example.com",
        "notes": SAMPLE,
        "labels": [{"id": "l1", "name": "test"}],
    })

    def run() -> None:
        app._login_succeeded("ornek@example.com", "fake-master-token", True)
        check("ana pencere açıldı", app.main_window is not None)

        window = app.main_window
        assert window is not None
        window._render()
        check("kartlar çizildi", len(window._card_widgets) >= 2)

        # This is the call that used to raise AttributeError.
        app.open_note("n1")
        editor = window._editors.get("n1")
        check("not editörü açıldı", editor is not None and editor.winfo_exists())

        if editor is not None:
            check("başlık yüklendi", editor.title_var.get() == "Akış testi")
            editor._close()

        app.open_note("n2")
        list_editor = window._editors.get("n2")
        check("liste editörü açıldı", list_editor is not None and list_editor.winfo_exists())
        if list_editor is not None:
            check("liste satırları yüklendi", len(list_editor._rows) == 2)
            list_editor._close()

        window.set_view("archive")
        window._render()
        check("arşiv görünümü boş", len(window._card_widgets) == 0)
        window.set_view("notes")
        window._render()
        app.update_idletasks()
        app.update()
        check("notlar görünümüne dönüldü", len(window._card_widgets) >= 2)

        # a label chip on the card filters the board instead of opening the note
        chip = None

        def find_chip(widget):
            nonlocal chip
            for child in widget.winfo_children():
                if isinstance(child, tk.Label) and child.cget("text") == "test":
                    chip = child
                    return
                find_chip(child)

        for card in window._card_widgets:
            if isinstance(card, tk.Frame):
                find_chip(card)
            if chip is not None:
                break
        check("kart üzerinde etiket düğmesi var", chip is not None)
        if chip is not None:
            opened_before = len(window._editors)
            chip.event_generate("<Button-1>", x=4, y=4)
            app.update()
            check("etiket düğmesi filtre uyguluyor",
                  window.view == "label" and window.label_name == "test")
            check("etiket düğmesi not açmıyor", len(window._editors) == opened_before)

        app.after(200, app._quit)

    app.after(400, run)
    app.mainloop()
    print("FAILURES:", failures if failures else "none")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
