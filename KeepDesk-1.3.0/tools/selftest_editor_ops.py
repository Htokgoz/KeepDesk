"""Exercise the editor's interactions without a real account.

    python tools/selftest_editor_ops.py
"""

from __future__ import annotations

import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "vendor"))

os.environ.setdefault("TMP", os.path.join(ROOT, "tmp"))
os.environ.setdefault("TEMP", os.path.join(ROOT, "tmp"))

import tkinter as tk  # noqa: E402

from app import theme  # noqa: E402
from app.service import KeepService  # noqa: E402
from app.ui.editor import NoteEditor  # noqa: E402

LIST_NOTE = {
    "id": "n2", "kind": "list", "title": "Liste", "text": "",
    "items": [{"id": "i1", "text": "bir", "checked": True},
              {"id": "i2", "text": "iki", "checked": False}],
    "labels": ["iş"], "color": "DEFAULT", "pinned": True,
    "archived": False, "trashed": False, "updated": 0, "created": 0,
}

TEXT_NOTE = {
    "id": "n1", "kind": "note", "title": "Not", "text": "ilk satır\nikinci",
    "items": [], "labels": [], "color": "BLUE", "pinned": False,
    "archived": False, "trashed": False, "updated": 0, "created": 0,
}

failures: list[str] = []


def check(label: str, fn) -> None:
    try:
        fn()
        print(f"  OK   {label}")
    except Exception:
        failures.append(label)
        print(f"  FAIL {label}")
        traceback.print_exc()


def main() -> int:
    root = tk.Tk()
    root.withdraw()
    theme.apply_theme(root)

    service = KeepService(root.after, device_id="0" * 16)
    service.update = lambda *a, **k: None
    service.set_items = lambda *a, **k: None
    service.convert = lambda *a, **k: None
    service.set_labels = lambda *a, **k: None

    # --- checklist editor ------------------------------------------------
    editor = NoteEditor(root, service, LIST_NOTE)
    root.update()

    for color in theme.NOTE_COLOR_ORDER:
        check(f"renk {color}", lambda c=color: (editor._set_color(c), root.update()))

    check("satır işaretle", lambda: editor._set_checked(editor._rows[1], True))
    check("satır ekle", lambda: editor._append_item("üç", focus=False))
    check("satır sil", lambda: editor._remove_item(editor._rows[-1]))
    check("başlık düzenle", lambda: (editor.title_var.set("Yeni başlık"), editor._flush()))
    check("etiket çipleri", editor._render_label_chips)

    def open_picker() -> None:
        service.prime_cache({"labels": [{"id": "l1", "name": "ev"},
                                        {"id": "l2", "name": "iş"}], "notes": []})
        editor._pick_labels()
        root.update()
        pickers = [w for w in editor.winfo_children() if isinstance(w, tk.Toplevel)]
        assert pickers, "etiket seçici açılmadı"
        pickers[0]._close()

    check("etiket seçici aç/kapat", open_picker)
    check("liste editörünü kapat", editor._close)
    root.update()

    # --- text editor -----------------------------------------------------
    note_editor = NoteEditor(root, service, TEXT_NOTE)
    root.update()
    check("gövde metni", lambda: note_editor.text.insert("end", "\nüçüncü"))
    check("gövde kaydı", note_editor._flush)
    check("not editörünü kapat", note_editor._close)
    root.update()

    root.destroy()
    print("FAILURES:", failures if failures else "none")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
