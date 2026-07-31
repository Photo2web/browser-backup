"""Persistente Liste der zum Entfernen ausgewählten Programme.

Wird beim Start einer Deinstallation geschrieben und später im
Neuinstallation-Screen als Quelle „Zuletzt entfernte Programme" gelesen, um die
Software wieder zu installieren. Speicherort ist ``%APPDATA%\\Umzugstool\\
entfernte_programme.json`` (pro Benutzer, dauerhaft auffindbar).

Ehrlich: Die Liste enthält die *zum Entfernen ausgewählten* Programme, nicht
den zurückgemeldeten Erfolg des (eigenständig laufenden) Skripts.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

from . import TOOL_VERSION


def store_dir() -> Path:
    """Verzeichnis für die Liste: %APPDATA%\\Umzugstool (Fallback: Home)."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / "Umzugstool"


def store_path() -> Path:
    return store_dir() / "entfernte_programme.json"


def load_removed(path: Path | None = None) -> list[dict]:
    """Liest die gespeicherten Programme. Fehlende/defekte Datei -> leere Liste."""
    p = Path(path) if path is not None else store_path()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    programs = data.get("programs") if isinstance(data, dict) else None
    return programs if isinstance(programs, list) else []


def _to_dict(program, now: str) -> dict:
    """InstalledProgram oder Dict -> serialisierbares Dict."""
    if isinstance(program, dict):
        entry = dict(program)
        entry.setdefault("removed_at", now)
        return entry
    return {
        "name": program.name,
        "publisher": program.publisher,
        "version": program.version,
        "scope": program.scope,
        "removed_at": now,
    }


def _sig(entry: dict) -> tuple[str, str]:
    return (str(entry.get("name", "")).lower(), str(entry.get("version") or ""))


def save_removed(programs, path: Path | None = None) -> Path:
    """Merged die Programme in die vorhandene Liste (Dedupe nach Name+Version)
    und schreibt sie. Gibt den Pfad zurück.

    Raises:
        OSError: wenn die Datei nicht geschrieben werden kann.
    """
    p = Path(path) if path is not None else store_path()
    now = datetime.datetime.now().isoformat(timespec="seconds")

    by_sig = {_sig(entry): entry for entry in load_removed(p)}
    for program in programs:
        entry = _to_dict(program, now)
        by_sig[_sig(entry)] = entry

    out = {
        "tool": "Umzugstool",
        "tool_version": TOOL_VERSION,
        "updated_at": now,
        "programs": sorted(by_sig.values(), key=lambda e: str(e.get("name", "")).lower()),
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return p
