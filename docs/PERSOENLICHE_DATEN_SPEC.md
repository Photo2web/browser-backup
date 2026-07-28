# Spezifikation: Persönliche Daten sichern & wiederherstellen (v1.2)

Status: **entworfen** (Umsetzung folgt)
Zuletzt aktualisiert: 2026-07-28

Neuer Programmteil zum Sichern und Wiederherstellen der persönlichen
Windows-Ordner (Dokumente, Bilder, Musik, Videos, Desktop, Downloads) —
unabhängig von der bestehenden Browser-Profil-Logik. Zusätzlich:
Speicherplatz-Prüfung (Quelle/Ziel) und ein Fortschrittsbalken für alle
lang laufenden Vorgänge.

---

## 1. Ziel & Abgrenzung

- **Ziel:** Beim Umzug auf einen neuen Windows-Rechner sollen neben den
  Browser-Profilen auch die persönlichen Nutzerdaten mitgenommen werden.
- **Kein** Eingriff in `core/browsers.py`, `core/backup.py`, `core/restore.py`.
  Das Feature ist ein eigenständiges Modul + eigener Tab.
- **Portabel, ohne Adminrechte** — wie das übrige Tool. Es werden nur Ordner
  im Nutzerkontext gelesen/geschrieben.

---

## 2. Ordner-Erkennung (Known Folders)

Die persönlichen Ordner können umgeleitet sein (OneDrive, NextCloud o. Ä.) —
z. B. liegt „Eigene Dokumente" ggf. unter `…\NextCloud\Dokumente`. Deshalb
werden die **echten** Pfade über die Windows-Shell-API aufgelöst, nicht hart
über `%USERPROFILE%\Documents` geraten.

- API: `SHGetKnownFolderPath` (via `ctypes`, `shell32`), mit den
  KNOWNFOLDERID-GUIDs der sechs Ordner.
- Fallback, falls die API scheitert: `%USERPROFILE%\<Standardname>` (best effort).
- Erfasste Ordner (`key` → Anzeigename → KNOWNFOLDERID):
  - `documents` → Dokumente → `FOLDERID_Documents`
  - `pictures` → Bilder → `FOLDERID_Pictures`
  - `music` → Musik → `FOLDERID_Music`
  - `videos` → Videos → `FOLDERID_Videos`
  - `desktop` → Desktop → `FOLDERID_Desktop`
  - `downloads` → Downloads → `FOLDERID_Downloads`
- Nicht vorhandene oder leere Ordner werden erkannt (`exists`) und in der GUI
  deaktiviert dargestellt.

---

## 3. Datenmodell (`core/personal_data.py`)

```python
@dataclass
class PersonalFolder:
    key: str            # "documents", "pictures", ...
    display_name: str   # "Dokumente", ...
    path: Path          # aufgelöster echter Pfad
    exists: bool

@dataclass
class FolderSize:
    total_bytes: int
    file_count: int
    walk_errors: list[str]   # unlesbare Unterordner (best effort)

@dataclass
class PersonalBackupResult:
    target: Path            # erzeugte ZIP-Datei ODER Kopie-Ordner
    folder_key: str
    mode: str               # "zip" | "copy"
    file_count: int
    skipped: list[str]      # gesperrte/unlesbare Dateien
    manifest: dict

@dataclass
class PersonalRestoreResult:
    folder_key: str
    dest: Path
    restored: int
    skipped_existing: int
    overwritten: int
    errors: list[str]
```

Funktionen:

- `detect_personal_folders() -> list[PersonalFolder]`
- `folder_size(path) -> FolderSize` — Walk mit `onerror`-Sammlung (wie in
  `backup.py`), liefert Gesamtgröße + Dateizahl.
- `free_space(path) -> int` — `shutil.disk_usage(path).free`; nutzt den nächsten
  existierenden Elternpfad, falls das Ziel noch nicht angelegt ist.
- `backup_personal_folder(folder, dest_dir, mode, progress_callback) -> PersonalBackupResult`
- `restore_personal_folder(source, dest, conflict, progress_callback) -> PersonalRestoreResult`

Fortschritt: gleiche `ProgressCallback`-Signatur `(current, total, message)` wie
in `core/backup.py`, damit Worker + GUI unverändert wiederverwendbar sind.

---

## 4. Sicherung

Pro ausgewähltem Ordner **ein** Backup-Artefakt. Modus gilt für den ganzen
Lauf (ein Radiobutton „ZIP / Kopie"):

- **ZIP** (`mode="zip"`):
  - Datei: `browserbackup_data_<key>_<YYYY-MM-DD_HHMM>.zip`
  - Inhalt: `data/<relativer_pfad>` + `backup_manifest.json`
  - `ZIP_DEFLATED`. Hinweis in der GUI: Fotos/Videos/Musik komprimieren kaum —
    ZIP kostet dann v. a. Zeit; Kopie ist bei Medien meist die bessere Wahl.
- **Kopie** (`mode="copy"`):
  - Ordner: `browserbackup_data_<key>_<YYYY-MM-DD_HHMM>/`
    mit `data/<…>` (1:1-Struktur) und `backup_manifest.json` daneben.
  - Datei-für-Datei-Kopie (`shutil.copy2`, mtime bleibt erhalten).

Gesperrte/unlesbare Dateien werden — wie bei den Profilen — **einzeln
übersprungen** und in `skipped` gesammelt; der Lauf bricht nicht ab.

### Manifest (`backup_manifest.json`)

```json
{
  "tool": "BrowserBackup",
  "tool_version": "1.2.0",
  "kind": "personal_data",
  "created_at": "2026-07-28T14:20:00",
  "folder_key": "documents",
  "folder_display_name": "Dokumente",
  "source_path": "D:\\NextCloud\\Dokumente",
  "mode": "zip",
  "file_count": 1234,
  "total_bytes": 5368709120,
  "source_host": "PC-NAME",
  "source_os": "Windows 11",
  "skipped": []
}
```

`folder_key` + `source_path` erlauben dem Restore die automatische Zuordnung
zum passenden Zielordner.

---

## 5. Speicherplatz-Prüfung

- **Größenanzeige:** Nach Auswahl werden die Ordnergrößen im Worker berechnet
  und neben der Checkbox angezeigt (z. B. „Bilder — 12,4 GB"). Darunter eine
  Zeile: Summe der Auswahl + freier Platz am Ziel.
- **Harte Prüfung vor Start** (Sichern und Wiederherstellen):
  benötigt (= Rohgröße der Auswahl, konservativ; ZIP ist höchstens so groß)
  vs. `free_space(ziel)`. Reicht es nicht → Fehlerdialog (App-Design), Abbruch.
- Formatierung: Byte-Größen menschenlesbar (`_format_bytes`), Dezimal-GB.

---

## 6. Wiederherstellung

- Quelle wählen: eine oder mehrere Backup-ZIPs **oder** ein Kopie-Ordner.
  Aus jedem Artefakt wird `backup_manifest.json` gelesen.
- **Automatische Zuordnung:** jede Zeile wird über `folder_key` dem passenden
  Bekanntordner des aktuellen Rechners zugeordnet; pro Zeile per „Anderen
  Ordner wählen" überschreibbar. Fehlt der Bekanntordner, ist die Zeile
  deaktiviert bis ein Ziel gewählt wird.
- **Konfliktverhalten pro Lauf** (Auswahl im Bestätigungsdialog vor Start):
  - `skip` — vorhandene Dateien überspringen (**Default**, zerstörungsfrei)
  - `overwrite` — Backup gewinnt immer
  - `newer` — nur überschreiben, wenn die Datei im Backup neuer ist (mtime)
- Anschließend Speicherplatz-Prüfung am Ziel (siehe §5).
- Ergebnis: `restored / skipped_existing / overwritten / errors` je Ordner,
  Zusammenfassung im Dialog.

---

## 7. GUI (`gui/personal_tab.py`)

Neuer 4. Tab „Persönliche Daten" (Segment in `app.py`). Selbst-enthalten mit
interner Umschaltung **Sichern | Wiederherstellen** (CTkSegmentedButton), damit
die Top-Leiste nicht weiter wächst.

Aufbau analog `reinstall_tab.py` (unten angepinnte Steuerung, oben die Liste):

- **Sichern-Ansicht:**
  - Checkliste der sechs Ordner (deaktiviert, wenn nicht vorhanden) mit
    Größenangabe; „Alle auswählen".
  - Radiobutton „ZIP / Kopie".
  - Zielordner-Auswahl (`filedialog.askdirectory`).
  - Zeile „Auswahl gesamt: X GB · Frei am Ziel: Y GB".
  - Button „Sichern".
- **Wiederherstellen-Ansicht:**
  - „Backup auswählen …" (ZIPs oder Kopie-Ordner), Liste der erkannten Ordner
    mit Ziel (per Dropdown/Button änderbar).
  - Button „Wiederherstellen" → Konflikt-/Bestätigungsdialog.
- **Gemeinsam unten:** `CTkProgressBar` (determiniert) + Statuszeile (aktuelle
  Datei) + Log-Textbox. Lange Läufe im `Worker`-Thread, Poll per `after()`.

---

## 8. Fortschrittsbalken (auch in bestehenden Tabs)

Da `Worker` bereits `(current, total, message)` liefert:

- Neuer `CTkProgressBar` in `personal_tab.py`, `backup_tab.py`, `restore_tab.py`.
- `bar.set(current / total)` im jeweiligen `_poll_worker()`; `total == 0`
  → unbestimmter Balken (`configure(mode="indeterminate")` + `start()`), sonst
  determiniert. Nach „done/error" auf 1.0 bzw. Reset.
- **Neuinstallation-Tab:** kein Balken für die eigentliche Installation (läuft
  im separaten PowerShell-Fenster, kein Callback) — bleibt beim Log.

---

## 9. Tests (`tests/test_personal_data.py`)

Alles gegen **Temp-Ordner**, keine echten Nutzerdaten:

- `folder_size` zählt Bytes/Dateien korrekt, sammelt Walk-Fehler.
- ZIP-Backup → Restore-Roundtrip: Inhalt identisch.
- Kopie-Backup → Restore-Roundtrip: Inhalt + mtime erhalten.
- Konfliktpolitik: `skip` / `overwrite` / `newer` verhalten sich korrekt
  (inkl. mtime-Vergleich).
- Manifest enthält `folder_key` + `source_path`; Restore ordnet korrekt zu.
- Known-Folder-Auflösung: Logik gegen gemockte GUIDs/Pfade.
- `_format_bytes` Grenzfälle (0, KB/MB/GB).

---

## 10. Versionierung & Doku

- `TOOL_VERSION` → **1.2.0**.
- `docs/FORTSCHRITT.md`: Abschnitt v1.2 (erledigt/offen/Annahmen).
- `README.md`: Feature + Bedienung „Persönliche Daten", Struktur-Baum
  (`personal_data.py`, `personal_tab.py`, Test).

---

## 11. Offene Annahmen / Risiken

- **Große Datenmengen:** Ordner können zig GB groß sein. Der Kopiermodus ist
  bei bereits komprimierten Medien deutlich schneller als ZIP; die GUI weist
  darauf hin.
- **Speicherbedarf-Schätzung** ist konservativ die Rohgröße; ZIP kann kleiner
  ausfallen — dadurch nie zu optimistisch (kein Abbruch mitten im Lauf wegen
  „voll", außer das Ziel füllt sich anderweitig).
- **Lange Pfade (>260 Zeichen):** unter Windows möglich problematisch; bei
  Bedarf `\\?\`-Präfix ergänzen (zunächst offen gelassen, in FORTSCHRITT.md
  vermerken).
- **Wie bei Browser-Profilen** wird der echte Restore erst auf dem neuen Gerät
  end-to-end getestet; Unit-Tests decken die Logik gegen Temp-Ordner ab.
