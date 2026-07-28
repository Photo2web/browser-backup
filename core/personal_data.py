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
