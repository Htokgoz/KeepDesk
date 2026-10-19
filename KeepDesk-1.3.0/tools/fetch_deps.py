"""Fetch wheels from PyPI without pip (the sandbox blocks pip's temp renames).

Selects the best wheel for this interpreter (CPython 3.14, win_amd64) and
extracts it into the target directory, recursively resolving dependencies.

Usage:
    python tools/fetch_deps.py --target vendor gkeepapi
    python tools/fetch_deps.py --target vendor_build pyinstaller
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import zipfile

import requests

PY_TAG = f"cp{sys.version_info.major}{sys.version_info.minor}"
ABI_TAG = PY_TAG
PLATFORM = "win_amd64"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _session() -> requests.Session:
    s = requests.Session()
    ca = os.environ.get("REQUESTS_CA_BUNDLE")
    if ca and os.path.exists(ca):
        s.verify = ca
    return s


def metadata(session: requests.Session, pkg: str) -> dict:
    resp = session.get(f"https://pypi.org/pypi/{pkg}/json", timeout=30)
    resp.raise_for_status()
    return resp.json()


def score(filename: str) -> tuple[int, int] | None:
    """Rank a wheel filename for compatibility with the running interpreter."""
    if not filename.endswith(".whl"):
        return None
    parts = filename[:-4].split("-")
    if len(parts) < 5:
        return None
    pytag, abitag, plat = parts[-3], parts[-2], parts[-1]
    py_tags = pytag.split(".")

    if abitag == "none":
        if not any(t in ("py3", "py2", PY_TAG) for t in py_tags):
            return None
    elif abitag == "abi3":
        if not all(t.startswith("cp3") for t in py_tags):
            return None
    elif abitag != ABI_TAG:
        return None

    if plat == "any":
        plat_score = 1
    elif plat.startswith(PLATFORM):
        plat_score = 3
    elif plat.startswith("win32"):
        plat_score = 2
    else:
        return None

    abi_score = 2 if abitag == ABI_TAG else (1 if abitag == "abi3" else 0)
    return (plat_score, abi_score)


def pick(json_data: dict) -> dict | None:
    wheels = [u for u in json_data["urls"] if u["packagetype"] == "bdist_wheel"]
    scored = [(score(u["filename"]), u) for u in wheels]
    scored = [(s, u) for s, u in scored if s is not None]
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def install(session: requests.Session, names: list[str], target: str) -> None:
    os.makedirs(target, exist_ok=True)
    wheel_dir = os.path.join(target, "_wheels")
    os.makedirs(wheel_dir, exist_ok=True)

    queue = list(names)
    seen: set[str] = set()
    while queue:
        pkg = queue.pop(0)
        key = pkg.lower().replace("_", "-")
        if key in seen:
            continue
        seen.add(key)

        data = metadata(session, pkg)
        info = data["info"]
        wheel = pick(data)
        if wheel is None:
            print(f"  !! no compatible wheel for {pkg} {info['version']}")
            continue
        print(f"  + {pkg} {info['version']}  ({wheel['filename']})")

        path = os.path.join(wheel_dir, wheel["filename"])
        if not os.path.exists(path):
            with session.get(wheel["url"], timeout=180, stream=True) as resp:
                resp.raise_for_status()
                with open(path, "wb") as fh:
                    for chunk in resp.iter_content(65536):
                        fh.write(chunk)
        with zipfile.ZipFile(path) as zf:
            zf.extractall(target)

        for dep in info.get("requires_dist") or []:
            if "extra ==" in dep:
                continue
            name = dep.split(";")[0].split("[")[0]
            for sep in ("<", ">", "=", "!", "~", "(", " "):
                name = name.split(sep)[0]
            name = name.strip()
            if name and name.lower() not in ("python",):
                queue.append(name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("packages", nargs="+")
    ap.add_argument("--target", default="vendor")
    ap.add_argument("--clean", action="store_true")
    args = ap.parse_args()

    target = os.path.join(ROOT, args.target) if not os.path.isabs(args.target) else args.target
    if args.clean and os.path.isdir(target):
        shutil.rmtree(target, ignore_errors=True)

    session = _session()
    print(f"installing into {target}")
    install(session, args.packages, target)
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
