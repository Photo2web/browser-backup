# Design: Software entfernen + Wiederherstell-Liste (Feature 1)

> Erstellt: 2026-07-31 · Umzugstool · Feature F1
> Status: freigegeben (Brainstorming) → Umsetzung
> Zielversion: v1.4.0

## Ziel

Auf einem neuen PC ist viel Software vorinstalliert. Der Nutzer soll **alle**
installierten Programme sehen, unerwünschte ankreuzen und deinstallieren –
wahlweise (soweit technisch bestimmt) nur für sich oder für alle Benutzer. Die
entfernten Programme werden in einer Liste gespeichert, aus der man sie später
wieder installieren kann (über die vorhandene Neuinstallation).

## Festgelegte Entscheidungen (Brainstorming)

- **GUI-Platzierung:** eigene, 4. Karte „Software entfernen" auf dem
  Startbildschirm (neben Sichern / Wiederherstellen / Neuinstallation).
- **Wiederherstellung:** in die vorhandene Neuinstallation eingebunden
  (winget-Skript/Bundle), keine Doppel-Logik.
- **Deinstallations-Ablauf:** eine Sammelbestätigung, dann der Reihe nach
  abarbeiten; still deinstallieren wo möglich, sonst Hersteller-Uninstaller.

## Ehrliche Realitäten (Design-Fakten)

1. **Scope ist nicht frei wählbar**, sondern durch die Registry-Hive bestimmt:
   `HKCU` = nur dieser Benutzer, `HKLM` = alle Benutzer. Ein systemweit
   installiertes Programm kann **nicht** „nur für mich" entfernt werden. Wir
   gruppieren/kennzeichnen nur; All-User-Deinstallation braucht Admin.
2. **„Wiederherstellung" = Neuinstallation der Software**, nicht der
   Einstellungen/Daten.
3. **Nicht jede Deinstallation ist still möglich** – manche Uninstaller öffnen
   ihr eigenes Fenster; der Nutzer klickt dort durch.

## Architektur

Zwei neue Core-Module (GUI-unabhängig, testbar) parallel zu den vorhandenen
`installed_apps.py` / `installplan.py`, plus ein neuer GUI-Screen und eine
kleine Erweiterung des Neuinstallation-Screens.

### 1. `core/installed_programs.py` (neu) – Erkennung

Liest die Windows-Uninstall-Registry über Pythons `winreg` (keine
Fremd-Abhängigkeit):

- `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall` → Scope `machine`
- `HKLM\SOFTWARE\WOW6432Node\...\Uninstall` (32-Bit) → Scope `machine`
- `HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall` → Scope `user`

Datenmodell:

```python
@dataclass(frozen=True)
class InstalledProgram:
    name: str                      # DisplayName
    publisher: str | None
    version: str | None            # DisplayVersion
    scope: str                     # "user" | "machine"
    uninstall_string: str | None
    quiet_uninstall_string: str | None
    install_location: str | None
    registry_key: str              # voller Key-Pfad (Diagnose/Dedupe)
```

**Filter** (wie „Programme & Features", damit die Liste sauber bleibt): Eintrag
wird nur übernommen, wenn
- `DisplayName` vorhanden **und** ein `UninstallString` **oder**
  `QuietUninstallString` existiert,
- `SystemComponent` **nicht** 1,
- kein Windows-Update/Hotfix (`ReleaseType` in {Update, Hotfix, Security Update}
  **oder** `ParentKeyName` gesetzt).

Öffentliche Funktion `list_installed_programs() -> list[InstalledProgram]`,
alphabetisch nach Name, dedupliziert (gleicher Name+Version aus 32/64-Bit-View
nur einmal). Parsing/Filter über kleine, einzeln testbare Hilfsfunktionen, damit
Tests eine **Mock-Registry** (Liste von Dicts) einspeisen können statt echter
`winreg`-Zugriffe.

### 2. `core/uninstallplan.py` (neu) – Deinstallation

Analog zu `installplan.py`: eine **reine, testbare** Funktion baut ein
PowerShell-Skript, plus eine `launch_*`-Funktion zum Starten.

- `build_uninstall_script(programs) -> str`: erzeugt `Deinstallieren.ps1`, das
  - sich **selbst als Admin eleviert** (UAC), sobald ein `machine`-Programm dabei
    ist – dasselbe Selbst-Elevations-Muster wie `installplan._PS_TEMPLATE`;
  - je Programm den **stillen** Weg wählt: `QuietUninstallString` falls
    vorhanden; bei MSI-Uninstallern (`MsiExec.exe /X{GUID}`) auf
    `msiexec /x{GUID} /qn /norestart` umschreiben; sonst den normalen
    `UninstallString` ausführen (Hersteller-Uninstaller erscheint);
  - Erfolg/Fehler je Programm zählt und am Ende zusammenfasst.
- `write_and_launch_uninstall(programs, work_dir) -> Path`: schreibt das Skript
  (UTF-8-BOM, wie `installplan`) und startet es in eigenem Konsolenfenster
  (`CREATE_NEW_CONSOLE`), ohne das Tool zu blockieren.

Das Skript führt Registry-`UninstallString`-Werte aus – das sind exakt die
Befehle, die Windows selbst zur Deinstallation nutzt (vertrauenswürdig).

### 3. `gui/uninstall_screen.py` (neu) – die 4. Karte

`UninstallScreen(master, on_back)`:
- `‹ Zurueck`-Button + Titel (wie die anderen Modi).
- Registry-Scan beim Anzeigen (`on_show`) im **Worker-Thread** (Karte erscheint
  sofort, Liste füllt sich gleich danach); Scan ist offline und schnell.
- Zwei Gruppen: **„Nur dieser Benutzer"** und **„Alle Benutzer (Admin nötig)"**,
  je Programm eine Checkbox mit Name + Version + Hersteller.
- „Alle auswählen" / „Alle abwählen".
- Button **„Ausgewählte entfernen"** → **eine** Sammelbestätigung
  (`ask_yes_no`), die jedes betroffene Programm auflistet und „Alle Benutzer"
  klar als Admin-Aktion (UAC) markiert → dann `write_and_launch_uninstall`.
- Nach dem Start: Auswahl in die Wiederherstell-Liste schreiben (siehe 4) und
  Hinweis anzeigen, dass der Fortschritt im separaten Fenster läuft.

### 4. Wiederherstell-Liste + Einbindung in Neuinstallation

**Speicherort (persistent, pro Benutzer):**
`%APPDATA%\Umzugstool\entfernte_programme.json`. Ehrlich: enthält die *zum
Entfernen ausgewählten* Programme (nicht rückgemeldeter Skript-Erfolg).

- Neue Funktion in `core/installed_programs.py` (oder kleines
  `core/removed_list.py`): `save_removed(programs)` (merge/dedupe nach
  Name+Version, Zeitstempel) und `load_removed() -> list[dict]`.
- JSON-Schema:
  ```json
  {"tool": "Umzugstool", "tool_version": "1.4.0", "updated_at": "...",
   "programs": [{"name": "...", "publisher": "...", "version": "...",
                 "scope": "user|machine", "removed_at": "..."}]}
  ```

**Einbindung in `gui/reinstall_tab.py`:** neue, dritte Quelle **„Zuletzt
entfernte Programme"** (neben Grundausstattung + installierte). Beim Laden wird
jeder Eintrag **gegen die ohnehin geladene winget-Liste** abgeglichen
(Name-Match, case-insensitiv/normalisiert): Treffer → winget-fähig (nutzt die
`package_id` aus der winget-Liste), sonst „manuell". Ankreuzen → speist die
vorhandene `write_install_plan`/winget-Pipeline. **Kein** winget-Zugriff im
Entfernen-Screen selbst.

### 5. Router / Home

- `gui/home_screen.py`: 4. Karte „Software entfernen" (neues Icon in
  `gui/home_icons.py`, kind `remove`/`uninstall`), Callback `on_uninstall`.
- `gui/app.py`: `UninstallScreen` als weiterer Screen, `show_mode("uninstall")`
  mit `on_show()`.

## Datenfluss

```
[Karte öffnen] → Worker: list_installed_programs() → Gruppen-Checklisten
[Ausgewählte entfernen] → Sammelbestätigung → write_and_launch_uninstall()
                                            → save_removed(auswahl)  → JSON
...später...
[Neuinstallation] → winget-Liste laden (wie bisher)
                  → Quelle „Zuletzt entfernte" = load_removed() gegen winget matchen
                  → ankreuzen → write_install_plan() (bestehend)
```

## Fehlerbehandlung

- Kein Programm gefunden / Registry nicht lesbar → Hinweis, kein Absturz.
- Einzelner unlesbarer Registry-Eintrag → überspringen, weiterlesen.
- Keine Auswahl → Fehlermeldung.
- JSON nicht schreibbar → Log-Hinweis, Deinstallation läuft trotzdem.
- Nicht-Windows / `winreg` fehlt → leere Liste (Tests laufen plattformunabhängig
  über die Mock-Ebene).

## Sicherheit

- **Echte Deinstallation wird nie an Mikes System getestet** – nur die Logik
  (Parsing, Filter, Skript-Erzeugung, JSON) gegen Mock-Registry/Temp. Der
  End-to-End-Lauf gehört auf den Zielrechner.
- Doppelte UI-Absicherung: Sammelbestätigung nennt jedes Programm; „Alle
  Benutzer" ist als Admin/UAC-Aktion gekennzeichnet.

## Tests (unittest)

- `installed_programs`: Parsing eines Mock-Eintrags → `InstalledProgram`;
  Filter lässt System/Update/namelose Einträge weg; Scope-Zuordnung user/machine;
  Dedupe 32/64-Bit.
- `removed_list`: save→load Round-Trip, Merge/Dedupe, defektes JSON → leere Liste.
- `uninstallplan`: Skript enthält still-Weg (QuietUninstallString), MSI-Umschreibung
  `/qn`, Elevation nur wenn machine-Programm dabei, Fallback normaler
  UninstallString; leere Auswahl.
- `reinstall`-Quelle: entfernte Einträge werden gegen eine (gemockte) winget-Liste
  in winget-fähig/manuell aufgeteilt.

## Betroffene/neue Dateien

- **neu** `core/installed_programs.py`, `core/uninstallplan.py`,
  `core/removed_list.py` (oder in installed_programs integriert),
  `gui/uninstall_screen.py`
- **geändert** `gui/home_screen.py`, `gui/home_icons.py`, `gui/app.py`,
  `gui/reinstall_tab.py`, `core/__init__.py` (v1.4.0)
- **neu** `tests/test_installed_programs.py`, `tests/test_uninstallplan.py`
  (+ Ergänzung in `tests/test_installplan.py` für die neue Quelle)
- Doku: README, docs/FORTSCHRITT.md; EXE-Build.

## Nicht-Ziele (YAGNI)

- Keine Rückmeldung des tatsächlichen Deinstallations-Erfolgs ins Tool (Skript
  läuft eigenständig/elevated); die Liste = getroffene Auswahl.
- Keine Wiederherstellung von Programm-Einstellungen/-Daten.
- Kein Erzwingen von „nur für mich" bei systemweiten Programmen (technisch nicht
  möglich).
