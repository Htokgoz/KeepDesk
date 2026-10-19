"""Small JSON settings store with Windows DPAPI encryption for secrets."""

from __future__ import annotations

import base64
import ctypes
import json
import os
import secrets
from ctypes import wintypes
from typing import Any

from .paths import data_path

_CRYPTPROTECT_UI_FORBIDDEN = 0x01


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _make_blob(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buf = ctypes.create_string_buffer(data, max(len(data), 1))
    blob = _DataBlob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    return blob, buf


def dpapi_protect(plain: str) -> str:
    """Encrypt a string with the current Windows user account (DPAPI)."""
    if not plain:
        return ""
    try:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p

        blob_in, _keep = _make_blob(plain.encode("utf-8"))
        blob_out = _DataBlob()
        ok = crypt32.CryptProtectData(
            ctypes.byref(blob_in),
            "KeepDesk",
            None,
            None,
            None,
            _CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(blob_out),
        )
        if not ok:
            raise ctypes.WinError()
        try:
            raw = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)
        return "dpapi:" + base64.b64encode(raw).decode("ascii")
    except Exception:
        # Never lose the value because of an unavailable crypto API.
        return "plain:" + base64.b64encode(plain.encode("utf-8")).decode("ascii")


def dpapi_unprotect(stored: str) -> str:
    if not stored:
        return ""
    if stored.startswith("plain:"):
        try:
            return base64.b64decode(stored[6:]).decode("utf-8")
        except Exception:
            return ""
    if not stored.startswith("dpapi:"):
        return stored
    try:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p

        raw = base64.b64decode(stored[6:])
        blob_in, _keep = _make_blob(raw)
        blob_out = _DataBlob()
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(blob_in),
            None,
            None,
            None,
            None,
            _CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(blob_out),
        )
        if not ok:
            raise ctypes.WinError()
        try:
            data = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)
        return data.decode("utf-8")
    except Exception:
        return ""


class Settings:
    """Tiny key/value store persisted next to the offline cache."""

    def __init__(self) -> None:
        self.path = data_path("settings.json")
        self.data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                self.data = loaded
        except (OSError, ValueError):
            self.data = {}

    def save(self) -> None:
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            # Last resort: try a direct write.
            try:
                with open(self.path, "w", encoding="utf-8") as fh:
                    json.dump(self.data, fh, ensure_ascii=False, indent=2)
            except OSError:
                pass

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any, save: bool = True) -> None:
        self.data[key] = value
        if save:
            self.save()

    # -- secrets ---------------------------------------------------------
    @property
    def email(self) -> str:
        return str(self.get("email", ""))

    @email.setter
    def email(self, value: str) -> None:
        self.set("email", value)

    @property
    def master_token(self) -> str:
        return dpapi_unprotect(str(self.get("master_token", "")))

    @master_token.setter
    def master_token(self, value: str) -> None:
        self.set("master_token", dpapi_protect(value))

    @property
    def device_id(self) -> str:
        value = str(self.get("device_id", ""))
        if len(value) != 16:
            value = secrets.token_hex(8)
            self.set("device_id", value)
        return value

    def clear_account(self) -> None:
        for key in ("email", "master_token"):
            self.data.pop(key, None)
        self.save()


def load_cache() -> dict | None:
    path = data_path("cache.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and "notes" in data:
            return data
    except (OSError, ValueError):
        pass
    return None


def save_cache(payload: dict) -> None:
    path = data_path("cache.json")
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        pass
