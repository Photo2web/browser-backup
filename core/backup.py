"""
backup.py — Sicherung eines Browserprofils in eine ZIP-Datei.

ZIP-Struktur (siehe PROJEKT.md §7):
    backup_manifest.json
    profile/            <- gefilterter Profilinhalt
    local_state/Local State   <- nur bei Chromium

Gesperrte/unlesbare Dateien werden einzeln abgefangen und im Ergebnis
gesammelt, die Sicherung bricht dadurch NICHT ab (PROJEKT.md §8.8).
"""

import datetime
import json
import os
import platform
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import TOOL_VERSION
from .blacklist import excluded_patterns_for_manifest, is_excluded
from .browsers import Browser, Profile

# Zeichen, die in Windows-Dateinamen nicht erlaubt sind.
_INVALID_FILENAME_CHARS = '<>:"/\\|?*'

# Callback-Signatur fuer Fortschrittsmeldungen: (aktuell, gesamt, meldung).
ProgressCallback = Callable[[int, int, str], None]


@dataclass
class BackupResult:
    """Ergebnis einer Sicherung."""

    zip_path: Path
    manifest: dict
    locked_files: list[str] = field(default_factory=list)
    file_count: int = 0


def _sanitize_filename_part(text: str) -> str:
    """Ersetzt Zeichen, die in Windows-Dateinamen verboten sind, durch '_'."""
    cleaned = "".join("_" if ch in _INVALID_FILENAME_CHARS else ch for ch in text)
    return cleaned.strip()


def _iter_profile_files(profile_root: Path, browser_key: str, exclude_cache: bool, walk_errors: list[str]):
    """Liefert (absoluter_pfad, relativer_posix_pfad) fuer alle zu sichernden
    Dateien im Profil. Blacklist-Ordner werden beim Durchlaufen komplett
    uebersprungen (kein Abstieg in Cache-Ordner) statt nachtraeglich
    gefiltert zu werden — spart Zeit bei grossen Cache-Ordnern.

    walk_errors: os.walk() ignoriert per Default JEDEN Fehler beim Auflisten
    eines Unterordners lautlos (z.B. gesperrter/unlesbarer Ordner) — ohne
    onerror-Callback wuerde ein solcher Ordner spurlos fehlen, ohne dass es
    im Ergebnis auftaucht. Der Callback traegt das stattdessen hier ein.
    """

    def _on_walk_error(exc: OSError) -> None:
        walk_errors.append(f"{exc.filename} ({exc.strerror or exc})")

    for dirpath, dirnames, filenames in os.walk(profile_root, topdown=True, onerror=_on_walk_error):
        current_rel = Path(dirpath).relative_to(profile_root)

        if exclude_cache:
            kept_dirnames = []
            for name in dirnames:
                child_rel = (current_rel / name).as_posix()
                if is_excluded(child_rel, browser_key):
                    continue
                kept_dirnames.append(name)
            dirnames[:] = kept_dirnames

        for name in filenames:
            child_rel = (current_rel / name).as_posix()
            if exclude_cache and is_excluded(child_rel, browser_key):
                continue
            yield Path(dirpath) / name, child_rel


def backup_profile(
    browser: Browser,
    profile: Profile,
    dest_dir: Path,
    exclude_cache: bool = True,
    progress_callback: ProgressCallback | None = None,
) -> BackupResult:
    """Sichert ein Profil als ZIP nach dest_dir.

    Parameter:
        browser: erkannter Browser (aus browsers.detect_browsers())
        profile: zu sicherndes Profil
        dest_dir: Zielordner fuer die ZIP-Datei (wird bei Bedarf angelegt)
        exclude_cache: Cache-Blacklist anwenden (Default: an, siehe GUI-Checkbox)
        progress_callback: optional, wird mit (aktuell, gesamt, meldung) aufgerufen

    Rueckgabe: BackupResult mit Pfad zur ZIP-Datei, Manifest-Inhalt und
    einer Liste gesperrter/unlesbarer Dateien (Sicherung bricht dafuer
    NICHT ab).
    """
    if not profile.path.exists():
        raise FileNotFoundError(f"Profilordner existiert nicht: {profile.path}")

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    profile_name_part = _sanitize_filename_part(profile.name) or "profil"
    zip_name = f"umzug_{browser.key}_{profile_name_part}_{timestamp}.zip"
    zip_path = dest_dir / zip_name

    locked_files: list[str] = []

    files = list(_iter_profile_files(profile.path, browser.key, exclude_cache, locked_files))
    has_local_state_file = bool(browser.local_state_path and browser.local_state_path.exists())
    total = len(files) + (1 if has_local_state_file else 0)

    written = 0

    if progress_callback:
        progress_callback(0, total, "Sicherung wird vorbereitet ...")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for abs_path, rel_posix in files:
            arcname = f"profile/{rel_posix}"
            try:
                zf.write(abs_path, arcname)
                written += 1
            except (OSError, PermissionError) as exc:
                # UNSICHER: Manche Firefox-/Chromium-Dateien (z.B. *.sqlite-wal
                # bei laufendem Browser) koennen kurzzeitig gesperrt sein.
                # Deshalb einzeln abfangen statt die Sicherung abzubrechen.
                locked_files.append(f"{rel_posix} ({exc})")

            if progress_callback:
                progress_callback(written + len(locked_files), total, rel_posix)

        has_local_state = False
        if has_local_state_file:
            try:
                zf.write(browser.local_state_path, "local_state/Local State")
                has_local_state = True
            except (OSError, PermissionError) as exc:
                locked_files.append(f"Local State ({exc})")
            if progress_callback:
                progress_callback(total, total, "Local State")

        manifest = {
            "tool": "BrowserBackup",
            "tool_version": TOOL_VERSION,
            "created_at": datetime.datetime.now().isoformat(),
            "browser": browser.key,
            "source_profile_dir": profile.id,
            "source_profile_name": profile.name,
            "has_local_state": has_local_state,
            "excluded_patterns": excluded_patterns_for_manifest(browser.key) if exclude_cache else [],
            "source_host": platform.node(),
            "source_os": f"{platform.system()} {platform.release()}",
            "locked_files": locked_files,
        }
        zf.writestr("backup_manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

    return BackupResult(zip_path=zip_path, manifest=manifest, locked_files=locked_files, file_count=written)


if __name__ == "__main__":
    # Manueller Testlauf: sichert das erste Profil des ersten gefundenen
    # Browsers nach ./test_backup_output (wird angelegt, liegt in .gitignore).
    # Aufruf vom Projekt-Root aus: python -m core.backup
    from .browsers import detect_browsers

    def _console_progress(current: int, total: int, message: str) -> None:
        print(f"  [{current}/{total}] {message}")

    found = detect_browsers()
    if not found:
        print("Kein Browser gefunden — Testlauf abgebrochen.")
    else:
        test_browser = found[0]
        test_profile = test_browser.profiles[0]
        out_dir = Path(__file__).resolve().parent.parent / "test_backup_output"

        print(f"Sichere Browser={test_browser.display_name}, Profil={test_profile.name!r}")
        print(f"Ziel: {out_dir}\n")

        result = backup_profile(
            test_browser, test_profile, out_dir, exclude_cache=True, progress_callback=_console_progress
        )

        print(f"\nFertig: {result.zip_path}")
        print(f"Dateien gesichert: {result.file_count}")
        print(f"Gesperrte/uebersprungene Dateien: {len(result.locked_files)}")
        for locked in result.locked_files[:10]:
            print(f"  ! {locked}")
