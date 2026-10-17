"""N8 deterministic source-only Windows/offline distribution and integrity audit.

This creates a reproducible SOURCE ZIP, not a standalone EXE/MSIX.
System Python/Tk + native wheels are separately required. Absolutely no user
photos, datasets, cached outputs, credentials or generated geometry included.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile


SOURCE_DIRS = ("monoscan_core", "tools", "scripts")
ROOT_FILES = ("MonoScan11-Desktop.cmd", "requirements-native.txt", "README.md", "LICENSE")
ALLOWED_SUFFIXES = {".py", ".md", ".cmd", ".txt"}
ROOT = Path(__file__).resolve().parents[1]
FIXED_DATE = (2020, 1, 1, 0, 0, 0)
MAX_SINGLE_BYTES = 8 * 1024 * 1024


class PackageError(ValueError):
    pass


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def package_manifest(root=ROOT):
    root = Path(root).resolve()
    mapping = {}
    for name in ROOT_FILES:
        item = root / name
        if item.is_file() and not item.is_symlink():
            mapping[name] = item
        elif name != "LICENSE":
            raise PackageError("Required distribution source missing: " + name)
    for directory in SOURCE_DIRS:
        folder = root / directory
        if not folder.is_dir() or folder.is_symlink():
            raise PackageError("Unsafe source directory: " + directory)
        for item in folder.rglob("*"):
            if not item.is_file():
                continue
            if item.is_symlink() or any((root / p).is_symlink() for p in item.relative_to(root).parents):
                raise PackageError("Symbolic link in distribution source")
            if item.suffix not in ALLOWED_SUFFIXES or "__pycache__" in item.parts:
                continue
            name = item.relative_to(root).as_posix()
            if not all(part not in ("..", ".") for part in PurePosixPath(name).parts):
                raise PackageError("Unsafe distribution path")
            mapping[name] = item
    if not all(n in mapping for n in (
        "monoscan_core/desktop.py", "monoscan_core/workspace.py",
        "monoscan_core/dense_mvs.py", "monoscan_core/bundle_adjustment.py",
        "scripts/monoscan_desktop.py", "tools/monoscan.py"
    )):
        raise PackageError("A required N3-N7 module was omitted")
    content = {}
    for name, item in sorted(mapping.items()):
        if item.stat().st_size > MAX_SINGLE_BYTES:
            raise PackageError("Source file too large: " + name)
        content[name] = item.read_bytes()
    return content


def _zip_record(out, name, raw):
    info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    out.writestr(info, raw)


def build_source_bundle(target: Path, *, root=ROOT):
    content = package_manifest(root)
    sha = {name: _hash(raw) for name, raw in content.items()}
    manifest = {
        "format": "MonoScan11 N8 source-only zip v1",
        "stage": "N8", "contains_user_data": False,
        "offline_runtime": "Python 3.11+ with Tk and separately installed CPU wheels",
        "not_standalone": True,
        "real_world_validated": False,
        "n9_real_photo_deferred": True,
        "sha256": sha,
    }
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise PackageError("Refusing to overwrite existing distribution")
    tmp = target.with_name(".tmp-" + target.name)
    if tmp.exists():
        raise PackageError("Unfinished distribution stage already present")
    try:
        with zipfile.ZipFile(tmp, "w", allowZip64=False) as out:
            for name, raw in sorted(content.items()):
                _zip_record(out, name, raw)
            _zip_record(out, "monoscan11-package-manifest.json",
                        (json.dumps(manifest, ensure_ascii=True, sort_keys=True,
                                    indent=2)+"\n").encode("utf-8"))
        verify_bundle(tmp)
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()
    return {
        "bundle": str(target.resolve()), "sha256": _hash(target.read_bytes()),
        "source_files": len(sha), "total_source_bytes": sum(map(len, content.values())),
        "standalone_windows_executable": False, "real_world_validated": False,
    }


def verify_bundle(path):
    try:
        with zipfile.ZipFile(path) as data:
            names = data.namelist()
            if (len(names) != len(set(x.casefold() for x in names))
                    or any(x.startswith("/") or "\\" in x or ".." in PurePosixPath(x).parts
                           for x in names)
                    or "monoscan11-package-manifest.json" not in names):
                raise PackageError("Unsafe distribution entry names")
            manifest = json.loads(data.read("monoscan11-package-manifest.json"))
            hashes = manifest["sha256"]
            if (manifest.get("format") != "MonoScan11 N8 source-only zip v1"
                    or manifest.get("not_standalone") is not True
                    or manifest.get("real_world_validated") is not False
                    or set(names) != set(hashes) | {"monoscan11-package-manifest.json"}):
                raise PackageError("Invalid package metadata")
            for name, expected in hashes.items():
                if _hash(data.read(name)) != expected:
                    raise PackageError("Distribution SHA mismatch: " + name)
                if data.getinfo(name).compress_type != zipfile.ZIP_STORED:
                    raise PackageError("Unexpected distribution compression")
            return manifest
    except (ValueError, OSError, KeyError, UnicodeError, zipfile.BadZipFile) as exc:
        if isinstance(exc, PackageError):
            raise
        raise PackageError("Cannot verify distribution ZIP") from exc


def main():
    p = argparse.ArgumentParser(description="N8 source-only zip, NOT standalone installer")
    p.add_argument("--output", type=Path, default=Path("dist/MonoScan11-N8-source.zip"))
    p.add_argument("--verify", type=Path)
    args = p.parse_args()
    if args.verify:
        data = verify_bundle(args.verify)
        print(json.dumps({"verified": True, "source_files": len(data["sha256"]),
                          "real_world_validated": False}, indent=2))
    else:
        print(json.dumps(build_source_bundle(args.output), indent=2))


if __name__ == "__main__":
    main()
