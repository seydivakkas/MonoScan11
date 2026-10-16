"""N7 local Windows project catalog and strict iPhone ZIP32 import.

Data is stored only on the user's disk. ZIP entries are checked before any
filesystem modification; all staging is private and atomically renamed.
No network, telemetry, fabricated scans, or image rewriting.
"""
from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
import zipfile


MAX_ARCHIVE_BYTES = 4 * 1024 ** 3  # ZIP32 policy, conservative total payload
MAX_ENTRY_BYTES = 1024 ** 3
MAX_ITEMS = 180   # 150 images + small optional files
ALLOWED_OPTIONAL = {"project.json", "arkit_sparse.ply"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


class WorkspaceError(ValueError):
    """Unsafe import, incompatible native contract, or broken catalog."""


def _is_safe_name(name):
    p = PurePosixPath(name)
    return (isinstance(name, str) and bool(name) and "\\" not in name
            and "\x00" not in name and not name.startswith("/")
            and len(name) <= 240 and all(part not in ("", ".", "..") for part in p.parts)
            and str(p) == name)


def validate_archive(archive: Path):
    """Check ZIP *and* session v1 contract; return (members, parsed manifest).

    ZIPStore.swift emits method-0 files. Reject compressed/symlinked/unknown
    entries, malformed JSON, unsafe path, oversized data or duplicate case-folds.
    """
    try:
        with zipfile.ZipFile(archive) as src:
            members = src.infolist()
            if not members or len(members) > MAX_ITEMS:
                raise WorkspaceError("Unexpected ZIP entry count")
            names = [info.filename for info in members]
            if (len(names) != len(set(n.casefold() for n in names))
                    or any(not _is_safe_name(n) or n.endswith("/") for n in names)):
                raise WorkspaceError("Unsafe or duplicate ZIP member path")
            total = 0
            for item in members:
                if item.flag_bits & 0x1 or item.compress_type != zipfile.ZIP_STORED:
                    raise WorkspaceError("Only unencrypted iPhone ZIPStore method-0 files supported")
                mode = (item.external_attr >> 16) & 0xFFFF
                if stat.S_IFMT(mode) == stat.S_IFLNK:
                    raise WorkspaceError("ZIP symlink rejected")
                if item.file_size > MAX_ENTRY_BYTES:
                    raise WorkspaceError("Oversized ZIP entry")
                total += item.file_size
                if total > MAX_ARCHIVE_BYTES:
                    raise WorkspaceError("ZIP payload too large")
            if names.count("session.json") != 1:
                raise WorkspaceError("Missing session.json v1")
            manifest_info = src.getinfo("session.json")
            if manifest_info.file_size > 3 * 1024 * 1024:
                raise WorkspaceError("Manifest too large")
            manifest = json.loads(src.read("session.json"))
            if (not isinstance(manifest, dict) or manifest.get("schemaVersion") != 1
                    or not isinstance(manifest.get("frames"), list)
                    or not 1 <= len(manifest["frames"]) <= 150):
                raise WorkspaceError("Unsupported session.json v1 manifest")
            frame_names = []
            previous_time = float("-inf")
            for rec in manifest["frames"]:
                if not isinstance(rec, dict) or not isinstance(rec.get("file"), str):
                    raise WorkspaceError("Malformed session frame")
                name = rec["file"]
                if (not _is_safe_name(name) or "/" in name
                        or Path(name).suffix.lower() not in IMAGE_SUFFIXES):
                    raise WorkspaceError("Invalid session image name")
                timestamp = rec.get("timestamp")
                if (type(timestamp) not in (int, float)
                        or not float("-inf") < float(timestamp) < float("inf")
                        or timestamp <= previous_time):
                    raise WorkspaceError("Invalid session timestamp order")
                previous_time = timestamp
                frame_names.append(name)
            if len(frame_names) != len(set(n.casefold() for n in frame_names)):
                raise WorkspaceError("Duplicate manifest image")
            expected = {"session.json"} | ALLOWED_OPTIONAL | {
                "images/" + n for n in frame_names
            }
            found = set(names)
            required = {"session.json"} | {"images/" + n for n in frame_names}
            if not required.issubset(found) or not found.issubset(expected):
                raise WorkspaceError("ZIP images do not match manifest exactly")
            return names, manifest
    except (zipfile.BadZipFile, json.JSONDecodeError, KeyError, UnicodeError, OSError) as exc:
        raise WorkspaceError("Invalid iPhone ZIP: " + str(exc)) from exc


def native_validate(folder, *, executable=None):
    """Run existing native session validator without importing platform GUI code."""
    cli = Path(__file__).resolve().parents[1] / "tools" / "monoscan.py"
    cmd = [executable or sys.executable, str(cli), "validate", str(folder)]
    finished = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=90)
    if finished.returncode != 0:
        raise WorkspaceError("Session validation failed: " + finished.stderr.strip()[:600])
    try:
        return json.loads(finished.stdout)
    except json.JSONDecodeError as exc:
        raise WorkspaceError("Validator returned invalid JSON") from exc


class ProjectCatalog:
    """JSON catalog: imported ZIP packages or explicitly linked local sessions."""

    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._index = self.root / "projects.json"
        self._projects = self._read_index()

    def _read_index(self):
        if not self._index.exists():
            return []
        try:
            data = json.loads(self._index.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise ValueError("Invalid list")
            ids = set()
            for entry in data:
                if (not isinstance(entry, dict) or
                        set(entry) != {"id", "name", "session", "origin"} or
                        entry["origin"] not in ("zip", "linked") or
                        not isinstance(entry["name"], str) or
                        not isinstance(entry["session"], str) or
                        not isinstance(entry["id"], str)):
                    raise ValueError("Malformed project entry")
                uuid.UUID(entry["id"])
                if entry["id"] in ids:
                    raise ValueError("Duplicate project ID")
                ids.add(entry["id"])
            return data
        except (ValueError, OSError, UnicodeError) as exc:
            raise WorkspaceError("Corrupt project catalog; not silently reset") from exc

    def _commit(self, entries):
        temp = self.root / (".index-" + uuid.uuid4().hex + ".json")
        try:
            temp.write_text(json.dumps(entries, ensure_ascii=False, indent=2),
                            encoding="utf-8")
            os.replace(temp, self._index)
            self._projects = entries
        finally:
            if temp.exists():
                temp.unlink()

    def projects(self):
        return [dict(p) for p in self._projects]

    def session_path(self, pid):
        item = next((p for p in self._projects if p["id"] == pid), None)
        if item is None:
            raise WorkspaceError("Unknown project")
        folder = Path(item["session"]).resolve()
        if item["origin"] == "zip" and not folder.is_relative_to(self.root / "sessions"):
            raise WorkspaceError("Managed project path escaped workspace")
        if not (folder / "images").is_dir():
            raise WorkspaceError("Project image folder is unavailable")
        return folder

    def link_folder(self, folder, name=None):
        folder = Path(folder).expanduser().resolve(strict=True)
        native_validate(folder)
        title = (name or folder.name).strip()
        if not 1 <= len(title) <= 80:
            raise WorkspaceError("Project title must contain 1-80 characters")
        result = {"id":str(uuid.uuid4()), "name": title,
                  "session": str(folder), "origin": "linked"}
        self._commit(self._projects + [result])
        return dict(result)

    def import_zip(self, archive, name=None):
        archive = Path(archive).expanduser().resolve(strict=True)
        names, _ = validate_archive(archive)
        title = (name or archive.stem).strip()
        if not 1 <= len(title) <= 80:
            raise WorkspaceError("Project title must contain 1-80 characters")
        parent = self.root / "sessions"
        parent.mkdir(exist_ok=True)
        pid = str(uuid.uuid4())
        destination = parent / pid
        staging = Path(tempfile.mkdtemp(prefix=".import-", dir=parent))
        try:
            with zipfile.ZipFile(archive) as src:
                for filename in names:
                    target = staging.joinpath(*PurePosixPath(filename).parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with src.open(filename) as inp, target.open("xb") as out:
                        shutil.copyfileobj(inp, out, 1024 * 1024)
            native_validate(staging)
            os.replace(staging, destination)
            result = {"id": pid, "name": title,
                      "session": str(destination), "origin": "zip"}
            try:
                self._commit(self._projects + [result])
            except Exception:
                shutil.rmtree(destination)
                raise
            return dict(result)
        finally:
            if staging.exists():
                shutil.rmtree(staging)

    def remove(self, pid):
        """Remove project from catalog, NEVER delete users' photos or saved runs."""
        if not any(p["id"] == pid for p in self._projects):
            raise WorkspaceError("Unknown project")
        self._commit([p for p in self._projects if p["id"] != pid])


def default_workspace():
    home = os.environ.get("LOCALAPPDATA")
    return Path(home) / "MonoScan11" / "workspace" if home else Path.home() / ".monoscan11" / "workspace"
