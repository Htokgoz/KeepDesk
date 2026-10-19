"""Application entry point."""

from __future__ import annotations

import ctypes
import logging
import logging.handlers
import os
import re
import sys
import time
import tkinter as tk
import traceback
from tkinter import messagebox

# -- make the vendored wheels importable when running from source ---------
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VENDOR = os.path.join(_ROOT, "vendor")
if not getattr(sys, "frozen", False) and os.path.isdir(_VENDOR):
    if _VENDOR not in sys.path:
        sys.path.insert(0, _VENDOR)

from . import __version__, theme  # noqa: E402
from .paths import asset_path, data_path  # noqa: E402
from .service import AuthError, KeepService, ServiceError  # noqa: E402
from .store import Settings, load_cache  # noqa: E402
from .ui.login import LoginView  # noqa: E402
from .ui.mainwindow import MainWindow  # noqa: E402

log = logging.getLogger("keepdesk")


def _setup_logging() -> None:
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    try:
        handler = logging.handlers.RotatingFileHandler(
            data_path("keepdesk.log"), maxBytes=512_000, backupCount=2, encoding="utf-8"
        )
        handler.setFormatter(fmt)
        log.addHandler(handler)
    except OSError:
        pass
    logging.getLogger("gkeepapi").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def _setup_tls() -> None:
    """Trust the bundled CA list (public roots + this machine's enterprise CAs)."""
    bundle = asset_path("ca-bundle.pem")
    if os.path.exists(bundle):
        os.environ.setdefault("REQUESTS_CA_BUNDLE", bundle)
        os.environ.setdefault("SSL_CERT_FILE", bundle)


def _enable_dpi() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("KeepDesk.Desktop")
    except Exception:
        pass


def _find_windows(title_prefix: str) -> list[tuple[int, str]]:
    """Visible top-level windows whose title starts with ``title_prefix``."""
    try:
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        found: list[tuple[int, str]] = []
        enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                if buffer.value.startswith(title_prefix):
                    found.append((int(hwnd), buffer.value))
            return True

        user32.EnumWindows(enum_proc(callback), 0)
        return found
    except Exception:
        log.debug("window enumeration failed", exc_info=True)
        return []


def _handle_running_instance(current_title: str) -> str:
    """Deal with another KeepDesk window before starting a fresh one.

    Returns ``"none"`` (no window), ``"raised"`` (same build, brought forward)
    or ``"closed"`` (an older build was asked to quit so this one can start).
    """
    windows = [item for item in _find_windows("KeepDesk") if re.match(r"^KeepDesk \d", item[1])]
    if not windows:
        return "none"
    user32 = ctypes.windll.user32

    same = [(hwnd, title) for hwnd, title in windows if title.strip() == current_title]
    if same:
        hwnd = same[0][0]
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        user32.FlashWindow(hwnd, True)
        return "raised"

    # Only older builds are on screen: ask every one of them to quit so the new
    # version is the window the user actually sees.
    for hwnd, _title in windows:
        user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
    deadline = time.time() + 4.0
    while time.time() < deadline:
        if not any(user32.IsWindow(hwnd) for hwnd, _ in windows):
            break
        time.sleep(0.15)
    return "closed"


class KeepDeskApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.withdraw()
        self.title(f"KeepDesk {__version__}")
        self.configure(bg=theme.BG)
        self.minsize(940, 620)
        theme.apply_theme(self)
        try:
            self.tk.call("tk", "scaling", max(1.0, self.winfo_fpixels("1i") / 72.0))
        except tk.TclError:
            pass
        icon = asset_path("icon.ico")
        if os.path.exists(icon):
            try:
                self.iconbitmap(icon)
            except tk.TclError:
                pass

        geometry = self.settings_geometry()
        self.geometry(geometry)
        self.protocol("WM_DELETE_WINDOW", self._quit)
        self.report_callback_exception = self._report_callback_exception

        self.login_view: LoginView | None = None
        self.main_window: MainWindow | None = None

        self.service = KeepService(self._schedule, device_id=self.settings.device_id)
        self.service.on_update = self._on_update
        self.service.on_status = self._on_status
        self.service.on_auth_lost = self._on_auth_lost

        self.deiconify()
        if self.settings.get("maximized"):
            self.after(40, lambda: self.state("zoomed"))
        self.after(60, self._bootstrap)

    # -- helpers ---------------------------------------------------------
    @property
    def settings(self) -> Settings:
        if not hasattr(self, "_settings"):
            self._settings = Settings()
        return self._settings

    def settings_geometry(self) -> str:
        geometry = self.settings.get("geometry")
        if isinstance(geometry, str):
            match = re.match(r"^(\d+)x(\d+)([+-]\d+)([+-]\d+)$", geometry)
            if match:
                width, height = int(match.group(1)), int(match.group(2))
                x, y = int(match.group(3)), int(match.group(4))
                screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
                if width >= 900 and height >= 600:
                    # Keep the window on screen even if the display changed.
                    if x < -20 or x + width > screen_w + 20:
                        x = max(0, (screen_w - width) // 2)
                    if y < 0 or y + height > screen_h + 20:
                        y = max(0, (screen_h - height) // 3)
                    return f"{width}x{height}+{x}+{y}"
        width = min(1280, max(980, self.winfo_screenwidth() - 220))
        height = min(860, max(640, self.winfo_screenheight() - 180))
        x = (self.winfo_screenwidth() - width) // 2
        y = max(40, (self.winfo_screenheight() - height) // 3)
        return f"{width}x{height}+{x}+{y}"

    def _schedule(self, fn) -> None:
        try:
            self.after(0, fn)
        except tk.TclError:
            pass

    def _report_callback_exception(self, exc, val, tb) -> None:
        log.error("UI callback failed: %s", val, exc_info=(exc, val, tb))
        try:
            messagebox.showerror("Beklenmeyen hata", f"{val}", parent=self)
        except tk.TclError:
            pass

    # -- screens ---------------------------------------------------------
    def _clear_screens(self) -> None:
        if self.main_window is not None:
            try:
                self.main_window.close_editors()
            except tk.TclError:
                pass
        for window in (self.main_window, self.login_view):
            if window is not None:
                try:
                    window.destroy()
                except tk.TclError:
                    pass
        self.main_window = None
        self.login_view = None
        self.service.on_update = self._on_update

    def show_main(self) -> None:
        self._clear_screens()
        self.main_window = MainWindow(self, self, self.service)
        self.main_window.pack(fill="both", expand=True)
        self.bind("<Control-n>", lambda _e: self.main_window and self.main_window.new_note())
        self.bind("<Control-f>", lambda _e: self.main_window and self.main_window.search.focus())
        self.bind("<F5>", lambda _e: self.service.request_sync(0.0))

    def show_login(self, message: str = "") -> None:
        self._clear_screens()
        self.login_view = LoginView(self, self.service, self._login_succeeded, self._notice)
        self.login_view.pack(fill="both", expand=True)
        if message:
            self.login_view.message.configure(text=message)
        self.login_view.prefill(self.settings.email)

    # -- lifecycle -------------------------------------------------------
    def _bootstrap(self) -> None:
        email = self.settings.email
        token = self.settings.master_token
        cached = load_cache()

        if cached and cached.get("email") and cached.get("email") == email:
            self.service.prime_cache(cached)

        if email and token:
            self.service.email = email
            self.show_main()
            self.service.resume(email, token, self._resume_done)
        else:
            self.show_login()

    def _resume_done(self, result, error) -> None:
        if error is None:
            log.info("session restored")
            if self.main_window:
                self.main_window.refresh(force=True)
            return
        if isinstance(error, AuthError):
            log.warning("stored token rejected: %s", error)
            self.settings.master_token = ""
            self.show_login(str(error))
        else:
            log.warning("resume failed: %s", error)
            if self.main_window:
                self.main_window.toast.show(
                    "Çevrimdışı moddasınız — önbellekteki notlar gösteriliyor.", "error", 4000)
            else:
                self.show_login(str(error))

    def _login_succeeded(self, email: str, token: str, remember: bool) -> None:
        if remember and token:
            self.settings.email = email
            self.settings.master_token = token
        elif not remember:
            self.settings.email = email
            self.settings.master_token = ""
        self.service.email = email
        self.show_main()
        if self.main_window:
            self.main_window.refresh(force=True)
            self.main_window.toast.show("Google Keep'e bağlandı.", "ok")

    def logout(self) -> None:
        self.settings.clear_account()
        self.service.logout()
        self.show_login("Çıkış yapıldı.")

    # -- board actions delegated from the note cards ----------------------
    def open_note(self, note_id: str, fresh: dict | None = None) -> None:
        if self.main_window is not None:
            self.main_window.open_note(note_id, fresh)

    def show_note_menu(self, note: dict, x: int, y: int) -> None:
        if self.main_window is not None:
            self.main_window.show_note_menu(note, x, y)

    def show_label(self, name: str) -> None:
        if self.main_window is not None:
            self.main_window.set_view("label", name)

    def begin_card_drag(self, card) -> None:
        if self.main_window is not None:
            self.main_window.begin_card_drag(card)

    def update_card_drag(self, x_root: int, y_root: int) -> None:
        if self.main_window is not None:
            self.main_window.update_card_drag(x_root, y_root)

    def end_card_drag(self) -> None:
        if self.main_window is not None:
            self.main_window.end_card_drag()

    # -- service callbacks ------------------------------------------------
    def _on_update(self) -> None:
        if self.main_window is not None:
            self.main_window.refresh()

    def _on_status(self, _status: str) -> None:
        if self.main_window is not None:
            self.main_window.refresh()

    def _on_auth_lost(self, message: str) -> None:
        self.settings.master_token = ""
        self.show_login(message)

    def _notice(self, message: str) -> None:
        if self.main_window is not None:
            self.main_window.toast.show(message)

    def _quit(self) -> None:
        try:
            zoomed = self.state() == "zoomed"
            self.settings.set("maximized", zoomed)
            if not zoomed:
                self.settings.set("geometry", self.geometry())
            self.settings.save()
        except tk.TclError:
            pass
        try:
            self.service.shutdown()
        except Exception:
            pass
        self.destroy()


def main() -> int:
    _setup_logging()
    _setup_tls()
    _enable_dpi()
    state = _handle_running_instance(f"KeepDesk {__version__}")
    if state == "raised":
        log.info("already running; focused the existing window")
        return 0
    if state == "closed":
        log.info("closed an older KeepDesk window before starting")
    log.info("starting KeepDesk %s (python %s)", __version__, sys.version.split()[0])
    try:
        app = KeepDeskApp()
        app.mainloop()
    except Exception:
        log.exception("fatal error")
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("KeepDesk başlatılamadı",
                                 traceback.format_exc(limit=3))
            root.destroy()
        except Exception:
            pass
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
