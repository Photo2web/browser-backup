"""
restore.py — Wiederherstellung eines Profils aus einer BrowserBackup-ZIP.

v1-Scope (bestaetigt in Phase 0, siehe PHASE0_NOTIZEN.md): nur
"vorhandenes Profil ueberschreiben" wird unterstuetzt. "Neues Profil
anlegen" ist auf v1.1 verschoben (Chromium info_cache-Erzeugung ohne
Testreihe zu riskant).

Local State (Chromium) wird NICHT automatisch mitwiederhergestellt
(PROJEKT.md §6.3) — nur wenn restore_local_state=True explizit gesetzt
wird (GUI fragt aktiv nach), und dann erst NACH einem Sicherheits-Backup
der vorhandenen Local State als "Local State.bak_<timestamp>".
"""

import datetime
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .backup import ProgressCallback, backup_profile
from .browsers import Browser, Profile


@dataclass
class RestoreResult:
    """Ergebnis einer Wiederherstellung."""

    restored_files: int = 0
    locked_files: list[str] = field(default_factory=list)
    safety_backup_path: Path | None = None
    local_state_restored: bool = False
    local_state_backup_path: Path | None = None


def read_manifest(zip_path: Path) -> dict:
    """Liest backup_manifest.json aus der ZIP — fuer die read-only
    Manifest-Anzeige in der GUI, BEVOR der Nutzer Ziel-Profil und Modus
    waehlt."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open("backup_manifest.json") as f:
            return json.load(f)


def restore_profile(
    zip_path: Path,
    target_browser: Browser,
    target_profile: Profile,
    make_safety_backup: bool = True,
    restore_local_state: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> RestoreResult:
    """Stellt ein Profil aus zip_path in target_profile.path wieder her
    (ueberschreibt vorhandene Dateien, entfernt aber keine Dateien, die
    NUR im Ziel existieren, z.B. lokale Cache-Reste — das ist unschaedlich,
    da es sich dabei per Definition um regenerierbare Daten handelt).

    Parameter:
        make_safety_backup: sichert das aktuelle Ziel-Profil VOR dem
            Ueberschreiben als eigene ZIP (Cache wird hier NICHT
            ausgeschlossen — vollstaendiges Rueckfall-Netz statt
            optimierter Sicherung).
        restore_local_state: nur bei Chromium relevant, Default aus
            PROJEKT.md §6.3 ist "Nein" (bestehende Local State bleibt
            unangetastet, da Passwoerter ohnehin nicht portabel sind).
    """
    zip_path = Path(zip_path)
    manifest = read_manifest(zip_path)

    result = RestoreResult()

    if make_safety_backup and target_profile.path.exists():
        safety_result = backup_profile(
            target_browser,
            target_profile,
            dest_dir=target_profile.path.parent,
            exclude_cache=False,
            progress_callback=None,
        )
        # Sicherheits-Backup klar als solches kennzeichnen.
        safety_name = safety_result.zip_path.name.replace("browserbackup_", "browserbackup_SAFETY_", 1)
        safety_path = safety_result.zip_path.with_name(safety_name)
        safety_result.zip_path.rename(safety_path)
        result.safety_backup_path = safety_path

    target_profile.path.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        members = [n for n in namelist if n.startswith("profile/") and not n.endswith("/")]
        will_restore_local_state = (
            restore_local_state and manifest.get("has_local_state") and "local_state/Local State" in namelist
        )
        total = len(members) + (1 if will_restore_local_state else 0)

        if progress_callback:
            progress_callback(0, total, "Wiederherstellung wird vorbereitet ...")

        restored = 0
        for member in members:
            rel = member[len("profile/"):]
            dest_path = target_profile.path / rel
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with zf.open(member) as src, open(dest_path, "wb") as dst:
                    dst.write(src.read())
                restored += 1
            except (OSError, PermissionError) as exc:
                # UNSICHER/erwarteter Fall: Zieldatei koennte noch durch den
                # Browser gesperrt sein, falls der Prozess-Check umgangen
                # oder der Browser zwischenzeitlich neu gestartet wurde.
                result.locked_files.append(f"{rel} ({exc})")

            if progress_callback:
                progress_callback(restored + len(result.locked_files), total, rel)

        result.restored_files = restored

        if will_restore_local_state:
            if target_browser.local_state_path is None:
                result.locked_files.append("Local State (Ziel-Browser hat keinen local_state_path)")
            else:
                if target_browser.local_state_path.exists():
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
                    backup_ls_path = target_browser.local_state_path.with_name(f"Local State.bak_{timestamp}")
                    try:
                        target_browser.local_state_path.replace(backup_ls_path)
                        result.local_state_backup_path = backup_ls_path
                    except OSError as exc:
                        result.locked_files.append(f"Local State Sicherheits-Backup fehlgeschlagen ({exc})")

                try:
                    with zf.open("local_state/Local State") as src, open(target_browser.local_state_path, "wb") as dst:
                        dst.write(src.read())
                    result.local_state_restored = True
                except (OSError, PermissionError) as exc:
                    result.locked_files.append(f"Local State ({exc})")

            if progress_callback:
                progress_callback(total, total, "Local State")

    return result
