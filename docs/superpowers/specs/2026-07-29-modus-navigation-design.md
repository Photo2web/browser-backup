# Design-Spec: Umzugstool — Modus-Navigation, Lauf-Ordner & farbiger Fortschrittsbalken

**Datum:** 2026-07-29
**Ziel-Version:** v1.3.0
**Betrifft:** vor allem die GUI-Schicht (`gui/`); `core/` nur für die Umbenennung
der Datei-/Ordner-Präfixe (§9). Produkt wird zu **„Umzugstool — für Windows 10+"**.

---

## 1. Ziel & Motivation

Die App ist aktuell **nach Modul** organisiert: ein globaler `CTkSegmentedButton`
mit den gleichrangigen Tabs *Sichern* (nur Browser), *Wiederherstellen* (nur
Browser), *Neuinstallation* und *Persönliche Daten* (mit eigenem internen
Sichern/Wiederherstellen-Umschalter). Das vermischt die beiden Grundabsichten.

Der Umbau stellt auf **Modus-zuerst** um:

1. **Startbildschirm** mit drei großen Karten-Buttons: **Sichern**,
   **Wiederherstellen**, **Neuinstallation**.
2. Nach der Wahl sieht der Nutzer **nur** die Funktionen des gewählten Modus.
3. Beim **Sichern** wird automatisch eine aufgeräumte Ordnerstruktur
   (ein Lauf-Ordner mit Zeitstempel, darin je Modul ein Unterordner) angelegt.
4. Der **Fortschrittsbalken** bekommt eine Prozentzahl und wechselt seine Farbe
   fließend von Rot (0 %) nach Grün (100 %).
5. Das Produkt wird von „BrowserBackup" zu **„Umzugstool"** umbenannt, da es
   längst mehr als Browser-Backups macht (§9).

---

## 2. Navigation & Screens

### 2.1 Screen-Router (`gui/app.py`)

`App` wird zum schlanken **Router** zwischen genau vier Screens:

- **Home** (`HomeScreen`) — der Startbildschirm.
- **Sichern** (`BackupMode`)
- **Wiederherstellen** (`RestoreMode`)
- **Neuinstallation** (`ReinstallTab`, bestehend, unverändert)

Nur ein Screen ist sichtbar. Der Router bietet `show_home()` und
`show_mode(name)`. Beim Verlassen des Sichern-Modus wird dessen Lauf-Ordner-
Status zurückgesetzt (siehe §4).

Das ☰-Menü (Copyright/Über, Hilfe) bleibt auf **allen** Screens oben rechts
erreichbar. Der bisherige globale `CTkSegmentedButton` entfällt.

### 2.2 Startbildschirm (`gui/home_screen.py`)

Drei nebeneinanderliegende **Karten-Buttons** (Icon + Titel + kurze Unterzeile),
im vorhandenen Dark-Theme, mit dezentem Hover-Effekt:

| Titel | Unterzeile | Aktion |
|---|---|---|
| Sichern | Browser-Profile & persönliche Daten sichern | `show_mode("backup")` |
| Wiederherstellen | Gesicherte Daten zurückspielen | `show_mode("restore")` |
| Neuinstallation | Programme neu aufsetzen (winget) | `show_mode("reinstall")` |

**Icons:** zur Laufzeit mit **Pillow** gezeichnet (Pillow ist über
customtkinter bereits vorhanden) und als `CTkImage` eingebunden — kein externes
Bildmaterial, kein Build-Änderung. Gekapselt in `gui/home_icons.py`
(Funktionen liefern `PIL.Image`, hell/dunkel-tauglich). Motive: Diskette
(Sichern), Kreis-Pfeil (Wiederherstellen), Download-Box (Neuinstallation).

### 2.3 Zurück-Navigation

Jeder Modus-Screen hat oben links einen **‹ Zurück**-Button → `show_home()`.
Innerhalb eines Modus wechselt man die Module über **Sub-Tabs** (§3).

---

## 3. Aufteilung der bestehenden Bereiche

### 3.1 Zuordnung

| Bereich | bisher | neu |
|---|---|---|
| Browser sichern (`BackupTab`) | Tab „Sichern" | Sub-Tab „Browser" im **Sichern**-Modus |
| Browser wiederherstellen (`RestoreTab`) | Tab „Wiederherstellen" | Sub-Tab „Browser" im **Wiederherstellen**-Modus |
| Persönliche Daten (`PersonalDataTab`) | ein Tab mit internem Umschalter | **aufgeteilt** (siehe 3.2) |
| Neuinstallation (`ReinstallTab`) | Tab „Neuinstallation" | eigener Modus, unverändert |

### 3.2 Split von `PersonalDataTab`

Der aktuelle interne Sichern/Wiederherstellen-Umschalter entfällt. Der Tab wird
in **zwei eigenständige Frames** zerlegt, die die bestehende Logik übernehmen:

- `PersonalBackupFrame` — der Sicher-Teil (ZIP/Kopie-Wahl, Größen laden,
  Speicherplatz-Prüfung, Sichern). **Kein eigenes Ziel-Feld mehr** — bezieht
  das Zielverzeichnis vom Sichern-Modus (§4).
- `PersonalRestoreFrame` — der Restore-Teil (Quelle wählen, Auto-Mapping auf
  Known Folders, Konfliktverhalten, Restore-Speicherplatz-Prüfung). Unverändert
  in der Sache, nur als eigener Frame.

`PersonalBackupFrame` wird Sub-Tab im Sichern-Modus, `PersonalRestoreFrame`
Sub-Tab im Wiederherstellen-Modus.

### 3.3 Modus-Container

- **`gui/backup_mode.py` — `BackupMode(ctk.CTkFrame)`**
  - Oben: **gemeinsames Ziel-Feld** (Entry + „Durchsuchen …") + Zurück-Button.
  - Darunter: Sub-Tabs `[Browser | Persönliche Daten]` (`CTkSegmentedButton`),
    die `BackupTab` und `PersonalBackupFrame` einblenden.
  - Stellt den Sub-Modulen die Ziel-/Lauf-Ordner-Schnittstelle bereit (§4).
- **`gui/restore_mode.py` — `RestoreMode(ctk.CTkFrame)`**
  - Oben: Zurück-Button. Kein gemeinsames Ziel (Restore wählt Quell-Dateien
    je Modul selbst).
  - Sub-Tabs `[Browser | Persönliche Daten]` → `RestoreTab`,
    `PersonalRestoreFrame`.

---

## 4. Ordnerstruktur beim Sichern

### 4.1 Gemeinsames Ziel + Lauf-Ordner

Im Sichern-Modus wählt der Nutzer **einmal** ein Zielverzeichnis. Beim ersten
tatsächlichen Sichern der Sitzung wird darin ein **Lauf-Ordner** mit Zeitstempel
angelegt; jedes Modul legt darin seinen **Unterordner** an:

```
<gewähltes Ziel>/
└── Umzug_2026-07-29_1130/             ← ein Lauf pro Sichern-Sitzung
    ├── Browser/                        ← ZIPs der Browser-Profile
    └── PersoenlicheDaten/              ← ZIP/Kopie der persönlichen Ordner
```

- **Lauf-Ordner-Name:** `Umzug_<YYYY-MM-DD_HHMM>` (gleiches Zeitstempel-Schema
  wie die Dateinamen in `core/personal_data.py`).
- **Modul-Unterordner:** feste Namen `Browser` und `PersoenlicheDaten`.

### 4.2 Definition „eine Sichern-Sitzung"

`BackupMode` hält `_run_dir: Path | None` (Startwert `None`).

- `module_dir(name: str) -> Path`: legt bei Bedarf den Lauf-Ordner an (falls
  `_run_dir is None` → `<ziel>/Umzug_<timestamp>/`, merken), dann
  `_run_dir / name`, `mkdir(parents=True, exist_ok=True)`, und gibt ihn zurück.
- **Erster** Sicher-Klick der Sitzung erzeugt den Lauf-Ordner; **weitere**
  Klicks (egal welches Modul) verwenden denselben (gleicher Zeitstempel).
- **Zurück zum Start** setzt `_run_dir = None` → nächster Eintritt = neuer Lauf.
- Wird nichts gesichert, entsteht **kein** leerer Ordner (lazy Anlage).

### 4.3 Schnittstelle zu den Sub-Modulen

`BackupMode` stellt bereit:

- `resolve_target() -> Path | None` — validiert das gemeinsame Ziel-Feld
  (nicht leer, Ordner existiert/erstellbar); zeigt sonst einen Fehler und gibt
  `None` zurück.
- `module_dir(name) -> Path` — wie 4.2.

`BackupTab` und `PersonalBackupFrame` erhalten eine Referenz auf ihren
`BackupMode` (Dependency Injection über den Konstruktor) und rufen beim Sichern
`mode.resolve_target()` → bei Erfolg `mode.module_dir("Browser" | "PersoenlicheDaten")`
als Zielordner, statt ein eigenes Ziel-Entry auszulesen. Die
Speicherplatz-Prüfung bezieht sich weiterhin auf das gemeinsame Ziel-Laufwerk.

---

## 5. Farbiger Fortschrittsbalken (`gui/progress.py`)

Neues wiederverwendbares Widget **`ColorProgressBar(ctk.CTkFrame)`**, das die
drei bisherigen nackten `CTkProgressBar` in Browser-Sichern, Browser-
Wiederherstellen und Persönliche Daten ersetzt:

- Aufbau: ein `CTkProgressBar` mit einem **mittig darüberliegenden** `CTkLabel`
  (Prozenttext).
- `set_fraction(frac: float)` (0.0–1.0):
  - Balken: `progress_bar.set(frac)`.
  - Label: `f"{round(frac * 100)} %"`.
  - Farbe: `configure(progress_color=_color_for(frac))`.
- `reset()`: setzt auf 0 %, Farbe Rot.
- **Farbberechnung** `_color_for(frac)` via `colorsys.hsv_to_rgb`:
  Farbton (Hue) linear von 0° (Rot) bei 0 % nach 120° (Grün) bei 100 %,
  Sättigung/Helligkeit fix (z. B. S≈0.9, V≈0.85), Ergebnis als `#rrggbb`.
  Bei ~50 % ergibt das automatisch Gelb/Orange.

Der Prozenttext bleibt in beiden Balken-Zuständen lesbar (heller Text mit
dünnem Kontrast-Hintergrund oder feste Textfarbe, die auf Rot **und** Grün
funktioniert — wird beim Bau visuell geprüft).

Die vorhandenen `progress_callback`-Aufrufe (current/total/message) werden auf
`set_fraction(current / total)` gemappt; keine Änderung an `core/`.

---

## 6. Betroffene Dateien

**Neu**
- `gui/home_screen.py` — Startbildschirm mit 3 Karten-Buttons.
- `gui/home_icons.py` — Pillow-gezeichnete Icons als `CTkImage`.
- `gui/backup_mode.py` — Sichern-Container (gemeinsames Ziel, Lauf-Ordner, Sub-Tabs).
- `gui/restore_mode.py` — Wiederherstellen-Container (Sub-Tabs).
- `gui/progress.py` — `ColorProgressBar`.

**Umbau**
- `gui/app.py` — Screen-Router + Menü auf allen Screens.
- `gui/backup_tab.py` — Ziel-Feld raus, Ziel/Lauf-Ordner per Injektion; Balken-Widget.
- `gui/personal_tab.py` — Split in `PersonalBackupFrame` / `PersonalRestoreFrame`;
  Sicher-Teil callback-basiert; Balken-Widget.
- `gui/restore_tab.py` — Balken-Widget (Quell-/Zielwahl bleibt).
- `core/__init__.py` — `TOOL_VERSION = "1.3.0"`, ggf. Produktname-Konstante.
- **Rebranding** (§9): `core/personal_data.py` (Datei-Präfix), `core/backup.py`
  (ZIP-Namen, falls Präfix), `gui/app.py` (Titel/About), `packaging/build.ps1`
  (`--name Umzugstool`), `README.md`, `assets/make_icon.py`, Tests mit
  Namens-Assertions.

`core/`-Backup-/Restore-**Logik** bleibt inhaltlich unverändert (nur
Namens-Präfixe). Laufzeit-Icons erfordern keine neuen Asset-Dateien; `build.ps1`
ändert sich nur beim `--name`.

---

## 7. Tests

- **Lauf-Ordner-Logik:** neue Unit-Tests für `module_dir` — erzeugt den
  Lauf-Ordner beim ersten Aufruf, gibt Modul-Unterordner zurück, verwendet
  denselben Lauf für weitere Module, legt nach Reset einen neuen an, erzeugt
  ohne Sicherung keinen Ordner. Wo GUI-Zustand nötig ist, gegen Temp-Ordner mit
  ausgelagerter/leicht testbarer Logik.
- **`ColorProgressBar`:** `_color_for(0.0)` ≈ Rot, `_color_for(1.0)` ≈ Grün,
  `_color_for(0.5)` im Gelb/Orange-Bereich; `set_fraction` setzt Label-Text
  korrekt (Logik ohne echten Render prüfbar).
- **Screen-Router / Split:** headless Smoke-Test (App instanziierbar, Wechsel
  Home ↔ Modi ohne Fehler, Sub-Frames existieren) — analog zum bestehenden
  `tests/test_personal_tab.py`.
- Die **bestehenden 41 Tests** bleiben grün.

Echter GUI-Klick-Durchlauf und echtes Sichern/Wiederherstellen sind headless
nicht verifizierbar → manueller Test auf dem Zielrechner (wie gehabt).

---

## 8. Versionierung

`TOOL_VERSION` → **1.3.0** (neue Navigation + Ordnerstruktur + Balken-Optik +
Rebranding, abwärtskompatibel; bestehende Backups bleiben lesbar).

---

## 9. Rebranding: „Umzugstool — für Windows 10+"

Der Produktname wechselt von „BrowserBackup" zu **„Umzugstool"** (Claim
„für Windows 10+"). Umfang:

- **Fenstertitel** (`gui/app.py`): `Umzugstool v{TOOL_VERSION} — für Windows 10+`.
- **About-Dialog**: „Umzugstool" statt „BrowserBackup"; Text auf den erweiterten
  Funktionsumfang (Browser, persönliche Daten, Neuinstallation) angepasst.
- **EXE-Name** (`packaging/build.ps1`): `--name Umzugstool` → `Umzugstool.exe`
  (reines ASCII, keine Umlaut-Probleme in Pfaden/Kommandozeile).
- **Lauf-Ordner-Präfix**: `Umzug_<YYYY-MM-DD_HHMM>` (§4).
- **Datei-Präfix** persönliche Daten (`core/personal_data.py`):
  `browserbackup_data_<key>_…` → `umzug_data_<key>_…`. Analog etwaige
  Präfixe der Browser-ZIPs (`core/backup.py`), sofern vorhanden.
- **README.md**: Titel/Beschreibung aktualisiert.
- Betroffene **Tests** (Namens-Assertions, z. B. `tests/test_personal_data.py`)
  werden auf die neuen Präfixe angepasst.

**Abwärtskompatibilität:** Der Restore ist manifest-basiert
(`core/restore.py:read_manifest`, interne Kennung z. B. `kind: "personal_data"`)
— **nicht** dateinamen-basiert. Bereits erstellte Backups (inkl. der aktuell
laufenden Sicherung mit der alten EXE) bleiben daher voll wiederherstellbar,
auch nach der Präfix-Umstellung.

**Nicht Teil des Renames:** der Git-Repository-Name (`browser-backup`) und der
Projekt-Ordner bleiben unverändert (rein extern, kein Funktionsbezug); historische
Doku-Dateien (`docs/FORTSCHRITT.md`, ältere Specs) werden nicht rückwirkend
umgeschrieben.

---

## 10. Annahmen & bewusste Grenzen

- **Pillow verfügbar:** wird über customtkinter (CTkImage) mitgeliefert; keine
  neue Abhängigkeit.
- **Ein Lauf pro Sitzung** ist bewusst an „Zurück zum Start" gekoppelt, nicht an
  Uhrzeit-Fenster — vorhersehbar und einfach erklärbar.
- **Kein echter Links-Rechts-Gradient** im Balken (bewusst gegen ein
  Custom-Canvas-Widget entschieden): die Füllfarbe wandert fortschrittsabhängig.
- **Restore-Ziel** bleibt pro Modul (Browser: passendes Profil; Persönliche
  Daten: Known Folder) — kein gemeinsames Ziel im Wiederherstellen-Modus nötig.
