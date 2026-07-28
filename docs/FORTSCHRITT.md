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
- Echter End-to-End-Restore-Test auf einem Zweitgeraet, sobald verfuegbar.

## Nutzer-Feedback nach erstem GUI-Test (2026-07-26)

**Status:** ✅ Umgesetzt.

### Erledigt
- **Dialog-Fehler behoben:** Prozess-Warnung-Dialog (`gui/dialogs.py`)
  hatte eine fest geratene Groesse ("440x200"), die zu niedrig war —
  der "Abbrechen"-Button ragte unter die sichtbare Kante. Jetzt wird die
  Groesse aus `winfo_reqwidth()`/`winfo_reqheight()` berechnet (tatsaechlich
  benoetigt: 573x330) und der Dialog mittig ueber dem Hauptfenster
  positioniert. Ausserdem schliesst Escape den Dialog jetzt immer als
  "Abbrechen", unabhaengig vom Button.
- **Admin-Neustart bewusst NICHT eingebaut:** Mike vermutete, dass
  "Permission denied"-Fehler durch Admin-Rechte umgangen werden koennten.
  Klargestellt: die beobachteten Fehler waren Datei-**Sperren** durch den
  laufenden Browser-Prozess (Sharing Violation), keine ACL-Restriktion —
  Admin-Rechte helfen dagegen nicht, und ein "Als Admin starten"-Button
  wuerde PROJEKT.md §2 ("keine Adminrechte noetig") widersprechen sowie
  potenziell Datei-Besitzer-Probleme fuer das normale Konto erzeugen.
  Mike hat dem zugestimmt, Feature entfaellt.
- **Mehr Browser erkannt** (`core/browsers.py`): Opera, Opera GX, Brave,
  Vivaldi, Ecosia zusaetzlich zu Firefox/Chrome/Edge. Alle nutzen denselben
  generischen `detect_chromium()`-Mechanismus. Auf Mikes System real
  verifiziert:
  - Opera: `%APPDATA%\Opera Software\Opera Stable` (kein "User Data"-
    Zwischenordner, anders als die uebrigen Chromium-Forks!). Dabei zwei
    Bugs gefunden und behoben: leerer `info_cache`-Name fiel nicht auf den
    Ordnernamen zurueck (`.get("name") or folder_name` statt `.get("name",
    folder_name)`), und ein verwaister `info_cache`-Eintrag ohne
    existierenden Profilordner wurde als Phantom-Profil angezeigt (jetzt
    per Existenz-Check gefiltert).
  - Ecosia: urspruengliche Annahme `%LOCALAPPDATA%\Ecosia\User Data` war
    FALSCH — realer Ordner heisst `EcosiaBrowser`. Per PowerShell-Suche auf
    Mikes System gefunden und korrigiert.
  - Brave/Vivaldi/Opera GX: NICHT verifiziert (nicht auf Mikes System
    installiert), gut dokumentierte Standardpfade, als `# UNSICHER`
    markiert falls sich das jemals als falsch herausstellt.
  - `core/blacklist.py`: alle neuen Browser-Keys als "chromium" behandelt
    (gleicher Chromium-Unterbau -> gleiche Cache-Ordnernamen).
  - `core/processes.py`: Prozessnamen fuer alle neuen Browser ergaenzt
    (opera.exe, brave.exe, vivaldi.exe, ecosia.exe — teils ANNAHME).
- **Sichern-Tab auf Checkliste umgebaut** (`gui/backup_tab.py`): statt
  Browser-/Profil-Dropdown jetzt eine Liste aller gefundenen Browser-
  Profil-Kombinationen mit Checkbox + "Alle auswaehlen"/"Alle abwaehlen".
  Ausgewaehlte Profile werden nacheinander im selben Worker-Thread
  gesichert (je eine eigene ZIP-Datei), Log/Fortschritt zeigen
  `[i/n] Browser / Profil: ...`, Abschluss-Dialog fasst alle Ergebnisse
  zusammen (Gesamtdateien, gesperrte Dateien, Chromium-Hinweis falls
  mindestens ein Chromium-Browser dabei war). Prozess-Check laeuft pro
  betroffenem Browser nur einmal, auch wenn mehrere seiner Profile
  ausgewaehlt sind.
- Ende-zu-Ende getestet (echte Dateien, kein Restore): Firefox 'default'
  (47 B) + Chrome 'Profil 1' (11,8 MB nach Cache-Ausschluss) gleichzeitig
  ausgewaehlt -> zwei korrekte ZIP-Dateien, korrekte Sammel-Zusammenfassung
  (637 Dateien gesamt, Chromium-Hinweis erschien wie erwartet).

- **Wiederherstellen-Tab auf Mehrfachauswahl umgebaut** (`gui/restore_tab.py`):
  Mike fragte, ob sich beim Wiederherstellen ebenfalls nur bestimmte
  Browser auswaehlen lassen — auch wenn (wie im Sichern-Tab jetzt Standard)
  jedes Profil einzeln als eigene ZIP gesichert wurde. Umgesetzt:
  - "Backup-ZIPs auswaehlen ..." oeffnet einen Mehrfachauswahl-Dialog
    (`filedialog.askopenfilenames`) statt nur einer einzelnen Datei.
  - Jede ausgewaehlte ZIP wird per Manifest (Feld `browser`) automatisch
    einem installierten Ziel-Browser zugeordnet. Ist der Quell-Browser
    hier nicht installiert, erscheint die Zeile deaktiviert mit Hinweis
    "wird uebersprungen" statt eines erratenen/falschen Ziels.
  - Pro Zeile zusaetzlich ein Ziel-Profil-Dropdown: vorbelegt mit dem
    exakten Namens-Treffer aus dem Manifest, sonst mit dem Standardprofil
    des Ziel-Browsers — der Nutzer kann es jederzeit manuell aendern.
  - "Alle auswaehlen"/"Alle abwaehlen" wie im Sichern-Tab.
  - Ein gemeinsames Sicherheits-Backup- und Local-State-Flag gilt fuer
    den ganzen Batch (Local State wird ohnehin nur dort angewendet, wo
    das Manifest `has_local_state` bestaetigt UND der Ziel-Browser
    Chromium-basiert ist — bei allen anderen Eintraegen ein stiller No-Op).
  - EIN gemeinsamer Bestaetigungs-Dialog vor dem Start listet alle
    betroffenen Profile auf (statt N Einzel-Dialogen).
  - Manifest-Textanzeige (fruehere Version: ein grosses Textfeld) entfaellt
    zugunsten der kompakten Pro-Zeile-Darstellung (Browser, Quell-Profil,
    Erstellungsdatum direkt im Checkbox-Label).
- Getestet OHNE einen echten Restore auszuloesen (Mikes reale Profile
  bleiben unangetastet, siehe "Zurueckgestellt" oben): Mehrfachauswahl von
  2 Test-ZIPs -> beide korrekt erkannt, Ziel-Profile korrekt vorbelegt.
  Zusaetzlich simuliert: Ziel-Browser nicht installiert -> Zeile korrekt
  deaktiviert, taucht nicht in der finalen Auswahl auf.

### Offen / empfohlen
- Mike sollte `python main.py` mit der neuen Checkliste in beiden Tabs
  (Sichern + Wiederherstellen, inkl. Opera/Ecosia) einmal selbst
  durchklicken.
- Brave/Vivaldi/Opera GX bei Gelegenheit gegenpruefen, falls verfuegbar.
- Echter Restore-Test mit der neuen Mehrfachauswahl auf einem Zweitgeraet,
  sobald verfuegbar (siehe "Zurueckgestellt" oben).

## Phase 3 — Feinschliff & Packaging

**Status:** ✅ Abgeschlossen (2026-07-26).

### Erledigt
- **Fehlerbehandlung nachgeschaerft** (gezielte Suche nach Stellen, an
  denen Sperren/Rechte-Fehler NICHT abgefangen wurden):
  - `core/backup.py`: `os.walk()` ignoriert per Default JEDEN Fehler beim
    Auflisten eines gesperrten/unlesbaren Unterordners lautlos — ohne
    Eintrag im Ergebnis. Jetzt per `onerror`-Callback in dieselbe
    `locked_files`-Liste eingetragen wie einzelne Datei-Fehler.
  - `core/restore.py`: `dest_path.parent.mkdir()` lag AUSSERHALB des
    try-Blocks — ein einzelner Ordner-Rechtefehler haette die komplette
    Wiederherstellung abgebrochen statt nur die eine Datei zu
    ueberspringen. In den try-Block verschoben, zusaetzlich
    `zipfile.BadZipFile` mit abgefangen.
  - `gui/restore_tab.py`: Beim Einlesen einer beschaedigten/keiner echten
    ZIP-Datei fing der Code nur `(KeyError, OSError)` ab — `read_manifest()`
    kann aber auch `zipfile.BadZipFile` oder `json.JSONDecodeError` werfen.
    Erweitert; getestet mit einer absichtlich kaputten ZIP-Datei (keine
    Exception mehr, saubere Log-Meldung).
  - Alle drei Fixes mit gezielten Tests verifiziert (siehe Commit-Historie).
- **README.md** geschrieben: Funktionsuebersicht, Bedienung (Sichern +
  Wiederherstellen Schritt fuer Schritt), deutlicher Chromium-Passwort-
  Abschnitt ganz oben, bekannte v1-Einschraenkungen, Projektstruktur,
  Build-Anleitung.
- **PyInstaller-Build eingerichtet und GETESTET** (nicht nur dokumentiert):
  - `requirements-dev.txt` (zusaetzlich zu `requirements.txt`: `pyinstaller`).
  - `build.ps1` — Wrapper-Skript mit Vorab-Check, ob PyInstaller installiert ist.
  - Exakter Build-Befehl:
    ```
    pyinstaller --onefile --windowed --name BrowserBackup --collect-all customtkinter main.py
    ```
    `--collect-all customtkinter` ist noetig, weil customtkinter eigene
    Theme-/Asset-Dateien ausliefert, die PyInstaller sonst nicht automatisch
    mitnimmt (sonst Absturz mit Theme-Fehler). `psutil` braucht keinen
    Extra-Flag (eingebauter PyInstaller-Hook).
  - Build tatsaechlich ausgefuehrt: `dist\BrowserBackup.exe` (~31 MB, wegen
    mitgebundelter customtkinter-Abhaengigkeiten wie Pillow/numpy) erzeugt.
  - `.exe` real gestartet und geprueft, dass der Prozess stabil laeuft
    (kein Sofort-Absturz durch fehlende Assets) — dann sauber beendet.

### Auf v1.1 verschoben (final, siehe auch oben)
- Restore: "Neues Profil anlegen" (Firefox `profiles.ini` + Chromium
  `info_cache`-Erzeugung).
- Selektives Mergen einzelner DPAPI-/`os_crypt`-Keys bei Chromium-Restore.
- Pruefen, ob `WebStorage/`, `gmp-widevinecdm/`, `gmp-gmpopenh264/`,
  `load_statistics.db`, `EntityExtraction/` doch ausgeschlossen werden
  sollten (aktuell bewusst konservativ NICHT ausgeschlossen).
- Brave/Vivaldi/Opera GX auf einer echten Installation verifizieren.
- Echter End-to-End-Restore-Test (Sicherheitsgruende, siehe oben) —
  empfohlen auf einem neuen/leeren Laptop, sobald verfuegbar.
- Admin-Neustart-Option bewusst NICHT eingebaut (siehe Nutzer-Feedback-
  Abschnitt oben) — loest das eigentliche Sperr-Problem nicht.

### Fuer Mike zum Ausprobieren
- `python main.py` — Quellcode-Version.
- `dist\BrowserBackup.exe` — bereits gebauter, portabler Build (kann direkt
  auf einen USB-Stick oder einen anderen PC kopiert werden, um den
  Wiederherstellen-Test aus "Zurueckgestellt" durchzufuehren).

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

---

## v1.1 — Tab „Neuinstallation" (App-Migration via winget)

Spezifikation: `docs/NEUINSTALLATION_SPEC.md` (freigegeben). Version → 1.1.0.

### Erledigt
- `core/installed_apps.py`: liest installierte Programme via
  `winget list --disable-interactivity`. Positionsbasiertes, locale-
  unabhaengiges Parsing (Header lokalisiert: `ID/Version/Verfügbar/Quelle`;
  Spalte „Verfügbar" nur bei Updates → 4 oder 5 Spalten). winget-faehig =
  Quelle `winget`/`msstore` + Id; sonst manuell (interne `ARP\`/`MSIX\`-Ids
  verworfen). BOM-bewusstes Decoding. 9 Unit-Tests + Realtest auf Mikes
  System (226 Programme, 92 winget-faehig, 134 manuell).
- `core/installplan.py`: erzeugt drei Dateien —
  1. `Installationsanweisung.md` (winget-faehig + manuell, lesbar),
  2. `Install-Apps.ps1` (Selbst-Elevation als Admin → PowerShell-7-Check →
     winget-Bootstrap [Add-AppxPackage-Re-Registrierung, sonst
     `Install-Module Microsoft.WinGet.Client` + `Repair-WinGetPackageManager`,
     sonst Store-Deeplink] → abgesicherte Einzelinstallation je Programm mit
     `--source`/`--exact`/`--accept-*`),
  3. `Apps.ubundle` (UniGetUI-Bundle). 9 Unit-Tests gruen.
- `gui/reinstall_tab.py` + Einbindung als dritter Segment-Button. Checkliste
  (winget-faehig ankreuzbar + „manuell" grau markiert), lazy-Load beim Oeffnen
  via Worker-Thread, Internet-Hinweis, Refresh-Button.
- Verifikation: 18 Unit-Tests gruen; generierte `Install-Apps.ps1` (real, 8
  und 92 Apps) besteht den PowerShell-Parser-Syntaxcheck; `Apps.ubundle` ist
  valides JSON; End-to-End headless im Tab getestet (laden → auswaehlen →
  3 Dateien erzeugt).

### Erweiterungen (nach Nutzer-Feedback, gleiche Version 1.1.0)
- **„Jetzt installieren"-Button:** `installplan.launch_install_script()` startet
  das erzeugte `Install-Apps.ps1` in einem eigenen Konsolenfenster
  (`CREATE_NEW_CONSOLE`); Elevation/PS7/winget regelt das Skript selbst. Im Tab
  nach „Dateien erzeugen" aktiv (nur wenn winget-faehige dabei), mit
  Sicherheits-Rueckfrage. Bewusst kein echter Lauf auf Mikes System getestet —
  Startlogik per Mock geprueft (richtiger Befehl, fehlendes Skript → Fehler).
- **Grundausstattung** (`core/essential_apps.py`): feste, kuratierte Liste
  haeufiger winget-Programme (12 Eintraege, alle IDs gegen die echte winget-
  Quelle verifiziert). Als zweite Checkliste im Tab, auch ohne winget-Laden
  waehlbar; Auswahl wird mit den installierten Programmen zusammengefuehrt und
  nach `package_id` dedupliziert. Pflege durch Editieren der Liste im Code.
- Verifikation: 24 Unit-Tests gruen; End-to-End headless (Grundausstattung →
  erzeugen → Button aktiv → Start gemockt; Firefox landet im Skript);
  Grundausstattungs-Skript besteht den PowerShell-Syntaxcheck.

### Offen fuer v1.2 (Ideen)
- Grundausstattung in der GUI editierbar + dauerhaft speichern (statt fest im
  Code) — bewusst auf spaeter verschoben.

### UniGetUI-Bundle-Schema (am Quellcode verifiziert)
- Top-Level: `export_version` (=3), `packages`, `incompatible_packages_info`,
  `incompatible_packages`.
- Paket: `Id`, `Name`, `Version`, `Source`, `ManagerName` (= `"Winget"`,
  Quelle `winget`/`msstore`). `InstallationOptions`/`Updates` optional →
  weggelassen. Manuelle Programme → `incompatible_packages` (Quelle „Local PC").

### Offen / Annahmen
- **Echter Lauf von `Install-Apps.ps1` erst auf dem Zielrechner** (analog
  Restore bewusst nicht auf Mikes Produktivsystem getestet).
- `winget list`-Parsing ist bei exotischen (CJK-)Namen fehleranfaellig; fuer
  lateinische Namen unkritisch. Moegliches Upgrade: `Get-WinGetPackage`
  (Microsoft.WinGet.Client) als strukturierte JSON-Quelle.
- msstore-Installation nutzt `--source msstore`; ob jedes msstore-Paket ohne
  Store-Anmeldung unbeaufsichtigt durchlaeuft, zeigt erst der Zielrechner.
- winget-Verfuegbarkeit auf dem Quellrechner vorausgesetzt (Windows 11).
