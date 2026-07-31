# Design: Restore vom Überordner (persönliche Daten)

> Erstellt: 2026-07-31 · Umzugstool · Feature F2
> Status: freigegeben (Brainstorming) → Umsetzungsplan folgt

## Ziel

Beim Wiederherstellen persönlicher Daten soll man **nur den Umzugs-Überordner**
wählen können. Das Tool findet die enthaltenen Datensicherungen selbst und lässt
sie – wie beim Sichern – per Häkchen auswählen. Die vorhandenen Einzel-Buttons
bleiben erhalten; der Ordner-Scan kommt **zusätzlich** dazu.

Kontext: Das Sichern legt seit v1.3 einen Lauf-Ordner an
(`<Ziel>/Umzug_<Datum>/` mit `Browser/` und `PersoenlicheDaten/`). Die
persönlichen Backups liegen als ZIP (`umzug_data_<key>_<zeit>.zip`) oder als
Kopie-Ordner (mit `backup_manifest.json` + `data/`) unter `PersoenlicheDaten/`.
Heute muss man diese ZIPs/Ordner einzeln von Hand wählen – das ändert dieses
Feature.

## Nicht-Ziele (YAGNI)

- **Kein** Browser-Restore über den Ordner-Scan – hier geht es ausschließlich um
  persönliche Daten; Browser hat seinen eigenen Reiter.
- **Keine** Änderung an `restore_personal_folder`, an der Konflikt-Abfrage oder
  am Cluster-genauen Speicherplatz-Check. Der Scan liefert nur dieselben
  `(source, manifest)`-Paare, die die GUI heute schon aus den manuellen Buttons
  erzeugt.
- Keine Deduplizierung gleicher `folder_key` – findet der Scan zwei Dokumente-
  Backups, werden beide angezeigt; der Nutzer entscheidet.

## Architektur

### Neu: Scan-Funktion in `core/personal_data.py`

GUI-unabhängig, einzeln testbar, im Stil der vorhandenen `read_backup_manifest`:

```
find_personal_backups(root: Path) -> list[tuple[Path, dict]]
```

Liefert `(source_path, manifest)`-Paare für alle gültigen persönlichen
Datensicherungen unterhalb von `root` (rekursiv). Erkennungsregeln:

1. **ZIP-Datei** mit Namenspräfix `umzug_data_` (abwärtskompatibel auch
   `browserbackup_data_`), deren `backup_manifest.json` `kind == "personal_data"`
   trägt → ein Fund. (Namenspräfix zuerst prüfen, damit nicht jedes fremde/große
   ZIP geöffnet werden muss; Manifest bestätigt die Gültigkeit.)
2. **Verzeichnis**, das direkt eine `backup_manifest.json` mit
   `kind == "personal_data"` enthält (Kopie-Backup) → ein Fund. Nicht weiter in
   dieses Verzeichnis absteigen (kein Abstieg in dessen `data/`).
3. Alles andere überspringen; in normale Unterordner weiter absteigen.
4. Defekte/fremde Dateien werden **still ignoriert** (kein Abbruch).
5. Ergebnis alphabetisch nach Anzeigename
   (`folder_display_name`, ersatzweise `folder_key`).

Dadurch funktioniert sowohl die Wahl des kompletten `Umzug_<Datum>/` als auch die
direkte Wahl von `PersoenlicheDaten/` (oder jedes anderen Ordners, der solche
Backups enthält).

### GUI: `PersonalRestoreFrame` (`gui/personal_tab.py`)

- Neuer Button **„Umzugsordner wählen …"** neben den zwei vorhandenen Buttons.
  Öffnet `filedialog.askdirectory`, ruft `find_personal_backups` im
  Worker-Thread (das Scannen kann bei vielen ZIPs kurz dauern → GUI nicht
  einfrieren), füllt danach dieselbe Zeilen-Liste wie die manuellen Buttons.
- **Gefundene Backups sind per Default angehakt.** Dafür bekommt jede Restore-
  Zeile eine Checkbox (`BooleanVar`, Default `True`); der bestehende Aufbau
  (Anzeigename, vorbelegtes Ziel-Feld, „Anderer Ordner …") bleibt.
- **„Alle auswählen / abwählen"**-Button (wie im Sichern-Frame).
- `_on_restore_clicked` berücksichtigt nur **angehakte** Zeilen. Sonst
  unverändert (Ziel-Prüfung, Speicherplatz, Konfliktmodus, Worker-Lauf).
- Kein Fund → Hinweis „Keine persönlichen Datensicherungen in diesem Ordner
  gefunden." (kein Absturz).

Hinweis: Die beiden vorhandenen manuellen Buttons erzeugen künftig ebenfalls
Zeilen **mit** Checkbox (default angehakt) – die Auswahl-Logik ist für alle
Quellen einheitlich.

## Datenfluss

```
[Umzugsordner wählen] → askdirectory → Worker: find_personal_backups(root)
   → Liste (source, manifest) → je Fund eine Zeile (Checkbox=an, Ziel vorbelegt)
[Wiederherstellen] → nur angehakte Zeilen → (unveränderte) Restore-Pipeline
```

## Fehlerbehandlung

- Leerer/backup-freier Ordner → Info-Hinweis, keine Zeilen.
- Einzelnes defektes ZIP / unlesbares Manifest → Fund übersprungen, Zeile ins
  Log (`_log`), Scan läuft weiter.
- Scan-Fehler (z. B. Ordner verschwindet) → `_on_run_error` wie bei anderen
  Läufen.

## Tests (unittest, `tests/test_personal_data.py`)

Neue Tests für `find_personal_backups`:
- findet ZIP **und** Kopie-Backup in einem verschachtelten Umzugsordner
  (`Umzug_x/PersoenlicheDaten/...`),
- Wahl des Unterordners `PersoenlicheDaten/` findet dieselben Backups,
- ignoriert Fremd-ZIP ohne gültiges Manifest,
- steigt **nicht** in das `data/` eines Kopie-Backups ab (kein Doppelfund),
- leerer Ordner → leere Liste,
- Sortierung nach Anzeigename.

## Betroffene Dateien

- `core/personal_data.py` – neue Funktion `find_personal_backups`.
- `gui/personal_tab.py` – `PersonalRestoreFrame`: Button, Scan im Worker,
  Checkbox je Zeile, „Alle auswählen/abwählen", nur angehakte restaurieren.
- `tests/test_personal_data.py` – neue Tests.
- Version → `1.3.2` (`core/__init__.py`), README/FORTSCHRITT-Notiz.

## Risiken / offene Punkte

- ZIPs werden zum Manifest-Lesen geöffnet; durch Namenspräfix-Filter bleibt das
  auf tatsächliche Datensicherungen beschränkt → unkritisch.
- Sicherheitsregel bleibt: echtes Wiederherstellen wird nicht gegen Mikes echte
  Ordner getestet, nur Logik gegen Temp-Ordner.
