"""Auslesen der installierten Programme via `winget list`.

GUI-unabhaengig und einzeln testbar. Liefert eine Liste von `InstalledApp`.
Programme, die winget kennt (Quelle winget/msstore + vorhandene Id), sind
automatisch neu installierbar; alle uebrigen gelten als "manuell".

Hintergrund zum Parsing (an realer Ausgabe auf Windows 11 verifiziert):
- Die Kopfzeile ist **lokalisiert** (z. B. dt. "ID  Version  Verfügbar  Quelle"),
  daher werden die Spalten ueber ihre **Position** bestimmt, nicht ueber den
  Spaltennamen: Name = erste, ID = zweite, Quelle = letzte Spalte.
- Die Spalte "Verfügbar"/"Available" erscheint nur, wenn Updates vorliegen —
  die Spaltenzahl ist also 4 oder 5. Die Offsets werden dynamisch aus dem
  Header abgeleitet.
- Nicht-winget-Programme haben eine leere Quelle; ihre ID ist ein interner
  Bezeichner (z. B. "ARP\\..." oder "MSIX\\...") und als winget-Paket unbrauchbar.

winget benoetigt eine Internetverbindung (es fragt seine Paketquelle online ab).
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

# Quellen, aus denen winget automatisch installieren kann.
_INSTALLABLE_SOURCES = frozenset({"winget", "msstore"})

# Zeichen, aus denen die Trennlinie unter der Kopfzeile bestehen kann
# (ASCII-Bindestrich sowie diverse Unicode-Striche, je nach winget-Version).
_DASH_CHARS = frozenset("-–—─")

_WINGET_LIST_ARGS = ("winget", "list", "--disable-interactivity")


class WinGetUnavailable(RuntimeError):
    """winget ist nicht installiert/auffindbar."""


class WinGetTimeout(RuntimeError):
    """`winget list` hat das Zeitlimit ueberschritten."""


@dataclass(frozen=True)
class InstalledApp:
    """Ein installiertes Programm laut winget."""

    name: str
    package_id: str | None      # winget-Id; None wenn nicht winget-installierbar
    version: str | None
    source: str | None          # "winget" | "msstore" | None

    @property
    def winget_installable(self) -> bool:
        return bool(self.package_id) and self.source in _INSTALLABLE_SOURCES


def _find_column_offsets(header: str) -> list[int]:
    """Startpositionen der Spalten aus der Kopfzeile (Wortanfaenge)."""
    offsets: list[int] = []
    for i, ch in enumerate(header):
        if ch != " " and (i == 0 or header[i - 1] == " "):
            offsets.append(i)
    return offsets


def _is_separator(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and all(ch in _DASH_CHARS for ch in stripped)


def _slice(line: str, offsets: list[int], index: int) -> str:
    """Feldwert einer Spalte anhand der Offsets (bis zum naechsten Spaltenstart)."""
    start = offsets[index]
    end = offsets[index + 1] if index + 1 < len(offsets) else None
    return line[start:end].strip()


def _parse_winget_list(text: str) -> list[InstalledApp]:
    """Parst die Textausgabe von `winget list` zu einer Liste von InstalledApp.

    Robust gegen fuehrende Fortschritts-/Spinner-Zeilen: die Kopfzeile wird
    ueber die darunterliegende Trennlinie (Bindestriche) gefunden.
    """
    lines = text.splitlines()

    sep_index = next((i for i, line in enumerate(lines) if _is_separator(line)), None)
    if sep_index is None or sep_index == 0:
        return []

    header = lines[sep_index - 1]
    offsets = _find_column_offsets(header)
    if len(offsets) < 2:          # mindestens Name + ID werden erwartet
        return []

    apps: list[InstalledApp] = []
    for line in lines[sep_index + 1:]:
        if not line.strip():
            continue

        name = _slice(line, offsets, 0)
        if not name:
            continue

        raw_id = _slice(line, offsets, 1)
        version = _slice(line, offsets, 2) if len(offsets) >= 3 else ""
        source_raw = line[offsets[-1]:].strip().lower()

        if source_raw in _INSTALLABLE_SOURCES:
            apps.append(InstalledApp(
                name=name,
                package_id=raw_id or None,
                version=version or None,
                source=source_raw,
            ))
        else:
            # Leere/unbekannte Quelle -> manuell; interne ARP-/MSIX-Id verwerfen.
            apps.append(InstalledApp(
                name=name,
                package_id=None,
                version=version or None,
                source=None,
            ))

    return apps


def _decode_winget_output(raw: bytes) -> str:
    """Dekodiert die winget-Ausgabe BOM-bewusst (UTF-16 oder UTF-8)."""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8-sig", errors="replace")


def list_installed_apps(timeout: float = 180.0) -> list[InstalledApp]:
    """Liest die installierten Programme via `winget list` aus.

    Raises:
        WinGetUnavailable: winget ist nicht auffindbar.
        WinGetTimeout: winget hat das Zeitlimit ueberschritten.

    Hinweis: benoetigt eine Internetverbindung.
    """
    if shutil.which("winget") is None:
        raise WinGetUnavailable(
            "winget wurde nicht gefunden. Der 'App-Installer' muss vorhanden sein "
            "(Windows 10/11, ueblicherweise vorinstalliert)."
        )

    try:
        proc = subprocess.run(
            list(_WINGET_LIST_ARGS),
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:  # winget verschwand zwischen which() und run()
        raise WinGetUnavailable("winget konnte nicht gestartet werden.") from exc
    except subprocess.TimeoutExpired as exc:
        raise WinGetTimeout(
            f"'winget list' hat laenger als {timeout:.0f} Sekunden gebraucht."
        ) from exc

    text = _decode_winget_output(proc.stdout or b"")
    apps = _parse_winget_list(text)

    # winget vorhanden (which() ok), lieferte aber keine brauchbare Liste:
    # typisch auf Windows 10 mit fehlendem/veraltetem "App-Installer".
    if not apps and (proc.returncode != 0 or not text.strip()):
        raise WinGetUnavailable(
            "winget lieferte keine Programmliste. Auf Windows 10 ist der "
            "'App-Installer' oft nicht (aktuell genug) installiert - bitte im "
            "Microsoft Store 'App-Installer' aktualisieren und erneut versuchen."
        )

    apps.sort(key=lambda app: app.name.lower())
    return apps


if __name__ == "__main__":
    # Manueller Sichttest (nur Lesezugriff):  python -m core.installed_apps
    try:
        result = list_installed_apps()
    except (WinGetUnavailable, WinGetTimeout) as err:
        print(f"Fehler: {err}")
        raise SystemExit(1)

    installable = [a for a in result if a.winget_installable]
    manual = [a for a in result if not a.winget_installable]
    print(f"Programme gesamt : {len(result)}")
    print(f"  winget-faehig  : {len(installable)}")
    print(f"  manuell        : {len(manual)}")
    print("\nBeispiele (winget-faehig):")
    for app in installable[:10]:
        print(f"  - {app.name}  [{app.package_id}]  ({app.source})")
    print("\nBeispiele (manuell):")
    for app in manual[:10]:
        print(f"  - {app.name}")
