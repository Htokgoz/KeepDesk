"""Label double-click + drag-to-reorder checks.

    python tools/selftest_labels.py
"""

from __future__ import annotations

import os
import sys
import time
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "vendor"))

os.environ["APPDATA"] = os.path.join(ROOT, "tmp", "appdata-labels")
os.environ.setdefault("TMP", os.path.join(ROOT, "tmp"))
os.environ.setdefault("TEMP", os.path.join(ROOT, "tmp"))

# start from a clean profile so a previous run's saved order cannot leak in
import shutil  # noqa: E402

shutil.rmtree(os.environ["APPDATA"], ignore_errors=True)

import tkinter as tk  # noqa: E402

from app import theme  # noqa: E402
from app.service import KeepService  # noqa: E402
from app.store import Settings  # noqa: E402
from app.ui.mainwindow import MainWindow  # noqa: E402

LABELS = [
    {"id": "l1", "name": "ev"},
    {"id": "l2", "name": "iş"},
    {"id": "l3", "name": "kişisel"},
    {"id": "l4", "name": "okuma"},
]

failures: list[str] = []


def check(label: str, condition: bool) -> None:
    print(("  OK   " if condition else "  FAIL ") + label)
    if not condition:
        failures.append(label)


class DummyApp:
    def __init__(self, service, settings):
        self.service = service
        self.settings = settings

    def open_note(self, *a, **k):
        pass

    def show_note_menu(self, *a, **k):
        pass

    def logout(self):
        pass


def build(root, service, settings) -> MainWindow:
    window = MainWindow(root, app=DummyApp(service, settings), service=service)
    window.pack(fill="both", expand=True)
    root.update()
    window._render()
    root.update()
    return window


def main() -> int:
    root = tk.Tk()
    root.geometry("1000x700")
    theme.apply_theme(root)

    settings = Settings()
    settings.set("label_order", "", save=True)
    settings.data.pop("label_order", None)

    service = KeepService(root.after, device_id="0123456789abcdef")
    service.email = "ornek@example.com"
    service.status = "ok"
    service.last_sync = time.time()
    service.prime_cache({"email": service.email, "notes": [], "labels": LABELS})

    window = build(root, service, settings)
    check("4 etiket listelendi", len(window._label_items) == 4)
    check("başlangıç sırası alfabetik",
          window._label_order == ["ev", "iş", "kişisel", "okuma"])

    item = window._label_items["ev"]
    check("etiket çift tık modunda", item.command_mode == "double")
    check("etiket sürüklenebilir", item.draggable is True)
    check("çift tık bağlaması var", bool(item._label.bind("<Double-Button-1>")))

    # --- drag "ev" below the last row -----------------------------------
    def row(name: str):
        return window._label_items[name]

    root.update_idletasks()
    # pointer well below every row -> drop at the end
    below = max(row(n).winfo_rooty() + row(n).winfo_height()
                for n in list(window._label_items)) + 40
    start_y = row("ev").winfo_rooty() + row("ev").winfo_height() // 2
    window._label_drag_start("ev", SimpleNamespace(y_root=start_y))
    window._label_drag_motion(SimpleNamespace(y_root=below))
    root.update()
    check("sürüklenen satır görünür kaldı", bool(row("ev").winfo_ismapped()))
    window._label_drag_end("ev", SimpleNamespace(y_root=below))
    root.update()

    check("sürükleme sırası güncelledi",
          window._label_order == ["iş", "kişisel", "okuma", "ev"])
    check("sıra ayarlara yazıldı",
          settings.get("label_order") == ["iş", "kişisel", "okuma", "ev"])
    packed = [w for w in window._labels_host.pack_slaves()]
    check("satırlar yeni sırayla paketlendi",
          [w._label.cget("text") for w in packed] == ["iş", "kişisel", "okuma", "ev"])

    # --- reorder back to the top (event timing independent) --------------
    window._label_order = [name for name in window._label_order if name != "ev"]
    window._label_order.insert(0, "ev")
    window._label_names = tuple(window._label_order)
    window._move_label_widget("ev", 0)
    window._save_label_order()
    root.update()
    check("yukarı taşıma çalıştı",
          window._label_order == ["ev", "iş", "kişisel", "okuma"])
    check("yukarı taşıma kaydedildi",
          settings.get("label_order") == ["ev", "iş", "kişisel", "okuma"])
    check("satır görünür kaldı", bool(row("ev").winfo_ismapped()))
    check("satırlar sırayla paketlendi",
          [w._label.cget("text") for w in window._labels_host.pack_slaves()]
          == ["ev", "iş", "kişisel", "okuma"])

    # put it back for the following checks
    window._label_order = [name for name in window._label_order if name != "ev"]
    window._label_order.append("ev")
    window._label_names = tuple(window._label_order)
    window._move_label_widget("ev", len(window._label_order) - 1)
    window._save_label_order()
    root.update()

    # --- order survives a rebuild ----------------------------------------
    window.destroy()
    root.update()
    window = build(root, service, settings)
    check("yeniden açılışta sıra korundu",
          window._label_order == ["iş", "kişisel", "okuma", "ev"])

    # --- single click must not navigate, double click must ----------------
    window.set_view("notes")
    root.update()
    first = window._label_items["iş"]
    first._label.event_generate("<Button-1>", x=6, y=6)
    root.update()
    check("tek tık gezinmiyor", window.view == "notes")
    # Tk refuses to synthesise "<Double-Button-1>", so call what it dispatches.
    first._click()
    root.update()
    check("çift tık etiketi açıyor",
          window.view == "label" and window.label_name == "iş")

    # --- a new label lands at the end ------------------------------------
    service.prime_cache({"email": service.email, "notes": [],
                         "labels": LABELS + [{"id": "l5", "name": "yeni"}]})
    window._sync_labels()
    root.update()
    check("yeni etiket sona eklendi",
          window._label_order == ["iş", "kişisel", "okuma", "ev", "yeni"])

    window.destroy()
    root.destroy()
    print("FAILURES:", failures if failures else "none")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
