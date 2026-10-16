"""N9 public real-iPhone-13 PHOTO_ONLY proxy: Pix4D Olympic Flame.

Public catalog: https://support.pix4d.com/hc/en-us/articles/360000235126
Published 117 JPEG 1440x1920 iPhone13 pictures, 208 MB project archive:
https://data.pix4d.com/misc/example_datasets/olympic_flame.zip

Pix4D says examples are for PERSONAL / PROFESSIONAL TRAINING only and
require attribution for commercial/promotional use. No license is accepted
implicitly. No direct ARKit pose/intrinsics are provided by this adapter.
Hence PHOTO_ONLY SfM requires a separately justified --focal-px.
Never report iPhone11/VIO/physical/metric acceptance for this capture.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import urllib.parse
import urllib.request
import zipfile

import cv2
import numpy as np


OFFICIAL_ZIP_URL = "https://data.pix4d.com/misc/example_datasets/olympic_flame.zip"
MAX_ZIP_BYTES = 350 * 1024**2
MAX_UNCOMPRESSED_BYTES = 1024**3


class IPhoneImageProxyError(ValueError):
    pass


def download_official_archive(destination, *, terms_reviewed=False):
    if not terms_reviewed:
        raise IPhoneImageProxyError("Review Pix4D training-only terms first")
    destination = Path(destination).resolve()
    if destination.exists():
        raise IPhoneImageProxyError("Refuse overwriting archive")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(".temp-"+destination.name)
    if temp.exists():
        raise IPhoneImageProxyError("Unfinished previous download must be inspected")
    try:
        req = urllib.request.Request(OFFICIAL_ZIP_URL, headers={"User-Agent": "MonoScan11-Research-N9"})
        with urllib.request.urlopen(req, timeout=90) as response:
            u = urllib.parse.urlparse(response.geturl())
            if u.scheme != "https" or u.hostname != "data.pix4d.com":
                raise IPhoneImageProxyError("Unexpected off-domain download")
            if int(response.headers.get("Content-Length") or 0) > MAX_ZIP_BYTES:
                raise IPhoneImageProxyError("Public ZIP exceeds size cap")
            n = 0
            with temp.open("xb") as dst:
                while True:
                    data = response.read(1024*1024)
                    if not data:
                        break
                    n += len(data)
                    if n > MAX_ZIP_BYTES:
                        raise IPhoneImageProxyError("Download exceeds maximum size")
                    dst.write(data)
        with zipfile.ZipFile(temp) as z:
            if z.testzip() is not None:
                raise IPhoneImageProxyError("Corrupt Pix4D ZIP CRC")
        os.replace(temp, destination)
    finally:
        if temp.exists():
            temp.unlink()
    return destination


def extract_photo_only_session(archive, destination, *,
                               terms_reviewed=False, frame_limit=24):
    if not terms_reviewed:
        raise IPhoneImageProxyError("Review Pix4D personal/professional training terms first")
    archive, destination = Path(archive).resolve(), Path(destination).resolve()
    if archive == destination or archive in destination.parents:
        raise IPhoneImageProxyError("Source ZIP cannot be placed within destination")
    if destination.exists():
        raise IPhoneImageProxyError("Refuse to overwrite a native session")
    if not isinstance(frame_limit, int) or not 3 <= frame_limit <= 100:
        raise IPhoneImageProxyError("Select 3–100 source images")
    with zipfile.ZipFile(archive) as zipped:
        infos = zipped.infolist()
        if len(infos) > 5000 or len(infos) == 0:
            raise IPhoneImageProxyError("Invalid source archive entry count")
        if sum(x.file_size for x in infos) > MAX_UNCOMPRESSED_BYTES:
            raise IPhoneImageProxyError("Oversized uncompressed dataset")
        names = [info.filename for info in infos]
        if len(names) != len(set(n.casefold() for n in names)):
            raise IPhoneImageProxyError("Duplicate archive path")
        candidates = []
        for item in infos:
            path = PurePosixPath(item.filename)
            if (item.filename.startswith("/") or ".." in path.parts
                    or "\\" in item.filename or stat.S_IFMT(item.external_attr >> 16) == stat.S_IFLNK):
                raise IPhoneImageProxyError("Unsafe input path")
            if item.is_dir():
                continue
            if item.file_size > 32*1024**2:
                raise IPhoneImageProxyError("Oversized single archive asset")
            # Pix4D original archive has additional OPF/point cloud metadata;
            # read only immutable JPEG bytes, never execute or deserialize OPF.
            if item.filename.lower().endswith((".jpg", ".jpeg")):
                candidates.append(item)
        candidates.sort(key=lambda info: info.filename.casefold())
        if len(candidates) < 3:
            raise IPhoneImageProxyError("No usable iPhone JPEG photo sequence")
        picks = np.linspace(0, len(candidates)-1,
                            num=min(frame_limit, len(candidates)))
        selected = [candidates[i] for i in dict.fromkeys(int(round(x)) for x in picks)]
        if len(selected) < 3:
            raise IPhoneImageProxyError("Insufficient selected photos")
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".n9-iphone-photo-", dir=destination.parent))
        records = []
        try:
            (staging / "images").mkdir()
            for i, entry in enumerate(selected):
                payload = zipped.read(entry)
                image = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8),
                                     cv2.IMREAD_COLOR)
                if image is None or min(image.shape[:2]) < 96:
                    raise IPhoneImageProxyError("Invalid JPEG photo")
                # New output names are intentionally normalized, not assumed
                # to carry ARKit timestamps or GPS positions.
                filename = f"public_iphone13_{i:03d}.jpg"
                (staging / "images" / filename).write_bytes(payload)
                records.append({
                    "file": filename, "original_zip_path": entry.filename,
                    "width": int(image.shape[1]), "height": int(image.shape[0]),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                })
            audit = {
                "dataset": "PIX4D Olympic Flame real JPEG example",
                "dataset_url": OFFICIAL_ZIP_URL,
                "source_zip_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "source_device_claim": "iPhone 13 according to Pix4D project page",
                "not_iphone11": True, "no_native_arkit_poses": True,
                "known_intrinsics": False, "photo_only_requires_calibrated_focal": True,
                "source_purpose": "personal_or_professional_training_only",
                "physical_iphone11_tested": False, "real_world_validated": False,
                "frames": records,
            }
            (staging / "n9_source_audit.json").write_text(
                json.dumps(audit, indent=2), encoding="utf-8")
            os.replace(staging, destination)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    return destination, audit


def main():
    parser = argparse.ArgumentParser(description="PIX4D iPhone13 real photos, not iPhone11 / not ARKit")
    parser.add_argument("--archive", type=Path, help="Official Pix4D ZIP; omit to download")
    parser.add_argument("--download-to", type=Path, help="Local output for actual archive download")
    parser.add_argument("--session-out", type=Path, help="Immutable photo-only native session")
    parser.add_argument("--frame-limit", type=int, default=24)
    parser.add_argument("--training-terms-reviewed", action="store_true")
    args = parser.parse_args()
    if args.archive:
        archive = args.archive
    elif args.download_to:
        archive = download_official_archive(args.download_to,
                                            terms_reviewed=args.training_terms_reviewed)
    else:
        parser.error("Specify --archive or --download-to")
    if args.session_out is None:
        print(json.dumps({"archive": str(archive), "real_world_validated": False}))
    else:
        path, audit = extract_photo_only_session(
            archive, args.session_out, terms_reviewed=args.training_terms_reviewed,
            frame_limit=args.frame_limit)
        print(json.dumps({"session": str(path), **audit}, indent=2))


if __name__ == "__main__":
    main()
