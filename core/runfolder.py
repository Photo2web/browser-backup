"""Lauf-Ordner-Logik fuer den Sichern-Modus.

Ein Sicherungslauf buendelt alle Modul-Sicherungen einer Sitzung in einem
Ordner mit Zeitstempel (``Umzug_<YYYY-MM-DD_HHMM>``); jedes Modul bekommt darin
seinen eigenen Unterordner (``Browser``, ``PersoenlicheDaten``). Rein
dateisystembasiert und ohne GUI -> gut testbar.
"""

from datetime import datetime
from pathlib import Path


def _default_timestamp() -> str:
    """Zeitstempel im Format YYYY-MM-DD_HHMM (wie core/personal_data.py)."""
    return datetime.now().strftime("%Y-%m-%d_%H%M")


# Öffentlicher Alias
timestamp = _default_timestamp


class RunFolder:
    """Ein Sicherungslauf: <base_dir>/Umzug_<timestamp>/ mit Modul-Unterordnern."""

    def __init__(self, base_dir, timestamp: str | None = None):
        self.base_dir = Path(base_dir)
        self.timestamp = timestamp or _default_timestamp()
        self.root = self.base_dir / f"Umzug_{self.timestamp}"

    def module_dir(self, name: str) -> Path:
        """Legt <root>/<name> an (falls noetig) und gibt den Pfad zurueck."""
        target = self.root / name
        target.mkdir(parents=True, exist_ok=True)
        return target
