# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for a folder build (used for local verification)."""

import os

ROOT = os.path.abspath(SPECPATH)
VENDOR = os.path.join(ROOT, "vendor")


def meta_datas(vendor: str) -> list:
    """Bundle wheel metadata so importlib.metadata works in the frozen app."""
    items = []
    if os.path.isdir(vendor):
        for entry in os.listdir(vendor):
            if entry.endswith((".dist-info", ".egg-info")):
                items.append((os.path.join(vendor, entry), entry))
    return items


hidden = [
    "gkeepapi",
    "gkeepapi.node",
    "gpsoauth",
    "gpsoauth.google",
    "gpsoauth.util",
    "Cryptodome",
    "Cryptodome.Cipher",
    "Cryptodome.Cipher.PKCS1_OAEP",
    "Cryptodome.Cipher._pkcs1_oaep",
    "Cryptodome.PublicKey",
    "Cryptodome.PublicKey.RSA",
    "Cryptodome.PublicKey._openssl",
    "Cryptodome.Math",
    "Cryptodome.Math._IntegerGMP",
    "Cryptodome.Math._IntegerNative",
    "Cryptodome.Util",
    "Cryptodome.Util.number",
    "Cryptodome.Util.py3compat",
    "requests",
    "urllib3",
    "certifi",
    "charset_normalizer",
    "idna",
    "future",
    "past.builtins",
]

a = Analysis(
    ["run.py"],
    pathex=[ROOT, VENDOR],
    binaries=[],
    datas=[("assets", "assets")] + meta_datas(VENDOR),
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "numpy", "pandas", "matplotlib", "scipy", "PIL", "pytest",
        "tkinter.test", "test", "pydoc_data", "setuptools", "pip",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KeepDesk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=os.path.join(ROOT, "assets", "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="KeepDesk",
)

