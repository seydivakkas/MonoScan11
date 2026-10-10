"""MonoScan11: offline iPhone photo/session validator and COLMAP runner.

Python standard library only. COLMAP is an optional, independently installed
binary. No phone photos are uploaded; ARKit poses are NOT fed to COLMAP yet.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import struct
import subprocess
import sys
from pathlib import Path

from colmap_models import ModelError, export_ply, inspect_model
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
        "arkit_poses_used_by_colmap": False,
    }


def commands_for(root: Path, work: Path, colmap: str, mode: str, gpu: bool) -> list[list[str]]:
    images = str(root / "images")
    db = str(work / "database.db")
    sparse = str(work / "sparse")
    dense = str(work / "dense")
    commands = [
        [colmap, "feature_extractor", "--database_path", db, "--image_path", images,
         "--ImageReader.single_camera", "1", "--FeatureExtraction.use_gpu", "1" if gpu else "0"],
        [colmap, "exhaustive_matcher", "--database_path", db,
         "--FeatureMatching.use_gpu", "1" if gpu else "0"],
        [colmap, "mapper", "--database_path", db, "--image_path", images,
         "--output_path", sparse],
    ]
    if mode == "dense":
        commands.extend([
            [colmap, "image_undistorter", "--image_path", images,
             "--input_path", str(work / "sparse" / "0"), "--output_path", dense,
             "--output_type", "COLMAP", "--max_image_size", "2000"],
            [colmap, "patch_match_stereo", "--workspace_path", dense,
             "--workspace_format", "COLMAP", "--PatchMatchStereo.geom_consistency", "true"],
            [colmap, "stereo_fusion", "--workspace_path", dense,
             "--workspace_format", "COLMAP", "--input_type", "geometric",
             "--output_path", str(work / "fused.ply")],
            [colmap, "poisson_mesher", "--input_path", str(work / "fused.ply"),
             "--output_path", str(work / "mesh.ply")],
        ])
    return commands


def reconstruct(root: Path, *, colmap: str, mode: str, gpu: bool, dry_run: bool) -> list[list[str]]:
    root = root.resolve()
    validate(root)
    work = root / "reconstruction"
    commands = commands_for(root, work, colmap, mode, gpu)
    if dry_run:
        for cmd in commands:
            print(subprocess.list2cmdline(cmd))
        return commands
    if mode == "dense" and not gpu:
        raise SessionError("Dense MVS için uygun CUDA/GPU kurulumu doğrulanmalı; önce --mode sparse kullanın.")
    if not Path(colmap).is_file() and shutil.which(colmap) is None:
        raise SessionError("COLMAP bulunamadı. --colmap ile COLMAP.bat tam yolunu belirtin.")
    if work.exists() and any(work.iterdir()):
        raise SessionError("reconstruction klasörü dolu; mevcut sonuçlar silinmesin diye işlem durduruldu.")
    work.mkdir(exist_ok=True)
    (work / "sparse").mkdir(exist_ok=True)
    for i, cmd in enumerate(commands):
        if mode == "dense" and i == 3 and not (work / "sparse" / "0").is_dir():
            raise SessionError("Seyrek COLMAP modeli sparse/0 altında bulunamadı; dense durduruldu.")
        print(f"[{i + 1}/{len(commands)}] {cmd[1]}", flush=True)
        subprocess.run(cmd, check=True)
        if i == 2 and not (work / "sparse" / "0" / "points3D.bin").is_file():
            raise SessionError("COLMAP geçerli bir sparse/0 modeli oluşturmadı (nokta dosyası yok).")
    try:
        report = inspect_model(work / "sparse" / "0")
    except (ModelError, OSError) as exc:
        raise SessionError(f"COLMAP çıktı modeli incelenemedi: {exc}") from exc
    if report["registered_images"] < 2 or report["point_count"] == 0:
        raise SessionError("COLMAP yeterli sahne modeli oluşturamadı (en az iki kamera ve bir 3D nokta gerekli).")
    (work / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return commands


def _model_dir(argument: Path) -> Path:
    path = argument.resolve()
    if (path / "images.bin").exists():
        return path
    return path / "reconstruction" / "sparse" / "0"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MonoScan11 offline Windows SfM/3D araçları")
    sub = parser.add_subparsers(dest="action", required=True)
    val = sub.add_parser("validate", help="Görüntüleri ve isteğe bağlı ARKit manifestini doğrula")
    val.add_argument("session", type=Path)
    rec = sub.add_parser("reconstruct", help="COLMAP ile gerçek fotoğraflardan SfM/MVS çalıştır")
    rec.add_argument("session", type=Path)
    rec.add_argument("--colmap", default="colmap", help="Örn: C:\\COLMAP\\COLMAP.bat")
    rec.add_argument("--mode", choices=["sparse", "dense"], default="sparse")
    rec.add_argument("--gpu", action="store_true", help="CUDA destekli GPU özellik çıkarımı/eşleme")
    rec.add_argument("--dry-run", action="store_true", help="Dosya değiştirmeden komutları göster")
    ins = sub.add_parser("inspect", help="COLMAP sparse çıktısındaki kayıtlı kare/nokta sayısını göster")
    ins.add_argument("session_or_model", type=Path)
    ins.add_argument("--export-ply", type=Path, help="3D görüntüleyicide açmak için PLY oluştur")
    demo = sub.add_parser("demo", help="Gerçek tarama değil, iki kamera triangulation sentetik deneyi")
    demo.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.action == "validate":
            result = validate(args.session)
        elif args.action == "reconstruct":
            reconstruct(args.session, colmap=args.colmap, mode=args.mode,
                        gpu=args.gpu, dry_run=args.dry_run)
            return 0
        elif args.action == "inspect":
            folder = _model_dir(args.session_or_model)
            result = inspect_model(folder)
            if args.export_ply:
                export_ply(folder, args.export_ply)
                result["exported_ply"] = str(args.export_ply)
        else:
            if any((args.output / name).exists() for name in ("synthetic_points.ply", "metrics.json")):
                raise SessionError("Demo çıktıları zaten var; üzerine yazılmadı")
            result = synthetic_demo(args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (SessionError, GeometryError, ModelError, subprocess.CalledProcessError, OSError) as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
