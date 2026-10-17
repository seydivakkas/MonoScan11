"""Optional OFFICIAL Apple ARKitScenes one-sequence asset retrieval.

This tool does not click through terms or assume a license on the user's
behalf. It will download only with explicit --license-reviewed; download
is local, never uploaded to GitHub. ARKitScenes capture device is iPad Pro
LiDAR, NOT a real MonoScan11 iPhone 11 session.
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
import urllib.request
import zipfile


ROOT = "https://docs-assets.developer.apple.com/ml-research/datasets/arkitscenes/v1"
FILES = ("lowres_wide.zip", "lowres_wide_intrinsics.zip", "lowres_wide.traj")
MAX_DOWNLOAD = {"lowres_wide.zip": 512 * 1024**2,
                "lowres_wide_intrinsics.zip": 128 * 1024**2,
                "lowres_wide.traj": 32 * 1024**2}


class DatasetFetchError(ValueError):
    pass


def source_urls(video_id, split):
    if not (isinstance(video_id, str) and video_id.isdigit() and len(video_id) == 8):
        raise DatasetFetchError("Video ID must be eight digits")
    if split not in ("Training", "Validation"):
        raise DatasetFetchError("Only Apple official split names are allowed")
    return {
        name: f"{ROOT}/raw/{split}/{video_id}/{name}" for name in FILES
    }


def _download(url, output, limit):
    # Exact official fixed host: no arbitrary URL redirect or remote scripts.
    request = urllib.request.Request(url, headers={"User-Agent": "MonoScan11-N9-Research/1"})
    with urllib.request.urlopen(request, timeout=45) as response:
        if response.geturl().split("/")[2] != "docs-assets.developer.apple.com":
            raise DatasetFetchError("Dataset redirect outside Apple's documented host")
        if int(response.headers.get("Content-Length") or 0) > limit:
            raise DatasetFetchError("Source file exceeds the configured download cap")
        with open(output, "xb") as out:
            n = 0
            while True:
                raw = response.read(1024*1024)
                if not raw:
                    break
                n += len(raw)
                if n > limit:
                    raise DatasetFetchError("Source asset exceeded configured byte cap")
                out.write(raw)


def _safe_extract(zip_path, destination, kind, video_id):
    if kind not in ("lowres_wide", "lowres_wide_intrinsics"):
        raise DatasetFetchError("Unknown official extraction type")
    valid_suffix = ".png" if kind == "lowres_wide" else ".pincam"
    total_bytes, files = 0, 0
    with zipfile.ZipFile(zip_path) as archive:
        if len(archive.infolist()) > 30000:
            raise DatasetFetchError("Unbounded official source ZIP")
        for member in archive.infolist():
            if member.is_dir():
                continue
            path = PurePosixPath(member.filename)
            if (len(path.parts) not in (1, 2)
                    or path.parts[-1].startswith(".")
                    or not path.parts[-1].startswith(video_id+"_")
                    or not path.parts[-1].endswith(valid_suffix)
                    or (len(path.parts) == 2 and path.parts[0] != kind)
                    or "\\" in member.filename
                    or stat.S_IFMT(member.external_attr >> 16) == stat.S_IFLNK):
                raise DatasetFetchError("Unexpected archive filename/type")
            if member.file_size > 40 * 1024**2:
                raise DatasetFetchError("Oversized image/intrinsic")
            total_bytes += member.file_size
            files += 1
            if total_bytes > 1024**3:
                raise DatasetFetchError("Excessive uncompressed asset bytes")
            final = destination / kind / path.name
            final.parent.mkdir(parents=True, exist_ok=True)
            if final.exists():
                raise DatasetFetchError("Duplicate or collision in official archive")
            with archive.open(member) as src, final.open("xb") as out:
                shutil.copyfileobj(src, out, 1024*1024)
    if files < 3:
        raise DatasetFetchError("Official asset ZIP contains too few frames")
    return files


def download_one_sequence(video_id, split, destination, *, license_reviewed=False):
    if not license_reviewed:
        raise DatasetFetchError("Review Apple's dataset terms and explicitly pass --license-reviewed")
    urls = source_urls(str(video_id), split)
    destination = Path(destination).expanduser().resolve()
    if destination.exists():
        raise DatasetFetchError("Refusing to overwrite an existing target")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".n9-apple-dataset-", dir=destination.parent))
    manifest = {"origin": "Apple ARKitScenes RAW", "model": "iPad Pro LiDAR",
                "not_iphone11": True, "physical_device_accepted": False,
                "real_world_validated": False, "split": split, "video_id": video_id,
                "urls": urls, "sha256": {}}
    try:
        for file, url in urls.items():
            out = temp / file
            try:
                _download(url, out, MAX_DOWNLOAD[file])
            except (OSError, urllib.error.URLError, DatasetFetchError) as exc:
                raise DatasetFetchError("Source asset could not be obtained: " + file) from exc
            manifest["sha256"][file] = hashlib.sha256(out.read_bytes()).hexdigest()
            if file.endswith(".zip"):
                _safe_extract(out, temp, file[:-4], str(video_id))
                out.unlink()
        if not (temp / "lowres_wide.traj").is_file():
            raise DatasetFetchError("Official trajectory unavailable")
        (temp / "n9_dataset_download_audit.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")
        os.replace(temp, destination)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return destination, manifest


def main():
    parser = argparse.ArgumentParser(description="Download real iPad Pro ARKitScenes assets, NOT iPhone11")
    parser.add_argument("--video-id", default="41069046")
    parser.add_argument("--split", choices=("Training", "Validation"), default="Validation")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--license-reviewed", action="store_true",
                        help="You have independently reviewed and may use this dataset under its terms")
    parser.add_argument("--show-urls", action="store_true", help="No download; show official URLs")
    args = parser.parse_args()
    if args.show_urls:
        print(json.dumps(source_urls(args.video_id, args.split), indent=2))
        return
    path, manifest = download_one_sequence(args.video_id, args.split, args.output,
                                           license_reviewed=args.license_reviewed)
    print(json.dumps({"path": str(path), **manifest}, indent=2))


if __name__ == "__main__":
    main()
