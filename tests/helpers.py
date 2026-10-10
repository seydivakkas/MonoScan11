"""Small real PNG and COLMAP binary fixtures, no third-party dependencies."""

import struct
import zlib
from pathlib import Path


def png_bytes(width=16, height=12, color=(127, 80, 40)):
    def chunk(name, data):
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)
    rows = b"".join(b"\x00" + bytes(color) * width for _ in range(height))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def write_model(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "images.bin").open("wb") as out:
        out.write(struct.pack("<Q", 2))
        for i in (1, 2):
            out.write(struct.pack("<I4d3dI", i, 1, 0, 0, 0, float(i), 0, 0, 1))
            out.write(f"frame_{i:04d}.png".encode() + b"\0")
            out.write(struct.pack("<Q", 1))
            out.write(struct.pack("<ddq", 50.0, 70.0, 1))
    with (folder / "points3D.bin").open("wb") as out:
        out.write(struct.pack("<Q", 1))
        out.write(struct.pack("<Q3d3BdQ", 1, 1.0, 2.0, 3.0, 10, 20, 30, 0.25, 2))
        out.write(struct.pack("<IIII", 1, 0, 2, 0))
