"""Generate PNG icons for PWA from SVG (requires: pip install pillow)."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "icebeach-wakeclub" / "apps" / "dashboard" / "public" / "icons"


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def write_png(path: Path, size: int, rgba: tuple[int, int, int, int]) -> None:
    width = height = size
    r, g, b, a = rgba
    row = b"\x00" + bytes((r, g, b, a)) * width
    raw = row * height

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", ihdr)
    png += _chunk(b"IDAT", zlib.compress(raw, 9))
    png += _chunk(b"IEND", b"")
    path.write_bytes(png)


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    # Brand gradient-ish solid tiles (simple; replace with real design later)
    write_png(ROOT / "icon-192.png", 192, (16, 35, 58, 255))
    write_png(ROOT / "icon-512.png", 512, (16, 35, 58, 255))
    print(f"Wrote {ROOT / 'icon-192.png'}")
    print(f"Wrote {ROOT / 'icon-512.png'}")


if __name__ == "__main__":
    main()
