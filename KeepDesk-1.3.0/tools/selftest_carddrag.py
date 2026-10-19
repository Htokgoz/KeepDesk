"""Card drag & drop reordering checks.

    python tools/selftest_carddrag.py
"""

from __future__ import annotations

import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "vendor"))

os.environ["APPDATA"] = os.path.join(ROOT, "tmp", "appdata-carddrag")
os.environ.setdefault("TMP", os.path.join(ROOT, "tmp"))
os.environ.setdefault("TEMP", os.path.join(ROOT, "tmp"))
shutil.rmtree(os.environ["APPDATA"], ignore_errors=True)

from app.main import KeepDeskApp  # noqa: E402

NOW = time.time()
NOTES = [
    {"id": "n1", "kind": "note", "title": "Birinci", "text": "a", "items": [],
     "labels": [], "color": "YELLOW", "pinned": False, "archived": False,
     "trashed": False, "updated": NOW - 10, "created": NOW - 100},
    {"id": "n2", "kind": "note", "title": "İkinci", "text": "b", "items": [],
     "labels": [], "color": "BLUE", "pinned": False, "archived": False,
     "trashed": False, "updated": NOW - 20, "created": NOW - 200},
    {"id": "n3", "kind": "note", "title": "Üçüncü", "text": "c", "items": [],
     "labels": [], "color": "GREEN", "pinned": False, "archived": False,
     "trashed": False, "updated": NOW - 30, "created": NOW - 300},
]

failures: list[str] = []


def check(label: str, condition: bool) -> None:
    print(("  OK   " if condition else "  FAIL ") + label)
    if not condition:
        failures.append(label)


def main() -> int:
    app = KeepDeskApp()
    app.service.prime_cache({"email": "ornek@example.com", "labels": [], "notes": NOTES})

    def later() -> None:
        app._login_succeeded("ornek@example.com", "tok", True)
        window = app.main_window
        window._render()
        app.update_idletasks()
        app.update()

        cards = {card.note["id"]: card for card in window._card_widgets
                 if hasattr(card, "note")}
        check("üç kart çizildi", len(cards) == 3)
        order = [note["id"] for note in window._visible_notes()]
        check("başlangıç sırası güncelleme sırasına göre", order == ["n1", "n2", "n3"])

        # a plain click (no movement) still opens the editor
        cards["n1"].event_generate("<ButtonPress-1>", x=30, y=20)
        cards["n1"].event_generate("<ButtonRelease-1>", x=30, y=20)
        app.update_idletasks()
        app.update()
        check("tıklama notu açıyor", "n1" in window._editors)
        if "n1" in window._editors:
            window._editors.pop("n1").destroy()
        app.update()

        # drag n1 onto the right half of n2 -> n1 goes after n2
        src = cards["n1"]
        dst = cards["n2"]
        sx, sy = src.winfo_rootx(), src.winfo_rooty()
        dx, dy = dst.winfo_rootx(), dst.winfo_rooty()
        src.event_generate("<ButtonPress-1>", x=30, y=20)
        app.update()
        src.event_generate("<B1-Motion>", x=(dx - sx) + dst.winfo_width() - 12,
                           y=(dy - sy) + 20)
        app.update()
        src.event_generate("<ButtonRelease-1>", x=(dx - sx) + dst.winfo_width() - 12,
                           y=(dy - sy) + 20)
        app.update()
        app.update_idletasks()

        check("sürükleme sırası değiştirdi",
              window._card_order[:3] == ["n2", "n1", "n3"])
        check("sıra ayarlara yazıldı",
              window._settings().get("card_order")[:3] == ["n2", "n1", "n3"])
        check("sürükleme not açmadı", "n1" not in window._editors)

        # and it survives a rebuild
        window.destroy()
        app.update()
        window = None
        app._login_succeeded("ornek@example.com", "tok", True)
        window = app.main_window
        window._render()
        app.update_idletasks()
        app.update()
        check("yeniden açılışta sıra korundu",
              [note["id"] for note in window._visible_notes()][:3] == ["n2", "n1", "n3"])

        app.after(150, app._quit)

    app.after(500, later)
    app.mainloop()
    print("FAILURES:", failures if failures else "none")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
