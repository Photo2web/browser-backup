"""
personal_data.py — Sichern/Wiederherstellen persoenlicher Windows-Ordner.

GUI-unabhaengig und testbar. Erfasst Dokumente/Bilder/Musik/Videos/Desktop/
Downloads ueber die Windows-Known-Folder-API (respektiert Umleitungen wie
OneDrive/NextCloud), berechnet Groessen/freien Platz und sichert je Ordner
wahlweise als ZIP oder 1:1-Kopie. Restore mit waehlbarem Konfliktverhalten.
"""

import ctypes
import datetime
import json
import os
import platform
import shutil
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import TOOL_VERSION

# Fortschritt: (aktuell, gesamt, meldung) — identisch zu core/backup.py.
ProgressCallback = Callable[[int, int, str], None]

# key -> (Anzeigename, KNOWNFOLDERID-GUID, Fallback-Unterordner in %USERPROFILE%)
_KNOWN_FOLDERS = (
    ("documents", "Dokumente", "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}", "Documents"),
    ("pictures",  "Bilder",    "{33E28130-4E1E-4676-835A-98395C3BC3BB}", "Pictures"),
    ("music",     "Musik",     "{4BD8D571-6D19-48D3-BE97-422220080E43}", "Music"),
    ("videos",    "Videos",    "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}", "Videos"),
    ("desktop",   "Desktop",   "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}", "Desktop"),
    ("downloads", "Downloads", "{374DE290-123F-4565-9164-39C4925E467B}", "Downloads"),
)


@dataclass
class PersonalFolder:
    key: str
    display_name: str
    path: Path
    exists: bool


def _resolve_known_folder(guid_str: str) -> Path | None:
    """Loest eine KNOWNFOLDERID (GUID-String) ueber SHGetKnownFolderPath zum
    echten Pfad auf — respektiert Umleitungen (OneDrive/NextCloud). Gibt None
    zurueck, wenn die API nicht verfuegbar ist oder scheitert (Nicht-Windows
    oder Fehler); der Aufrufer nutzt dann einen Fallback-Pfad."""
    if os.name != "nt":
        return None
    try:
        class _GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", ctypes.c_uint32),
                ("Data2", ctypes.c_uint16),
                ("Data3", ctypes.c_uint16),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        u = uuid.UUID(guid_str)
        guid = _GUID()
        guid.Data1, guid.Data2, guid.Data3 = u.time_low, u.time_mid, u.time_hi_version
        for i, b in enumerate(u.bytes[8:]):
            guid.Data4[i] = b

        ptr = ctypes.c_wchar_p()
        res = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(guid), 0, None, ctypes.byref(ptr)
        )
        if res != 0 or not ptr.value:
            return None
        path = ptr.value
        ctypes.windll.ole32.CoTaskMemFree(ptr)
        return Path(path)
    except Exception:
        return None


def detect_personal_folders() -> list[PersonalFolder]:
    """Liefert die sechs persoenlichen Ordner mit echtem Pfad + Existenz-Flag."""
    profile = Path(os.path.expanduser("~"))
    folders: list[PersonalFolder] = []
    for key, name, guid, fallback in _KNOWN_FOLDERS:
        resolved = _resolve_known_folder(guid)
        if resolved is None:
            resolved = profile / fallback
        folders.append(
            PersonalFolder(key=key, display_name=name, path=resolved, exists=resolved.is_dir())
        )
    return folders


def _format_bytes(n: int) -> str:
    """Menschenlesbare Groesse (dezimal, 1000er-Schritte)."""
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(n)
    for unit in units:
        if value < 1000.0 or unit == units[-1]:
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1000.0


@dataclass
class FolderSize:
    total_bytes: int
    file_count: int
    walk_errors: list[str] = field(default_factory=list)


def _iter_files(root) -> list[tuple[Path, str]]:
    """(absoluter Pfad, relativer POSIX-Pfad) fuer alle Dateien unter root."""
    root = Path(root)
    out: list[tuple[Path, str]] = []
    if not root.is_dir():
        return out
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            abs_path = Path(dirpath) / name
            out.append((abs_path, abs_path.relative_to(root).as_posix()))
    return out


def _total_size(files) -> int:
    total = 0
    for abs_path, _rel in files:
        try:
            total += abs_path.stat().st_size
        except OSError:
            pass
    return total


def folder_size(path) -> FolderSize:
    """Gesamtgroesse + Dateizahl eines Ordners; unlesbare Unterordner werden
    gesammelt statt lautlos ignoriert (os.walk onerror)."""
    path = Path(path)
    total = 0
    count = 0
    errors: list[str] = []

    def _on_error(exc: OSError) -> None:
        errors.append(f"{exc.filename} ({exc.strerror or exc})")

    for dirpath, _dirnames, filenames in os.walk(path, onerror=_on_error):
        for name in filenames:
            fp = Path(dirpath) / name
            try:
                total += fp.stat().st_size
                count += 1
            except OSError as exc:
                errors.append(f"{fp} ({exc})")
    return FolderSize(total_bytes=total, file_count=count, walk_errors=errors)


def free_space(path) -> int:
    """Freier Platz am Ziel. Sucht den naechsten existierenden Elternpfad,
    falls das Ziel noch nicht angelegt wurde."""
    p = Path(path)
    while not p.exists():
        if p.parent == p:
            break
        p = p.parent
    return shutil.disk_usage(str(p)).free


@dataclass
class PersonalBackupResult:
    target: Path
    folder_key: str
    mode: str
    file_count: int
    skipped: list[str] = field(default_factory=list)
    manifest: dict = field(default_factory=dict)


def _timestamp() -> str:
    """Zeitstempel im Format YYYY-MM-DD_HHMM."""
    return datetime.datetime.now().strftime("%Y-%m-%d_%H%M")


def _build_manifest(folder, mode, file_count, total_bytes, skipped) -> dict:
    """Erstellt ein Manifest-Dictionary mit Sicherungsinformationen."""
    return {
        "tool": "BrowserBackup",
        "tool_version": TOOL_VERSION,
        "kind": "personal_data",
        "created_at": datetime.datetime.now().isoformat(),
        "folder_key": folder.key,
        "folder_display_name": folder.display_name,
        "source_path": str(folder.path),
        "mode": mode,
        "file_count": file_count,
        "total_bytes": total_bytes,
        "source_host": platform.node(),
        "source_os": f"{platform.system()} {platform.release()}",
        "skipped": skipped,
    }


def backup_personal_folder(folder, dest_dir, mode="zip", progress_callback=None) -> PersonalBackupResult:
    """Sichert einen persoenlichen Ordner als ZIP (data/... + Manifest im ZIP)
    oder als 1:1-Kopie (Ordner mit data/ + backup_manifest.json daneben).
    Gesperrte Dateien werden uebersprungen und in skipped gesammelt."""
    if mode not in ("zip", "copy"):
        raise ValueError(f"Unbekannter Modus: {mode!r}")
    if not folder.path.is_dir():
        raise FileNotFoundError(f"Ordner existiert nicht: {folder.path}")

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    files = _iter_files(folder.path)
    total = len(files)
    skipped: list[str] = []
    written = 0
    written_files: list[tuple[Path, str]] = []
    if progress_callback:
        progress_callback(0, total, "Sicherung wird vorbereitet ...")

    base = f"browserbackup_data_{folder.key}_{_timestamp()}"

    if mode == "zip":
        target = dest_dir / f"{base}.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for abs_path, rel in files:
                try:
                    zf.write(abs_path, f"data/{rel}")
                    written += 1
                    written_files.append((abs_path, rel))
                except (OSError, PermissionError) as exc:
                    skipped.append(f"{rel} ({exc})")
                if progress_callback:
                    progress_callback(written + len(skipped), total, rel)
            total_bytes = _total_size(written_files)
            manifest = _build_manifest(folder, mode, written, total_bytes, skipped)
            zf.writestr("backup_manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    else:
        target = dest_dir / base
        data_root = target / "data"
        data_root.mkdir(parents=True, exist_ok=True)
        for abs_path, rel in files:
            out = data_root / rel
            try:
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(abs_path, out)
                written += 1
                written_files.append((abs_path, rel))
            except (OSError, PermissionError) as exc:
                skipped.append(f"{rel} ({exc})")
            if progress_callback:
                progress_callback(written + len(skipped), total, rel)
        total_bytes = _total_size(written_files)
        manifest = _build_manifest(folder, mode, written, total_bytes, skipped)
        (target / "backup_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    return PersonalBackupResult(
        target=target, folder_key=folder.key, mode=mode,
        file_count=written, skipped=skipped, manifest=manifest,
    )
