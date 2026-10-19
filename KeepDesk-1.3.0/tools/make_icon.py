"""Generate the app icon (assets/icon.ico + icon.png) with no dependencies.

The mark is a Keep-style yellow rounded note with three lines.  Shapes are
rasterised at 4x and box-filtered down so the small sizes stay clean.
"""

from __future__ import annotations

import math
import os
import struct
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")

YELLOW = (0xF7, 0xB7, 0x33)
DARK = (0x3A, 0x2C, 0x05)


def rounded_rect_sdf(px, py, x0, y0, x1, y1, radius):
    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2
    hx = (x1 - x0) / 2 - radius
    hy = (y1 - y0) / 2 - radius
    dx = abs(px - cx) - hx
    dy = abs(py - cy) - hy
    outside = math.hypot(max(dx, 0), max(dy, 0))
    inside = min(max(dx, dy), 0)
    return outside + inside - radius


def segment_sdf(px, py, ax, ay, bx, by, radius):
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    length2 = vx * vx + vy * vy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / length2))
    dx, dy = px - (ax + t * vx), py - (ay + t * vy)
    return math.hypot(dx, dy) - radius


def render(size: int, ss: int = 4) -> list[bytearray]:
    w = size * ss
    margin = w * 0.045
    radius = w * 0.20
    line_r = w * 0.035
    rows: list[bytearray] = []
    lines = []
    for index, frac in enumerate((0.34, 0.50, 0.66)):
        length = w * (0.46 if index < 2 else 0.30)
        lines.append((w * 0.5 - length / 2, w * frac, w * 0.5 + length / 2, w * frac))

    for y in range(w):
        row = bytearray()
        for x in range(w):
            # Sample the centre of the high-res pixel.
            px, py = x + 0.5, y + 0.5
            d = rounded_rect_sdf(px, py, margin, margin, w - margin, w - margin, radius)
            if d > 0:
                row.extend((0, 0, 0, 0))
                continue
            shade = YELLOW
            for ax, ay, bx, by in lines:
                if segment_sdf(px, py, ax, ay, bx, by, line_r) <= 0:
                    shade = DARK
                    break
            row.extend((shade[0], shade[1], shade[2], 255))
        rows.append(row)

    # Box filter down to the target size.
    out: list[bytearray] = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            r = g = b = a = 0
            for sy in range(ss):
                src = rows[y * ss + sy]
                for sx in range(ss):
                    offset = (x * ss + sx) * 4
                    r += src[offset]
                    g += src[offset + 1]
                    b += src[offset + 2]
                    a += src[offset + 3]
            count = ss * ss
            row.extend((r // count, g // count, b // count, a // count))
        out.append(row)
    return out


def png_bytes(size: int, rows: list[bytearray]) -> bytes:
    raw = b"".join(b"\x00" + bytes(row) for row in rows)

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    os.makedirs(ASSETS, exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = {}
    for size in sizes:
        payload = png_bytes(size, render(size))
        images[size] = payload
        with open(os.path.join(ASSETS, f"icon-{size}.png"), "wb") as fh:
            fh.write(payload)
    with open(os.path.join(ASSETS, "icon.png"), "wb") as fh:
        fh.write(images[256])

    entries = []
    offset = 6 + 16 * len(sizes)
    blob = b""
    for size in sizes:
        payload = images[size]
        entries.append(
            struct.pack("<BBBBHHII", 0 if size == 256 else size, 0 if size == 256 else size,
                        0, 0, 1, 32, len(payload), offset)
        )
        offset += len(payload)
        blob += payload
    ico = struct.pack("<HHH", 0, 1, len(sizes)) + b"".join(entries) + blob
    with open(os.path.join(ASSETS, "icon.ico"), "wb") as fh:
        fh.write(ico)
    print("wrote", os.path.join(ASSETS, "icon.ico"), len(ico), "bytes")


if __name__ == "__main__":
    main()
