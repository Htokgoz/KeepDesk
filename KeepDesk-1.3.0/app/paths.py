"""Filesystem locations used by the app (works both from source and from a
PyInstaller bundle)."""

from __future__ import annotations

import os
import sys
import tempfile

APP_NAME = "KeepDesk"


def resource_dir() -> str:
    """Directory that holds bundled read-only resources (assets/)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def asset_path(*parts: str) -> str:
    return os.path.join(resource_dir(), "assets", *parts)


def _writable(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write-test")
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def data_dir() -> str:
    """Writable per-user directory for settings and the offline cache.

    Falls back to LOCALAPPDATA and finally the temp directory when the profile
    folder is read-only (roaming profiles, kiosk setups, sandboxes).
    """
    global _DATA_DIR
    if _DATA_DIR and os.path.isdir(_DATA_DIR):
        return _DATA_DIR

    candidates = []
    for env in ("APPDATA", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            candidates.append(os.path.join(base, APP_NAME))
    candidates.append(os.path.join(tempfile.gettempdir(), APP_NAME))
    candidates.append(os.path.join(os.path.expanduser("~"), "." + APP_NAME))

    for path in candidates:
        if _writable(path):
            _DATA_DIR = path
            return path
    _DATA_DIR = candidates[-1]
    return _DATA_DIR


_DATA_DIR = ""


def data_path(*parts: str) -> str:
    return os.path.join(data_dir(), *parts)
