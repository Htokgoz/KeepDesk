"""Render the login screen for a visual check: ``python tools/selftest_login.py``."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "vendor"))

import tkinter as tk  # noqa: E402

from app import theme  # noqa: E402
from app.main import _enable_dpi  # noqa: E402
from app.service import KeepService  # noqa: E402
from app.ui.login import LoginView  # noqa: E402


def main() -> None:
    _enable_dpi()
    root = tk.Tk()
    root.title("KeepDesk login test")
    root.geometry("1000x720")
    theme.apply_theme(root)
    try:
        root.tk.call("tk", "scaling", max(1.0, root.winfo_fpixels("1i") / 72.0))
    except tk.TclError:
        pass

    service = KeepService(root.after, device_id="0123456789abcdef")
    view = LoginView(root, service, lambda *a: None, lambda *a: None)
    view.pack(fill="both", expand=True)
    view.prefill("ornek.hesap@gmail.com")
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode:
        view.set_mode(mode)
    root.lift()
    root.attributes("-topmost", True)
    root.after(1800, lambda: root.attributes("-topmost", False))

    def dump() -> None:
        with open(os.path.join(ROOT, "tmp", "window.txt"), "w", encoding="utf-8") as fh:
            fh.write(f"{root.winfo_rootx()},{root.winfo_rooty()},"
                     f"{root.winfo_width()},{root.winfo_height()}")

    root.after(2000, dump)
    root.after(22000, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
