"""Render the main window with sample data, for visual checks.

    python tools/selftest_ui.py [seconds]
"""

from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "vendor"))

import tkinter as tk  # noqa: E402

from app import theme  # noqa: E402
from app.main import _enable_dpi, _setup_tls  # noqa: E402
from app.service import KeepService  # noqa: E402
from app.ui.mainwindow import MainWindow  # noqa: E402

NOW = time.time()

SAMPLE = [
    {
        "id": "n1", "kind": "note", "title": "Alışveriş fikirleri", "text":
        "Hafta sonu için market listesi: zeytinyağı, kahve çekirdeği, "
        "tam buğday unu ve taze fesleğen. Fırında domates çorbası denenecek.",
        "items": [], "labels": ["ev"], "color": "YELLOW", "pinned": True,
        "archived": False, "trashed": False, "updated": NOW - 120, "created": NOW - 9000,
    },
    {
        "id": "n2", "kind": "list", "title": "Yapılacaklar", "text": "",
        "items": [
            {"id": "i1", "text": "Sunum taslağını bitir", "checked": True},
            {"id": "i2", "text": "Toplantı notlarını paylaş", "checked": True},
            {"id": "i3", "text": "Uçuş rezervasyonunu onayla", "checked": False},
            {"id": "i4", "text": "Kitaplığı düzenle", "checked": False},
        ],
        "labels": ["iş"], "color": "DEFAULT", "pinned": False, "archived": False,
        "trashed": False, "updated": NOW - 400, "created": NOW - 4000,
    },
    {
        "id": "n3", "kind": "note", "title": "Kitap önerileri", "text":
        "Kış okuma listesi: Sefiller, Bir Bilim Adamının Romanı, Tutunamayanlar.\n"
        "Not: kütüphaneden alınacak.",
        "items": [], "labels": ["okuma"], "color": "BLUE", "pinned": False,
        "archived": False, "trashed": False, "updated": NOW - 900, "created": NOW - 20000,
    },
    {
        "id": "n4", "kind": "note", "title": "Fikir", "text":
        "Mutfak için basit bir envanter uygulaması: barkod okuma + son kullanma tarihi.",
        "items": [], "labels": [], "color": "GREEN", "pinned": False,
        "archived": False, "trashed": False, "updated": NOW - 1500, "created": NOW - 30000,
    },
    {
        "id": "n5", "kind": "list", "title": "Hafta sonu planı", "text": "",
        "items": [
            {"id": "j1", "text": "Cumartesi: bisiklet turu", "checked": False},
            {"id": "j2", "text": "Pazar: kahvaltı + pazar", "checked": False},
        ],
        "labels": ["kişisel"], "color": "PINK", "pinned": False, "archived": False,
        "trashed": False, "updated": NOW - 5000, "created": NOW - 50000,
    },
    {
        "id": "n6", "kind": "note", "title": "", "text":
        "Tasarım referansı: Google Keep'in kart düzeni, sabitlenen notlar üstte.",
        "items": [], "labels": ["tasarım"], "color": "PURPLE", "pinned": True,
        "archived": False, "trashed": False, "updated": NOW - 7000, "created": NOW - 60000,
    },
]


def main() -> None:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 7.0
    _setup_tls()
    _enable_dpi()
    root = tk.Tk()
    root.title("KeepDesk self test")
    root.geometry("1180x760")
    theme.apply_theme(root)
    try:
        root.tk.call("tk", "scaling", max(1.0, root.winfo_fpixels("1i") / 72.0))
    except tk.TclError:
        pass

    service = KeepService(root.after, device_id="0123456789abcdef")
    service.email = "ornek.hesap@gmail.com"
    service.status = "ok"
    service.last_sync = time.time()
    service.prime_cache({
        "email": service.email,
        "notes": SAMPLE,
        "labels": [
            {"id": "l1", "name": "ev"},
            {"id": "l2", "name": "iş"},
            {"id": "l3", "name": "kişisel"},
            {"id": "l4", "name": "okuma"},
            {"id": "l5", "name": "tasarım"},
        ],
    })

    window = MainWindow(root, app=window_app(service), service=service)
    window.pack(fill="both", expand=True)
    root.lift()
    root.focus_force()
    root.attributes("-topmost", True)
    root.after(1800, lambda: root.attributes("-topmost", False))

    def dump_geometry() -> None:
        with open(os.path.join(ROOT, "tmp", "window.txt"), "w", encoding="utf-8") as fh:
            fh.write(f"{root.winfo_rootx()},{root.winfo_rooty()},"
                     f"{root.winfo_width()},{root.winfo_height()}")

    root.after(2500, dump_geometry)
    root.after(int(seconds * 1000), root.destroy)
    root.mainloop()


class _DummyApp:
    def __init__(self, service):
        self.service = service

    def open_note(self, *args, **kwargs):
        pass

    def show_note_menu(self, *args, **kwargs):
        pass

    def logout(self):
        pass


def window_app(service):
    return _DummyApp(service)


if __name__ == "__main__":
    main()
