# FORTSCHRITT — BrowserBackup

## Phase 0 — Realitaets-Check der Profilstrukturen

**Status:** ✅ Abgeschlossen (2026-07-26).

### Erledigt
- `inspect_profiles.py` erstellt und zweimal auf Mikes System ausgefuehrt
  (Top-Level-Report + gezielter Drilldown fuer `storage` (Firefox),
  `Service Worker` und `WebStorage` (Chromium)). Nur Lesezugriff.
- Finale Blacklist aus echten Messungen abgeleitet, siehe
  `PHASE0_NOTIZEN.md` (Abschnitt "Finale Blacklist") fuer alle Details
  und Groessenangaben. Kurzfassung:
  - Firefox: `crashes/`, `datareporting/`, `minidumps/`, `parent.lock`,
    `shader-cache/` + Pfadmuster `storage/*/*/cache` (183 MB Fund).
    Kompat-Eintraege fuer aeltere Versionen: `cache2/`, `startupCache/`,
    `thumbnails/`, `OfflineCache/`, `.parentlock`, `lock`.
  - Chromium: `Cache/`, `Code Cache/`, `GPUCache/`, `DawnGraphiteCache/`,
    `DawnWebGPUCache/` + Pfadmuster `Service Worker/CacheStorage/` und
    `Service Worker/ScriptCache/` (zusammen der dominante Grossteil des
    Service-Worker-Ordners). Kompat-Eintraege fuer aeltere Versionen:
    `GrShaderCache/`, `ShaderCache/`, `Media Cache/`, `Application Cache/`,
    `component_crx_cache/`, `Crashpad/`.
- Restore-Entscheidung bestaetigt: v1 unterstuetzt nur "vorhandenes
  Profil ueberschreiben" (siehe `PHASE0_NOTIZEN.md`).
- Blacklist-Umfang bestaetigt: konservative Variante (nur eindeutig als
  Cache identifizierte Ordner/Muster).
- Git-Repository initialisiert, Phase 0 committet.

## Phase 1 — Kernlogik (ohne GUI)

**Status:** ✅ Abgeschlossen (2026-07-26).

### Erledigt
- `core/__init__.py`: Paket-Grundlage + `TOOL_VERSION`-Konstante.
- `core/browsers.py`: `Browser`/`Profile`-Dataclasses, Erkennung von
  Firefox (`profiles.ini`) und Chromium (`Local State` → `info_cache`).
  Manuell getestet via `python -m core.browsers` — hat alle 2 Firefox-,
  2 Chrome- und 1 Edge-Profil korrekt erkannt (deckt sich mit Phase-0-Messung).
- `core/blacklist.py`: finale Blacklist aus Phase 0 implementiert, inkl.
  Pfadmuster-Unterstuetzung (`storage/*/*/cache`,
  `Service Worker/CacheStorage`, `Service Worker/ScriptCache`) via `fnmatch`.
- `core/backup.py`: `backup_profile()` — ZIP mit `ZIP_DEFLATED`, wendet
  Blacklist beim Durchlaufen an (kein Abstieg in ausgeschlossene Ordner,
  nicht nachtraeglich gefiltert), erzeugt `backup_manifest.json`, nimmt bei
  Chromium die gemeinsame `Local State` mit auf. Gesperrte/unlesbare
  Dateien werden einzeln abgefangen (kein Abbruch) und im `BackupResult`
  gesammelt. Fortschritt ueber Callback `(aktuell, gesamt, meldung)`.
  Manuell getestet via `python -m core.backup` (kleines Profil) UND
  gezielt gegen das grosse `default-release`-Profil (316 MB, Firefox lief
  dabei) — 554 gesperrte Dateien wurden korrekt einzeln abgefangen, 101
  Dateien gesichert, kein Absturz. Reale Bestaetigung des in PROJEKT.md
  §8.8 geforderten Verhaltens.
- `core/restore.py`: `restore_profile()` + `read_manifest()` — entpackt
  `profile/`-Eintraege ins Ziel-Profil (ueberschreibt vorhandene Dateien),
  optionales Sicherheits-Backup des Ziels (per Wiederverwendung von
  `backup_profile()`, Cache dabei bewusst NICHT ausgeschlossen), Local
  State nur bei explizitem `restore_local_state=True` inkl. eigenem
  Backup als `Local State.bak_<timestamp>` (PROJEKT.md §6.3). Unterstuetzt
  nur "vorhandenes Profil ueberschreiben" (v1-Scope, siehe unten).
- `core/processes.py`: `find_running_processes()`, `is_browser_running()`,
  `terminate_browser()` (erfordert `confirm=True`) via `psutil`.
  Manuell getestet via `python -m core.processes`.

### Zurueckgestellt
- `restore.py` konnte nicht gegen ein echtes Ziel-Profil getestet werden
  (Mike moechte seine echten Profile nicht riskieren). Test folgt, sobald
  ein neuer/leerer Laptop zur Verfuegung steht. Bis dahin nur durch
  Code-Review + die Wiederverwendung von `backup_profile()` fuer das
  Sicherheits-Backup abgesichert.

## Phase 2 — GUI (customtkinter)

**Status:** ✅ Abgeschlossen (2026-07-26).

### Erledigt
- `gui/app.py`: Hauptfenster, Dark-Theme, `CTkSegmentedButton` zum
  Umschalten zwischen "Sichern"/"Wiederherstellen".
- `gui/worker.py`: `Worker`-Klasse — fuehrt Backup/Restore in einem
  Thread aus, reicht Fortschritt/Ergebnis ueber eine `queue.Queue` an
  die GUI weiter (Poll-Muster via `widget.after()`, GUI friert nicht ein).
- `gui/dialogs.py`: wiederverwendete Dialoge — Prozess-Warnung mit drei
  Optionen (Beenden/Trotzdem fortfahren/Abbrechen), Info-/Fehler-/
  Ja-Nein-Dialoge. Loest bei Bedarf das echte Toplevel-Fenster auf
  (`winfo_toplevel()`), damit `transient()`/`grab_set()` auch bei
  Aufrufen aus einem Frame heraus funktionieren.
- `gui/backup_tab.py`: Browser-/Profil-Dropdown, Zielordner-Auswahl,
  Cache-Checkbox (Default an), Prozess-Check vor Start, Fortschrittsbalken
  + Log, Abschluss-Dialog inkl. Chromium-Passwort-Hinweis (PROJEKT.md §6.2).
- `gui/restore_tab.py`: ZIP-Auswahl mit read-only Manifest-Anzeige,
  automatische Ziel-Vorauswahl passend zum Manifest, Ziel-Browser-/
  Ziel-Profil-Dropdown, Sicherheits-Backup-Checkbox (Default an),
  Local-State-Checkbox (nur bei Chromium-Ziel aktiv, Default aus gemaess
  PROJEKT.md §6.3), Bestaetigungs-Dialog vor dem Ueberschreiben,
  Prozess-Check, Abschluss-Dialog. Bewusst KEINE Radio-Auswahl
  "neu anlegen" (v1-Scope), stattdessen Hinweistext.
- `main.py`: Einstiegspunkt (`python main.py`).
- `requirements.txt`: `customtkinter`, `psutil`.
- Smoke-Tests durchgefuehrt (Fenster aufgebaut, kurz sichtbar, wieder
  geschlossen — keine echten Backups/Restores ausgeloest):
  - Alle 3 Browser + Profile werden in beiden Tabs korrekt geladen.
  - Manifest-Anzeige mit echter Test-ZIP geprueft (Browser, Profilname,
    Erstellt-am, Quellrechner, Quell-OS korrekt dargestellt).
  - Ziel-Vorauswahl passend zum Manifest funktioniert.
  - Local-State-Checkbox korrekt deaktiviert bei Firefox-Ziel, aktiviert
    bei Chrome-Ziel.
  - Der eigentliche "Wiederherstellen"-Button wurde NICHT ausgeloest
    (haette ein echtes Profil ueberschrieben).

### Offen / empfohlen
- Mike sollte `python main.py` selbst einmal interaktiv durchklicken
  (Layout, Klick-Verhalten, Fenstergroesse) — von hier aus liess sich nur
  der Aufbau pruefen, nicht der visuelle Eindruck.
- Echter End-to-End-Restore-Test auf einem Zweitgeraet, sobald verfuegbar.

### Auf v1.1 verschoben (bewusst, nicht vergessen)
- Restore: "Neues Profil anlegen" (Firefox `profiles.ini`-Eintrag +
  Chromium `info_cache`-Erzeugung) — Risiko eines beschaedigten Profils
  ohne Testreihe zu hoch fuer v1.
- Pruefen, ob folgende grosse, nicht eindeutig cache-benannte Ordner
  in einer spaeteren Version doch ausgeschlossen werden sollten:
  - Chromium `WebStorage/` (bei Mike bis zu 326,7 MB in einem Origin-Ordner)
  - Firefox `gmp-widevinecdm/` (21,6 MB), `gmp-gmpopenh264/` (1,1 MB)
  - Chromium `load_statistics.db` (+`-wal`/`-shm`, ~36,5 MB bei Edge)
  - Edge `EntityExtraction/` (8,4 MB)
- Selektives Mergen einzelner DPAPI-/`os_crypt`-Keys bei Chromium-Restore
  (bereits in PROJEKT.md §6.3 als Nice-to-have vermerkt).

### Getroffene Annahmen (Phase 0)
- `configparser` mit UTF-8 fuer `profiles.ini`.
- Es wird von Standard-Installationspfaden ausgegangen (kein Microsoft-
  Store-Chrome o.ae. gesondert behandelt) — auf Mikes System nicht
  aufgetreten, bleibt eine Annahme fuer andere Systeme.
- Firefox-Cache-Ordner (`cache2` etc.) koennen je nach Firefox-Version im
  Roaming-Profil ODER unter `%LOCALAPPDATA%` liegen. v1 sichert nur das
  Roaming-Profil (wie in PROJEKT.md §4.1 spezifiziert) — der ausgelagerte
  lokale Cache wird dadurch ohnehin nie mitgesichert, das ist gewuenscht.
