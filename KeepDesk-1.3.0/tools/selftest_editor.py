"""Render the note editor for a visual check: ``python tools/selftest_editor.py [list|note]``."""

from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "vendor"))

import tkinter as tk  # noqa: E402

from app import theme  # noqa: E402
from app.main import _enable_dpi  # noqa: E402
from app.service import KeepService  # noqa: E402
from app.ui.editor import NoteEditor  # noqa: E402
from app.ui.mainwindow import MainWindow  # noqa: E402

NOW = time.time()

LIST_NOTE = {
    "id": "n2", "kind": "list", "title": "Yapılacaklar", "text": "",
    "items": [
        {"id": "i1", "text": "Sunum taslağını bitir", "checked": True},
        {"id": "i2", "text": "Toplantı notlarını paylaş", "checked": True},
        {"id": "i3", "text": "Uçuş rezervasyonunu onayla", "checked": False},
        {"id": "i4", "text": "Kitaplığı düzenle", "checked": False},
    ],
    "labels": ["iş"], "color": "DEFAULT", "pinned": True, "archived": False,
    "trashed": False, "updated": NOW - 400, "created": NOW - 4000,
}

TEXT_NOTE = {
    "id": "n1", "kind": "note", "title": "Alışveriş fikirleri", "text":
    "Hafta sonu için market listesi: zeytinyağı, kahve çekirdeği, tam buğday unu ve "
    "taze fesleğen.\n\nFırında domates çorbası denenecek. Tarif için eski deftere bak.",
    "items": [], "labels": ["ev", "alışveriş"], "color": "YELLOW", "pinned": False,
    "archived": False, "trashed": False, "updated": NOW - 120, "created": NOW - 9000,
}


class DummyApp:
    def __init__(self, service):
        self.service = service

    def open_note(self, *a, **k):
        pass

    def show_note_menu(self, *a, **k):
        pass

    def logout(self):
        pass


def main() -> None:
    kind = sys.argv[1] if len(sys.argv) > 1 else "list"
    _enable_dpi()
    root = tk.Tk()
    root.title("KeepDesk editor test")
    root.geometry("1000x720")
    theme.apply_theme(root)
    try:
        root.tk.call("tk", "scaling", max(1.0, root.winfo_fpixels("1i") / 72.0))
    except tk.TclError:
        pass

    service = KeepService(root.after, device_id="0123456789abcdef")
    service.email = "ornek.hesap@gmail.com"
    service.status = "ok"
    service.last_sync = time.time()
    note = LIST_NOTE if kind == "list" else TEXT_NOTE
    service.prime_cache({"email": service.email, "notes": [note], "labels": [
        {"id": "l1", "name": "iş"}, {"id": "l2", "name": "ev"}]})

    # Editing is out of scope for this visual test.
    service.update = lambda *a, **k: None
    service.set_items = lambda *a, **k: None
    service.convert = lambda *a, **k: None

    window = MainWindow(root, app=DummyApp(service), service=service)
    window.pack(fill="both", expand=True)
    root.lift()
    root.attributes("-topmost", True)
    root.after(1800, lambda: root.attributes("-topmost", False))

    def open_editor() -> None:
        try:
            editor = NoteEditor(root, service, note)
            editor.attributes("-topmost", True)
            editor.after(1800, lambda: editor.attributes("-topmost", False))
            with open(os.path.join(ROOT, "tmp", "editor_debug.txt"), "w", encoding="utf-8") as fh:
                fh.write(f"exists={editor.winfo_exists()} viewable={editor.winfo_viewable()} "
                         f"geom={editor.geometry()} title={editor.title()}\n")
        except Exception:
            import traceback

            with open(os.path.join(ROOT, "tmp", "editor_debug.txt"), "w", encoding="utf-8") as fh:
                fh.write(traceback.format_exc())

    root.after(400, open_editor)
    root.after(22000, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
