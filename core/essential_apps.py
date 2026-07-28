"""Kuratierte "Grundausstattung" - haeufig gebrauchte Programme fuer einen
frisch aufgesetzten Windows-Rechner.

Diese Liste ist bewusst fest im Code gehalten und leicht zu pflegen: einfach
Zeilen in ESSENTIAL_APPS ergaenzen/entfernen. Jede winget-Id wurde gegen die
echte winget-Quelle geprueft (Stand 2026-07-28) - beim Ergaenzen bitte die Id
vorher mit ``winget show --id <Id> -e`` verifizieren (Prinzip: keine erfundenen
Ids).

Die Eintraege werden ueber ``to_installed_app()`` in dasselbe ``InstalledApp``
umgewandelt, das auch die winget-Erkennung liefert - dadurch laufen sie ohne
Sonderfall durch dieselbe Erzeugen-/Installieren-Pipeline (siehe installplan.py).
"""

from __future__ import annotations

from dataclasses import dataclass

from core.installed_apps import InstalledApp


@dataclass(frozen=True)
class EssentialApp:
    """Ein vordefiniertes winget-Programm der Grundausstattung."""

    name: str
    package_id: str
    category: str
    source: str = "winget"

    def to_installed_app(self) -> InstalledApp:
        return InstalledApp(
            name=self.name,
            package_id=self.package_id,
            version=None,
            source=self.source,
        )


# Reihenfolge = Anzeigereihenfolge (nach Kategorie gruppiert).
ESSENTIAL_APPS: tuple[EssentialApp, ...] = (
    EssentialApp("Mozilla Firefox", "Mozilla.Firefox", "Browser"),
    EssentialApp("Google Chrome", "Google.Chrome", "Browser"),
    EssentialApp("Adobe Acrobat Reader (64-bit)", "Adobe.Acrobat.Reader.64-bit", "Dokumente"),
    EssentialApp("7-Zip", "7zip.7zip", "Archive"),
    EssentialApp("VLC media player", "VideoLAN.VLC", "Medien"),
    EssentialApp("Mozilla Thunderbird", "Mozilla.Thunderbird", "Kommunikation"),
    EssentialApp("Zoom Workplace", "Zoom.Zoom", "Kommunikation"),
    EssentialApp("Notepad++", "Notepad++.Notepad++", "Werkzeuge"),
    EssentialApp("Microsoft PowerToys", "Microsoft.PowerToys", "Werkzeuge"),
    EssentialApp("Visual Studio Code", "Microsoft.VisualStudioCode", "Entwicklung"),
    EssentialApp("Git", "Git.Git", "Entwicklung"),
    EssentialApp("PowerShell 7", "Microsoft.PowerShell", "Entwicklung"),
)


def essential_apps() -> list[EssentialApp]:
    """Liefert die Grundausstattung als Liste (Kopie der festen Reihenfolge)."""
    return list(ESSENTIAL_APPS)
