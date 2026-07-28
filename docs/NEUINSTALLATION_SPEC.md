# Spec: Tab „Neuinstallation" (App-Migration auf neuen Windows-Rechner)

> Erstellt: 2026-07-28 · Ziel-Version: **1.1.0** · Status: freigegeben, in Umsetzung

## 1. Ziel

Ein neuer Tab listet die auf dem aktuellen Rechner installierten Programme mit
Checkbox auf. Aus der Auswahl erzeugt das Tool Dateien, mit denen sich diese
Programme auf einem **neuen Windows-Rechner** wieder installieren lassen:

1. `Installationsanweisung.md` — lesbare Liste (winget-Apps + manuelle Apps).
2. `Install-Apps.ps1` — selbst-elevierendes PowerShell-Installationsskript.
3. `Apps.ubundle` — UniGetUI-Bundle (JSON) zum Import in die UniGetUI-GUI.

## 2. Umfang / Nicht-Ziele

**In Scope:**
- Alle installierten Programme auflisten, winget-fähige markieren.
- Drei o. g. Ausgabedateien erzeugen.
- Skript regelt: Admin-Selbst-Elevation, PowerShell-7-Check, winget/App-Installer-
  Bootstrap (der „erst Microsoft Store"-Fall), abgesicherte Einzelinstallation.

**Out of Scope (v1.1):**
- Kein automatisches Ausführen des Skripts aus dem Tool heraus (der Lauf passiert
  bewusst manuell auf dem Zielrechner).
- Keine Versions-Fixierung (immer neueste Version installieren).
- Kein Chocolatey/Scoop — nur winget (+ UniGetUI-Bundle als Alternative).

## 3. Datenmodell (`core/installed_apps.py`)

```python
@dataclass(frozen=True)
class InstalledApp:
    name: str                 # Anzeigename (winget-Spalte "Name")
    package_id: str | None    # winget-Id, None wenn nicht zuordenbar
    version: str | None
    source: str | None        # "winget" | "msstore" | None

    @property
    def winget_installable(self) -> bool:
        return bool(self.package_id) and self.source in {"winget", "msstore"}
```

## 4. Programme auslesen (`core/installed_apps.py`)

- Aufruf: `winget list --disable-interactivity` (kein Zusatzmodul nötig).
- **Braucht Internet** (winget fragt seine Quelle online ab) → vorher prüfen,
  im Tab deutlich anzeigen.
- Parsing: Kopfzeile (`Name  Id  Version  Available  Source`) liefert die
  Spalten-Startpositionen; Datenzeilen werden anhand dieser Offsets zerlegt.
  Die Spalte `Available` erscheint nur, wenn Updates vorliegen — Parser muss das
  tolerieren (Spalten dynamisch aus dem Header ableiten, nicht hart kodieren).
- Zeilen vor dem Header (Fortschritts-/Spinner-Ausgabe) überspringen.
- Ausgabe als UTF-8 lesen (Encoding-Fehler ersetzend behandeln).
- `Id` leer → `source=None` → **manuell**. `Id` gesetzt + bekannte Source →
  **winget-fähig**.
- Fehlerfälle: winget nicht vorhanden → eigene Exception (`WinGetUnavailable`),
  vom Tab als klare Meldung angezeigt; Timeout → Meldung.
- **Annahme/Risiko:** Fixed-width-Parsing ist bei exotischen (CJK-)Namen fehler-
  anfällig; für lateinische Programmnamen unkritisch. Mögliches Upgrade später:
  `Get-WinGetPackage` (Microsoft.WinGet.Client) als strukturierte JSON-Quelle.

## 5. Ausgabedateien (`core/installplan.py`)

Reine String-Erzeugung aus einer Liste ausgewählter `InstalledApp` → unit-testbar.

### 5.1 `Installationsanweisung.md`
```
# Installationsanweisung — erzeugt am <Datum> mit BrowserBackup <Version>
Quelle: <PC-Name>

## Automatisch installierbar (winget)
- <Name> — `<PackageId>`
...

## Manuell zu installieren
- <Name> (kein passendes winget-Paket gefunden)
...
```

### 5.2 `Install-Apps.ps1`
Ablauf (Reihenfolge):
1. **Selbst-Elevation**: Admin-Rechte prüfen; falls nicht erhöht, per
   `Start-Process -Verb RunAs` neu starten (mit Re-Launch-Guard gegen Schleife).
2. **PowerShell-7-Check**: `pwsh` (>=7) vorhanden? Wenn nein → Hinweis + Angebot,
   via `winget install --id Microsoft.PowerShell -e` zu installieren.
3. **winget-/App-Installer-Bootstrap** (fängt den „erst Microsoft Store"-Fall ab):
   - `winget` verfügbar? Wenn ja → weiter.
   - Wenn nein → erst Re-Registrierung:
     `Add-AppxPackage -RegisterByFamilyName -MainPackage Microsoft.DesktopAppInstaller_8wekyb3d8bbwe`
   - Wenn weiter nicht verfügbar → Bootstrap über offizielles Modul:
     `Install-Module Microsoft.WinGet.Client` + `Repair-WinGetPackageManager -AllUsers`.
   - Letzter Fallback → klare Meldung + Store-Deeplink, Skript bricht sauber ab.
4. **Installation** je Programm, einzeln abgesichert (ein Fehlschlag stoppt nicht
   den Rest):
   `winget install --id <Id> --source <Source> -e --accept-package-agreements --accept-source-agreements`
   (`--source` wird mitgegeben, weil msstore-Produkt-Ids sonst fehlschlagen;
   `--accept-source-agreements` fängt den msstore-Zustimmungsdialog ab.)
5. Abschluss: Zusammenfassung (erfolgreich / fehlgeschlagen).

Die App-Ids werden als PowerShell-Array in das Skript generiert.

### 5.3 `Apps.ubundle`
- Format: UniGetUI-Bundle als JSON (`.ubundle`).
- **Offen:** exaktes JSON-Schema wird vor der Generierung an einem echten
  UniGetUI-Bundle verifiziert (kein erfundenes Format) — Internet-Fetch der
  UniGetUI-Doku/eines Beispiels (bereits freigegeben).

## 6. GUI (`gui/reinstall_tab.py`, Einbindung in `gui/app.py`)

- Dritter Segment-Button „Neuinstallation" neben „Sichern"/„Wiederherstellen".
- Beim Öffnen: Programme im Hintergrund-Thread laden (bestehendes `Worker`-Muster),
  solange Ladehinweis anzeigen. Internet-Hinweis sichtbar.
- Checkliste (`CTkScrollableFrame`, Muster aus `backup_tab.py`):
  - **Jede** Zeile hat eine Checkbox (Mike-Wunsch: alle per Checkbox wählbar).
  - winget-fähige Zeile: Name + `Id` + Häkchen → kommt in `.md`, `.ps1`, `.ubundle`.
  - manuelle Zeile: Name + Label „(manuell)" → Häkchen nimmt sie nur in die
    `.md`-Anleitung auf. Standard: nicht angehakt (Liste kann lang sein).
  - Buttons „Alle winget-fähigen auswählen" / „Alle abwählen".
- Zielordner wählen → „Dateien erzeugen" → Abschluss-Dialog mit den erzeugten
  Pfaden.

## 7. Fehlerbehandlung
- winget fehlt / Timeout beim Laden → klare Meldung im Tab, kein Absturz.
- Leere Auswahl → Info-Dialog.
- Schreibfehler beim Erzeugen → Fehlerdialog mit Pfad/Grund.

## 8. Testplan
- `core/installed_apps.py`: Unit-Test des Parsers mit Beispiel-`winget list`-Ausgabe
  (mit und ohne `Available`-Spalte); echter Lauf auf Mikes System zur Sichtprüfung.
- `core/installplan.py`: Unit-Tests für `.md` und `.ps1` (erwartete Strings/Ids).
- `Install-Apps.ps1`: PowerShell-Parser-Syntaxcheck (wie bei `build.ps1`) +
  Logik-Durchsicht. **Echter Lauf erst auf dem neuen Rechner** (analog Restore).
- `.ubundle`: gegen echtes UniGetUI-Schema erzeugt, Import-Test bleibt dem
  Zielrechner überlassen.

## 9. Umsetzungsschritte
1. `core/installed_apps.py` + Parser-Unit-Test.
2. `core/installplan.py` (`.md` + `.ps1`) + Unit-Tests; `.ubundle` nach Schema-
   Verifikation.
3. `gui/reinstall_tab.py` + Einbindung in `gui/app.py`.
4. PS-Syntaxcheck, Version → 1.1.0, README + FORTSCHRITT.md ergänzen, Commit.

## 10. Offene Annahmen
- winget ist auf Mikes aktuellem Rechner vorhanden (Windows 11) — bestätigt sich
  beim ersten Laden.
- UniGetUI-Bundle-Schema wird vor Generierung verifiziert.
- Kein realer Skript-Lauf im Rahmen dieser Umsetzung (Zielrechner-Test später).
