"""MonoScan11 offline session validation, geometry demo and native SfM CLI."""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path

from geometry import GeometryError, synthetic_demo

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
HEIC_SUFFIXES = {".heic", ".heif"}


class SessionError(ValueError):
    pass


def image_files(root: Path) -> list[Path]:
    folder = root / "images"
    if not folder.is_dir():
        raise SessionError(f"Görüntü klasörü bulunamadı: {folder}")
    items = sorted(p for p in folder.iterdir() if p.is_file())
    photos = [p for p in items if p.suffix.lower() in IMAGE_SUFFIXES]
    if not photos and any(p.suffix.lower() in HEIC_SUFFIXES for p in items):
        raise SessionError("HEIC/HEIF görüntüler bulundu. Önce JPEG/PNG'ye dönüştürün; iPhone Kamera > Biçimler > En Uyumlu.")
    return photos


def image_dimensions(path: Path) -> tuple[int, int]:
    """Verify PNG/JPEG header and dimensions without external image libraries.

    This is *not* a full entropy/CRC decoder. COLMAP still performs decoding.
    """
    try:
        with path.open("rb") as fh:
            header = fh.read(24)
            if header.startswith(b"\x89PNG\r\n\x1a\n"):
                if len(header) < 24 or header[12:16] != b"IHDR":
                    raise SessionError(f"Geçersiz PNG başlığı: {path.name}")
                width, height = struct.unpack(">II", header[16:24])
                if not width or not height or width > 50_000 or height > 50_000:
                    raise SessionError(f"Geçersiz PNG boyutları: {path.name}")
                return width, height
            if header[:2] != b"\xff\xd8":
                raise SessionError(f"Geçersiz JPEG/PNG başlığı: {path.name}")
            fh.seek(2)
            while True:
                marker = fh.read(1)
                if not marker:
                    raise SessionError(f"JPEG boyut bilgisi okunamadı: {path.name}")
                if marker != b"\xff":
                    raise SessionError(f"JPEG segment işaretçisi bozuk: {path.name}")
                while marker == b"\xff":
                    marker = fh.read(1)
                if not marker:
                    raise SessionError(f"JPEG işaretçisi eksik: {path.name}")
                code = marker[0]
                if code in (0xD8, 0x01) or 0xD0 <= code <= 0xD7:
                    continue
                if code in (0xD9, 0xDA):
                    raise SessionError(f"JPEG SOF boyut bilgisi eksik: {path.name}")
                length_raw = fh.read(2)
                if len(length_raw) != 2:
                    raise SessionError(f"JPEG segment uzunluğu eksik: {path.name}")
                length = struct.unpack(">H", length_raw)[0]
                if length < 2:
                    raise SessionError(f"Geçersiz JPEG segmenti: {path.name}")
                if code in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                            0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    data = fh.read(5)
                    if len(data) < 5:
                        raise SessionError(f"Eksik JPEG boyutları: {path.name}")
                    height, width = struct.unpack(">HH", data[1:5])
                    if width == 0 or height == 0:
                        raise SessionError(f"Sıfır boyutlu JPEG: {path.name}")
                    return width, height
                fh.seek(length - 2, 1)
    except OSError as exc:
        raise SessionError(f"Görüntü okunamadı ({path.name}): {exc}") from exc


def check_matrix(value: object, n: int, desc: str) -> None:
    if not isinstance(value, list) or len(value) != n:
        raise SessionError(f"{desc}: {n}x{n} matris bekleniyor")
    for row in value:
        if not isinstance(row, list) or len(row) != n or any(
            isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
            for x in row
        ):
            raise SessionError(f"{desc}: sonlu sayılardan oluşan {n}x{n} matris bekleniyor")


def check_camera(frame: dict, index: int) -> None:
    k = frame["intrinsics"]
    pose = frame["cameraToWorld"]
    if k[0][0] <= 0 or k[1][1] <= 0:
        raise SessionError(f"frames[{index}]: odak uzaklığı (fx/fy) pozitif olmalı")
    if any(abs(k[2][i] - ref) > 1e-3 for i, ref in enumerate((0, 0, 1))):
        raise SessionError(f"frames[{index}]: K matrisinin son satırı geçersiz")
    if any(abs(pose[3][i] - ref) > 1e-3 for i, ref in enumerate((0, 0, 0, 1))):
        raise SessionError(f"frames[{index}]: kamera dönüşümünün son satırı geçersiz")
    # Check rotation columns approximate orthogonality and determinant +1.
    columns = [[pose[r][c] for r in range(3)] for c in range(3)]
    for i in range(3):
        n = sum(x * x for x in columns[i])
        if abs(n - 1) > 0.03:
            raise SessionError(f"frames[{index}]: kamera dönüşümü rijit değil")
        for j in range(i + 1, 3):
            if abs(sum(a * b for a, b in zip(columns[i], columns[j]))) > 0.03:
                raise SessionError(f"frames[{index}]: kamera dönüşümü ortogonal değil")
    a, b, c = columns
    det = a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])
    if abs(det - 1) > 0.04:
        raise SessionError(f"frames[{index}]: kamera dönüşümünün yönü geçersiz")


def validate(root: Path) -> dict:
    root = root.resolve()
    files = image_files(root)
    if len(files) < 3:
        raise SessionError("SfM denemesi için en az 3 görüntü gerekir (öneri: 30–100).")
    file_names = {p.name for p in files}
    if len({p.name.casefold() for p in files}) != len(files):
        raise SessionError("Aynı adlı (büyük/küçük harf farkıyla) görüntüler bulundu")
    dims = {p.name: image_dimensions(p) for p in files}
    manifest = root / "session.json"
    warnings = []
    if len(files) < 30:
        warnings.append("30'dan az görüntü var; rekonstrüksiyon başarısız olabilir.")
    heic_count = sum(p.suffix.lower() in HEIC_SUFFIXES for p in (root / "images").iterdir() if p.is_file())
    if heic_count:
        warnings.append(f"{heic_count} HEIC/HEIF görüntüsü atlandı; JPEG/PNG'ye dönüştürün.")

    nposes = 0
    if manifest.is_file():
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        except (ValueError, UnicodeDecodeError) as exc:
            raise SessionError(f"session.json okunamadı: {exc}") from exc
        if not isinstance(payload, dict) or payload.get("schemaVersion") != 1:
            raise SessionError("Desteklenmeyen session.json şema sürümü")
        frames = payload.get("frames")
        if not isinstance(frames, list) or not frames:
            raise SessionError("session.json içinde frames bulunamadı")
        recorded = []
        last_time = -math.inf
        for i, frame in enumerate(frames):
            if not isinstance(frame, dict):
                raise SessionError(f"frames[{i}] geçersiz")
            name = frame.get("file")
            if not isinstance(name, str) or Path(name).name != name or name not in file_names or "/" in name or "\\" in name:
                raise SessionError(f"frames[{i}]: görüntü adı bulunamadı veya güvenli değil")
            recorded.append(name)
            width, height = frame.get("width"), frame.get("height")
            if any(type(v) is not int or v <= 0 for v in (width, height)):
                raise SessionError(f"frames[{i}]: piksel boyutları geçersiz")
            if dims[name] != (width, height):
                raise SessionError(f"frames[{i}]: JPEG/PNG ve JSON görüntü boyutları uyuşmuyor: {name}")
            check_matrix(frame.get("intrinsics"), 3, f"frames[{i}].intrinsics")
            check_matrix(frame.get("cameraToWorld"), 4, f"frames[{i}].cameraToWorld")
            check_camera(frame, i)
            timestamp = frame.get("timestamp")
            if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
                raise SessionError(f"frames[{i}]: zaman damgası geçersiz")
            if timestamp <= last_time:
                raise SessionError(f"frames[{i}]: zaman damgaları artan sırada olmalı")
            last_time = timestamp
        if len(recorded) != len(set(recorded)):
            raise SessionError("session.json içinde tekrar eden görüntü isimleri var")
        if set(recorded) != file_names:
            raise SessionError("session.json ile images klasörünün içeriği uyuşmuyor")
        nposes = len(frames)
    else:
        warnings.append("session.json yok: yalnızca fotoğraf tabanlı SfM kullanılabilir.")
    return {
        "images": len(files),
        "pose_records": nposes,
        "image_formats": {ext: sum(p.suffix.lower() == ext for p in files) for ext in sorted({p.suffix.lower() for p in files})},
        "image_total_mb": round(sum(p.stat().st_size for p in files) / 1_048_576, 3),
        "warnings": warnings,
        "arkit_poses_used_by_native": False,
    }


def main(argv: list[str] | None = None) -> int:
    """Legacy entrypoint retained for validate/demo; reconstruction is native."""
    parser = argparse.ArgumentParser(description="MonoScan11 yerel, COLMAP'sız SfM araçları")
    subs = parser.add_subparsers(dest="action", required=True)
    val = subs.add_parser("validate", help="Fotoğrafları ve ARKit manifestini doğrula")
    val.add_argument("session", type=Path)
    rec = subs.add_parser("reconstruct", help="MonoScan11 native sparse SfM; photo-only or ARKit-guided")
    rec.add_argument("session", type=Path)
    rec.add_argument("--mode", choices=["photo-only", "arkit-guided"], default="photo-only")
    rec.add_argument("--focal-px", type=float, default=None,
                     help="session.json yoksa kalibre edilmiş odak uzunluğu (piksel)")
    rec.add_argument("--dry-run", action="store_true")
    ins = subs.add_parser("inspect", help="Native rekonstrüksiyon klasörü özetini oku")
    ins.add_argument("run", type=Path)
    alignment = subs.add_parser("align-arkit", help="PHOTO_ONLY kameralarını ARKit VIO'ya Sim(3) ile hizala; yalnız tanı")
    alignment.add_argument("run", type=Path)
    alignment.add_argument("session", type=Path)
    demo = subs.add_parser("demo", help="Sentetik iki-kamera geometri demosu")
    demo.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.action == "validate":
            result = validate(args.session)
        elif args.action == "reconstruct":
            result = validate(args.session)
            if args.dry_run:
                print(json.dumps({"engine": "monoscan-native", "mode": args.mode,
                                  "input_images": result["images"], "executed": False},
                                 indent=2, ensure_ascii=True))
                return 0
            # Import only for reconstruction; validate/demo keep their Python-stdlib contract.
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            from monoscan_core.reconstruction import ReconstructionError, reconstruct
            from monoscan_core.vision import VisionError
            from monoscan_core.camera import CameraGeometryError
            from monoscan_core.arkit_fusion import ARKitFusionError
            try:
                if args.mode == "arkit-guided":
                    if args.focal_px is not None:
                        raise SessionError("--focal-px is incompatible with arkit-guided mode")
                    from monoscan_core.arkit_guided import reconstruct_arkit_guided
                    output, summary = reconstruct_arkit_guided(args.session)
                else:
                    output, summary = reconstruct(args.session, focal_px=args.focal_px)
            except (ReconstructionError, VisionError, CameraGeometryError, ARKitFusionError) as exc:
                raise SessionError(str(exc)) from exc
            print(json.dumps({"run": str(output), **summary}, indent=2, ensure_ascii=True))
            return 0
        elif args.action == "align-arkit":
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            from monoscan_core.arkit_fusion import ARKitFusionError, align_run_to_arkit
            try:
                result = align_run_to_arkit(args.run, args.session)
            except ARKitFusionError as exc:
                raise SessionError(str(exc)) from exc
        elif args.action == "inspect":
            folder = args.run.resolve()
            if not folder.is_dir() or not all((folder / p).is_file()
                    for p in ("summary.json", "cameras.json", "tracks.json", "sparse.ply")):
                raise SessionError("Native model output incomplete; pass explicit run directory")
            result = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
            if result.get("engine") != "monoscan-native":
                raise SessionError("Output does not belong to MonoScan11 native engine")
        else:
            if any((args.output / name).exists() for name in ("synthetic_points.ply", "metrics.json")):
                raise SessionError("Demo çıktıları zaten var; üzerine yazılmadı")
            result = synthetic_demo(args.output)
        print(json.dumps(result, ensure_ascii=True, indent=2))
    except (SessionError, GeometryError, OSError, ValueError) as exc:
        print(("HATA: " + str(exc)).encode("ascii", errors="backslashreplace").decode("ascii"), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
