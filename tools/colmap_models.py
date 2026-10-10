"""Minimal, dependency-free COLMAP binary sparse model inspection.

Reads images.bin and points3D.bin using COLMAP's documented binary layout.
No image data leaves the local machine. Read-only (except explicit PLY export).
"""

from __future__ import annotations

import math
import os
import struct
from pathlib import Path


class ModelError(ValueError):
    pass


def _read_exact(handle, size):
    data = handle.read(size)
    if len(data) != size:
        raise ModelError("COLMAP model dosyası eksik veya bozuk")
    return data


def _unpack(handle, fmt):
    return struct.unpack("<" + fmt, _read_exact(handle, struct.calcsize("<" + fmt)))


def _skip_exact(handle, size):
    """Skip fixed-length binary blocks without allowing silent seek past EOF."""
    if size < 0 or handle.tell() + size > os.fstat(handle.fileno()).st_size:
        raise ModelError("COLMAP model dosyasında eksik dizi veya iz kaydı")
    handle.seek(size, 1)


def _safe_count(value, max_count=10_000_000):
    if value > max_count:
        raise ModelError("COLMAP modeli beklenmeyen büyüklükte")
    return value


def image_names(path: Path):
    names = []
    with Path(path).open("rb") as handle:
        (count,) = _unpack(handle, "Q")
        _safe_count(count)
        for _ in range(count):
            _unpack(handle, "I4d3dI")  # image ID, quaternion, translation, camera ID
            name_bytes = bytearray()
            while True:
                c = _read_exact(handle, 1)
                if c == b"\x00":
                    break
                if len(name_bytes) > 4096:
                    raise ModelError("Çok uzun COLMAP görüntü adı")
                name_bytes.extend(c)
            names.append(name_bytes.decode("utf-8", errors="replace"))
            (n2d,) = _unpack(handle, "Q")
            _safe_count(n2d, 100_000_000)
            _skip_exact(handle, n2d * 24)  # x, y doubles and point3D_id signed int64
        if handle.read(1):
            raise ModelError("images.bin sonunda beklenmeyen veri")
    return names


def sparse_points(path: Path):
    """Stream (xyz, rgb, error) entries without storing large point clouds."""
    with Path(path).open("rb") as handle:
        (count,) = _unpack(handle, "Q")
        _safe_count(count, 100_000_000)
        for _ in range(count):
            record = _unpack(handle, "Q3d3BdQ")
            xyz = tuple(record[1:4])
            rgb = tuple(record[4:7])
            error = record[7]
            track_length = _safe_count(record[8], 100_000_000)
            _skip_exact(handle, track_length * 8)  # image_id + point2D_idx
            if not all(math.isfinite(x) for x in (*xyz, error)):
                raise ModelError("COLMAP nokta bulutunda sonlu olmayan sayı")
            yield xyz, rgb, error
        if handle.read(1):
            raise ModelError("points3D.bin sonunda beklenmeyen veri")


def inspect_model(folder: Path):
    folder = Path(folder)
    images = folder / "images.bin"
    points = folder / "points3D.bin"
    if not images.is_file() or not points.is_file():
        raise ModelError("COLMAP sparse klasöründe images.bin ve points3D.bin bulunmalı")
    image_list = image_names(images)
    number = 0
    errors = 0.0
    for _xyz, _rgb, reprojection_error in sparse_points(points):
        number += 1
        errors += reprojection_error
    return {
        "registered_images": len(image_list),
        "point_count": number,
        "mean_reprojection_error_px": errors / number if number else None,
        "registered_image_names": image_list,
        "metric_scale_known": False,
        "note": "SfM çıktısında metrik ölçek belirsizdir; gerçek doğruluk karşılaştırması yapılmadı.",
    }


def export_ply(folder: Path, destination: Path):
    """Export colored sparse COLMAP cloud; double pass to preserve low memory use."""
    folder = Path(folder)
    src = folder / "points3D.bin"
    if not src.is_file():
        raise ModelError("points3D.bin bulunamadı")
    with src.open("rb") as handle:
        (count,) = _unpack(handle, "Q")
        _safe_count(count, 100_000_000)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ModelError("PLY dosyası zaten var; üzerine yazılmadı")
    with destination.open("w", encoding="ascii", newline="\n") as out:
        out.write("ply\nformat ascii 1.0\ncomment COLMAP sparse SfM; arbitrary scale\n")
        out.write(f"element vertex {count}\nproperty float x\nproperty float y\nproperty float z\n")
        out.write("property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
        for xyz, rgb, _err in sparse_points(src):
            out.write(f"{xyz[0]:.9g} {xyz[1]:.9g} {xyz[2]:.9g} {rgb[0]} {rgb[1]} {rgb[2]}\n")
    return destination
