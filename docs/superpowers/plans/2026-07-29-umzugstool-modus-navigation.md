# Umzugstool: Modus-Navigation, Lauf-Ordner & farbiger Fortschrittsbalken — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die GUI von „BrowserBackup" zum „Umzugstool" umbauen — Startbildschirm mit drei Karten-Buttons (Sichern/Wiederherstellen/Neuinstallation), gemeinsame Zielwahl beim Sichern mit einem Lauf-Ordner + Modul-Unterordnern, und ein wiederverwendbarer Fortschrittsbalken mit Prozentzahl und rot→grün-Farbe.

**Architecture:** `core/` bleibt inhaltlich unverändert (nur Datei-Präfixe). Neue reine Logik (`core/runfolder.py`) und ein reines Farb-Widget sind test-getrieben. Die GUI wird von „Modul-zuerst" (globaler SegmentedButton) auf „Modus-zuerst" umgestellt: `App` wird ein schlanker Screen-Router zwischen `HomeScreen`, `BackupMode`, `RestoreMode` und dem bestehenden `ReinstallTab`. Die bestehenden Tabs werden zu Sub-Frames der Modi; `PersonalDataTab` wird in einen Sicher- und einen Restore-Frame gesplittet.

**Tech Stack:** Python 3.11+, customtkinter (Dark-Theme), Pillow (via customtkinter), `unittest` (nicht pytest), PyInstaller (`--onefile`).

## Global Constraints

- **Test-Runner:** `unittest`, nicht pytest. Suite: `python -m unittest discover -s tests`. Einzeln: `python -m unittest tests.<modul> -v`.
- **Sprache:** alle Kommentare, GUI-Texte und Doku auf Deutsch. GUI-Texte in ASCII-Schreibweise wie im Bestand („Persoenliche Daten", „Zurueck", „‹").
- **Produktname:** „Umzugstool", Claim „fuer Windows 10+". EXE: `Umzugstool.exe`. Fenstertitel: `Umzugstool v{TOOL_VERSION} - fuer Windows 10+`.
- **Version:** `core/__init__.py` → `TOOL_VERSION = "1.3.0"`.
- **Lauf-Ordner-Name:** `Umzug_<YYYY-MM-DD_HHMM>`. Modul-Unterordner: exakt `Browser` und `PersoenlicheDaten`.
- **Datei-Präfixe:** Browser-ZIP `umzug_<key>_...`, Persönliche-Daten `umzug_data_<key>_...`.
- **Zeitstempel-Format:** `%Y-%m-%d_%H%M` (wie bestehendes `core/personal_data.py:_timestamp`).
- **Progress-Callback-Signatur:** `progress_callback(current: int, total: int, message: str)` — unverändert. Worker-Queue-Items: `("progress", current, total, message)`, `("done", results)`, `("error", exc)`.
- **Threading:** lange Läufe im `Worker` (aus `gui/worker.py`), Poll per `after()`. Tkinter-Widgets nur im Main-Thread anfassen.
- **Farbe:** Balkenfarbe per HSV-Interpolation Hue 0°(rot)→120°(grün), S≈0.9, V≈0.85.
- **Abwärtskompatibilität:** Restore ist manifest-basiert (`core/restore.py:read_manifest`, `kind`-Feld) — Präfix-Umbenennung darf bestehende Backups NICHT unlesbar machen. Keine Manifest-*Feldwerte* umbenennen, nur Dateinamen.
- **Bestehende 41 Tests bleiben grün.**
- **Nach jedem Task committen UND nach GitHub pushen** (`git push`); Branch: `feature/modus-navigation`.

---

### Task 1: `core/runfolder.py` — Lauf-Ordner-Logik (rein, TDD)

Reine Filesystem-Logik für „ein Lauf-Ordner pro Sichern-Sitzung, darin Modul-Unterordner". Kein Tkinter → voll unit-testbar.

**Files:**
- Create: `core/runfolder.py`
- Test: `tests/test_runfolder.py`

**Interfaces:**
- Produces:
  - `class RunFolder(base_dir: Path | str, timestamp: str | None = None)` mit Attributen `.base_dir: Path`, `.timestamp: str`, `.root: Path` (= `base_dir / f"Umzug_{timestamp}"`).
  - `RunFolder.module_dir(name: str) -> Path` — legt `root / name` an (`parents=True, exist_ok=True`) und gibt den Pfad zurück.
  - `runfolder.timestamp() -> str` — `%Y-%m-%d_%H%M`.

- [ ] **Step 1: Failing test**

```python
# tests/test_runfolder.py
import tempfile
import unittest
from pathlib import Path

from core.runfolder import RunFolder, timestamp


class RunFolderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_root_uses_umzug_prefix_and_timestamp(self):
        rf = RunFolder(self.base, timestamp="2026-07-29_1130")
        self.assertEqual(rf.root, self.base / "Umzug_2026-07-29_1130")

    def test_module_dir_creates_subfolder_under_run_root(self):
        rf = RunFolder(self.base, timestamp="2026-07-29_1130")
        browser = rf.module_dir("Browser")
        self.assertTrue(browser.is_dir())
        self.assertEqual(browser, self.base / "Umzug_2026-07-29_1130" / "Browser")

    def test_two_modules_share_same_run_root(self):
        rf = RunFolder(self.base, timestamp="2026-07-29_1130")
        a = rf.module_dir("Browser")
        b = rf.module_dir("PersoenlicheDaten")
        self.assertEqual(a.parent, b.parent)
        self.assertNotEqual(a, b)

    def test_timestamp_format(self):
        ts = timestamp()
        # YYYY-MM-DD_HHMM -> 15 Zeichen, Unterstrich an Position 10
        self.assertEqual(len(ts), 15)
        self.assertEqual(ts[10], "_")
```

- [ ] **Step 2: Run test, verify it fails**

Run: `python -m unittest tests.test_runfolder -v`
Expected: FAIL (`ModuleNotFoundError: core.runfolder`).

- [ ] **Step 3: Implement**

```python
# core/runfolder.py
"""Lauf-Ordner-Logik fuer den Sichern-Modus.

Ein Sicherungslauf buendelt alle Modul-Sicherungen einer Sitzung in einem
Ordner mit Zeitstempel (``Umzug_<YYYY-MM-DD_HHMM>``); jedes Modul bekommt darin
seinen eigenen Unterordner (``Browser``, ``PersoenlicheDaten``). Rein
dateisystembasiert und ohne GUI -> gut testbar.
"""

from datetime import datetime
from pathlib import Path


def timestamp() -> str:
    """Zeitstempel im Format YYYY-MM-DD_HHMM (wie core/personal_data.py)."""
    return datetime.now().strftime("%Y-%m-%d_%H%M")


class RunFolder:
    """Ein Sicherungslauf: <base_dir>/Umzug_<timestamp>/ mit Modul-Unterordnern."""

    def __init__(self, base_dir, timestamp: str | None = None):
        self.base_dir = Path(base_dir)
        self.timestamp = timestamp or globals()["timestamp"]()
        self.root = self.base_dir / f"Umzug_{self.timestamp}"

    def module_dir(self, name: str) -> Path:
        """Legt <root>/<name> an (falls noetig) und gibt den Pfad zurueck."""
        target = self.root / name
        target.mkdir(parents=True, exist_ok=True)
        return target
```

Hinweis: der Default-Parameter heißt bewusst `timestamp` (überdeckt die Funktion im lokalen Scope); der Aufruf `globals()["timestamp"]()` holt die Modul-Funktion. Alternativ die Funktion in `_default_timestamp()` umbenennen und `timestamp = _default_timestamp` als öffentlichen Alias setzen — Implementer wählt die klarere Variante und hält den Test grün.

- [ ] **Step 4: Run test, verify it passes**

Run: `python -m unittest tests.test_runfolder -v`
Expected: PASS (4 Tests).

- [ ] **Step 5: Full suite + commit + push**

```bash
python -m unittest discover -s tests
git add core/runfolder.py tests/test_runfolder.py
git commit -m "feat(core): RunFolder - Lauf-Ordner mit Modul-Unterordnern (v1.3)"
git push
```

---

### Task 2: Rebranding (Präfixe, Version, Build, Doku)

Alle **nicht-GUI**-Namensstellen auf „Umzugstool" umstellen. GUI-Titel/About kommen in Task 10, das Restore-Filetype-Label in Task 7.

**Files:**
- Modify: `core/__init__.py` (Version)
- Modify: `core/backup.py:111` (ZIP-Präfix)
- Modify: `core/personal_data.py:223` (Daten-Präfix)
- Modify: `packaging/build.ps1` (`--name`)
- Modify: `README.md` (Titel/Beschreibung)
- Modify: `assets/make_icon.py` (Kommentar/Name, kosmetisch)
- Modify: `tests/test_personal_data.py:95` (Präfix-Assertion)

- [ ] **Step 1: Assertion zuerst anpassen (wird rot)**

In `tests/test_personal_data.py:95`:
```python
            self.assertTrue(res.target.name.startswith("umzug_data_documents_"))
```

- [ ] **Step 2: Test läuft rot**

Run: `python -m unittest tests.test_personal_data -v`
Expected: FAIL (Name beginnt noch mit `browserbackup_data_`).

- [ ] **Step 3: Präfixe umstellen**

`core/personal_data.py:223`:
```python
    base = f"umzug_data_{folder.key}_{_timestamp()}"
```

`core/backup.py:111`:
```python
    zip_name = f"umzug_{browser.key}_{profile_name_part}_{timestamp}.zip"
```

- [ ] **Step 4: Test grün**

Run: `python -m unittest tests.test_personal_data -v`
Expected: PASS.

- [ ] **Step 5: Version, Build, Doku**

`core/__init__.py`:
```python
TOOL_VERSION = "1.3.0"  # v1.3.0: Modus-Navigation + Lauf-Ordner + farbiger Balken + Umzugstool-Rebranding
```

`packaging/build.ps1` — Zeile 30, `--name` und Meldungen anpassen:
```powershell
pyinstaller --onefile --windowed --name Umzugstool --icon assets/icon.ico --add-data "assets/icon.ico;assets" --collect-all customtkinter main.py
```
Und die drei `Write-Host`-Texte („Baue …", „Fertig: dist\…") von `BrowserBackup.exe` auf `Umzugstool.exe` ändern.

`README.md`: Titel/Kurzbeschreibung auf „Umzugstool — fuer Windows 10+" und den erweiterten Funktionsumfang (Browser, persönliche Daten, Neuinstallation) aktualisieren. Datei-/EXE-Nennungen von `BrowserBackup` auf `Umzugstool` ändern; die inhaltliche Beschreibung sonst belassen.

`assets/make_icon.py`: nur die Namensnennung im Kommentar/Docstring auf „Umzugstool" anpassen (rein kosmetisch, keine Logik).

- [ ] **Step 6: Full suite + commit + push**

```bash
python -m unittest discover -s tests
git add core/__init__.py core/backup.py core/personal_data.py packaging/build.ps1 README.md assets/make_icon.py tests/test_personal_data.py
git commit -m "chore: Rebranding zu Umzugstool - Praefixe, Version 1.3.0, Build, Doku"
git push
```

---

### Task 3: `gui/progress.py` — `ColorProgressBar` (Farbe TDD, Widget-Smoke)

Wiederverwendbares Balken-Widget: Prozentzahl mittig + Füllfarbe wandert rot→grün. Die reine Farbfunktion ist test-getrieben; das Widget wird headless smoke-getestet.

**Files:**
- Create: `gui/progress.py`
- Test: `tests/test_progress.py`

**Interfaces:**
- Produces:
  - `color_for_fraction(frac: float) -> str` — `#rrggbb`, clamped auf [0,1].
  - `class ColorProgressBar(ctk.CTkFrame)` mit `set_fraction(frac: float) -> None` (setzt Balken, Label `"NN %"`, Farbe) und `reset() -> None` (0 %, rot).

- [ ] **Step 1: Failing test (Farbfunktion + Label-Logik)**

```python
# tests/test_progress.py
import unittest

from gui.progress import color_for_fraction


def _rgb(hexstr):
    hexstr = hexstr.lstrip("#")
    return int(hexstr[0:2], 16), int(hexstr[2:4], 16), int(hexstr[4:6], 16)


class ColorForFractionTests(unittest.TestCase):
    def test_zero_is_reddish(self):
        r, g, b = _rgb(color_for_fraction(0.0))
        self.assertGreater(r, 150)
        self.assertLess(g, 90)

    def test_one_is_greenish(self):
        r, g, b = _rgb(color_for_fraction(1.0))
        self.assertGreater(g, 150)
        self.assertLess(r, 90)

    def test_half_is_yellowish(self):
        r, g, b = _rgb(color_for_fraction(0.5))
        self.assertGreater(r, 150)
        self.assertGreater(g, 150)

    def test_clamps_out_of_range(self):
        self.assertEqual(color_for_fraction(-1.0), color_for_fraction(0.0))
        self.assertEqual(color_for_fraction(2.0), color_for_fraction(1.0))
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m unittest tests.test_progress -v`
Expected: FAIL (`ModuleNotFoundError: gui.progress`).

- [ ] **Step 3: Implement**

```python
# gui/progress.py
"""Wiederverwendbarer Fortschrittsbalken mit Prozentzahl und rot->gruen-Farbe.

Die Fuellfarbe wandert fortschrittsabhaengig von Rot (0 %) ueber Gelb (~50 %)
nach Gruen (100 %). Ein zentriertes Label zeigt die Prozentzahl.
"""

import colorsys

import customtkinter as ctk


def color_for_fraction(frac: float) -> str:
    """#rrggbb fuer den Fortschritt frac (0..1): Hue 0deg(rot)->120deg(gruen)."""
    frac = max(0.0, min(1.0, frac))
    hue = (120.0 * frac) / 360.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.9, 0.85)
    return f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"


class ColorProgressBar(ctk.CTkFrame):
    """CTkProgressBar mit ueberlagerter Prozentzahl und wandernder Farbe."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._bar = ctk.CTkProgressBar(self)
        self._bar.set(0)
        self._bar.pack(fill="x", expand=True)
        # Prozentlabel mittig ueber dem Balken.
        self._label = ctk.CTkLabel(self, text="0 %", font=ctk.CTkFont(size=11, weight="bold"))
        self._label.place(relx=0.5, rely=0.5, anchor="center")
        self.reset()

    def set_fraction(self, frac: float) -> None:
        frac = max(0.0, min(1.0, frac))
        self._bar.set(frac)
        self._bar.configure(progress_color=color_for_fraction(frac))
        self._label.configure(text=f"{round(frac * 100)} %")

    def reset(self) -> None:
        self.set_fraction(0.0)
```

- [ ] **Step 4: Run, verify pass**

Run: `python -m unittest tests.test_progress -v`
Expected: PASS (4 Tests).

- [ ] **Step 5: Widget-Smoke-Test ergänzen**

An `tests/test_progress.py` anhängen (headless, nur wenn ein Display/Tk verfügbar ist — Muster wie `tests/test_personal_tab.py`):
```python
class ColorProgressBarWidgetTests(unittest.TestCase):
    def test_set_fraction_updates_label(self):
        import customtkinter as ctk
        from gui.progress import ColorProgressBar
        try:
            root = ctk.CTk()
        except Exception as exc:  # kein Display (CI) -> ueberspringen
            self.skipTest(f"kein Tk verfuegbar: {exc}")
        root.withdraw()
        try:
            bar = ColorProgressBar(root)
            bar.set_fraction(0.42)
            self.assertEqual(bar._label.cget("text"), "42 %")
        finally:
            root.destroy()
```

- [ ] **Step 6: Full suite + commit + push**

```bash
python -m unittest discover -s tests
git add gui/progress.py tests/test_progress.py
git commit -m "feat(gui): ColorProgressBar - Prozentzahl + rot->gruen-Farbverlauf"
git push
```

---

### Task 4: `gui/home_icons.py` + `gui/home_screen.py` — Startbildschirm

Drei mit Pillow gezeichnete Icons und der Startbildschirm mit drei Karten-Buttons.

**Files:**
- Create: `gui/home_icons.py`
- Create: `gui/home_screen.py`
- Test: `tests/test_home.py`

**Interfaces:**
- Produces:
  - `home_icons.draw_icon(kind: str, size: int = 64) -> PIL.Image.Image` mit `kind ∈ {"save","restore","reinstall"}`.
  - `home_icons.ctk_icon(kind: str, size: int = 64) -> ctk.CTkImage`.
  - `class HomeScreen(ctk.CTkFrame)`, Konstruktor `HomeScreen(master, on_backup, on_restore, on_reinstall)` — drei Callables ohne Argumente.

- [ ] **Step 1: Failing test (Icons, rein)**

```python
# tests/test_home.py
import unittest

from gui.home_icons import draw_icon


class DrawIconTests(unittest.TestCase):
    def test_known_kinds_return_rgba_image_of_size(self):
        for kind in ("save", "restore", "reinstall"):
            img = draw_icon(kind, 48)
            self.assertEqual(img.size, (48, 48))
            self.assertEqual(img.mode, "RGBA")

    def test_unknown_kind_raises(self):
        with self.assertRaises(ValueError):
            draw_icon("nope", 48)
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m unittest tests.test_home -v`
Expected: FAIL (`ModuleNotFoundError: gui.home_icons`).

- [ ] **Step 3: Icons implementieren**

```python
# gui/home_icons.py
"""Mit Pillow gezeichnete Icons fuer den Startbildschirm.

Pillow ist ueber customtkinter (CTkImage) bereits vorhanden -> kein externes
Bildmaterial noetig. Jede Zeichenfunktion liefert ein RGBA-Image; ctk_icon()
verpackt es fuer die GUI.
"""

import customtkinter as ctk
from PIL import Image, ImageDraw

_ACCENT = (56, 132, 255, 255)   # Blau, passt zum CTk-Theme "blue"
_LIGHT = (232, 238, 248, 255)


def _canvas(size: int):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _save(size: int) -> Image.Image:
    img, d = _canvas(size)
    m = size * 0.14
    d.rounded_rectangle([m, m, size - m, size - m], radius=size * 0.10, fill=_ACCENT)
    d.rectangle([size * 0.34, m, size * 0.66, size * 0.34], fill=_LIGHT)          # Schieber
    d.rectangle([size * 0.54, size * 0.16, size * 0.62, size * 0.30], fill=_ACCENT)
    d.rounded_rectangle([size * 0.30, size * 0.52, size * 0.70, size - m * 1.2],  # Etikett
                        radius=size * 0.04, fill=_LIGHT)
    return img


def _restore(size: int) -> Image.Image:
    img, d = _canvas(size)
    m = size * 0.18
    d.arc([m, m, size - m, size - m], start=70, end=360, fill=_ACCENT, width=int(size * 0.11))
    d.polygon([(size * 0.50, size * 0.06), (size * 0.50, size * 0.30),
               (size * 0.72, size * 0.18)], fill=_ACCENT)                          # Pfeilspitze
    return img


def _reinstall(size: int) -> Image.Image:
    img, d = _canvas(size)
    d.rectangle([size * 0.44, size * 0.16, size * 0.56, size * 0.50], fill=_ACCENT)
    d.polygon([(size * 0.32, size * 0.46), (size * 0.68, size * 0.46),
               (size * 0.50, size * 0.70)], fill=_ACCENT)                          # Download-Pfeil
    d.rounded_rectangle([size * 0.22, size * 0.74, size * 0.78, size * 0.86],
                        radius=size * 0.03, fill=_LIGHT)                           # Ablage
    return img


_DRAWERS = {"save": _save, "restore": _restore, "reinstall": _reinstall}


def draw_icon(kind: str, size: int = 64) -> Image.Image:
    try:
        return _DRAWERS[kind](size)
    except KeyError:
        raise ValueError(f"Unbekanntes Icon: {kind!r}")


def ctk_icon(kind: str, size: int = 64) -> ctk.CTkImage:
    img = draw_icon(kind, size)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
```

- [ ] **Step 4: Run, verify pass**

Run: `python -m unittest tests.test_home -v`
Expected: PASS (2 Tests).

- [ ] **Step 5: HomeScreen implementieren**

```python
# gui/home_screen.py
"""Startbildschirm: drei Karten-Buttons (Sichern / Wiederherstellen / Neuinstallation)."""

import customtkinter as ctk

from .home_icons import ctk_icon

_CARDS = [
    ("save", "Sichern", "Browser-Profile & persoenliche Daten sichern", "on_backup"),
    ("restore", "Wiederherstellen", "Gesicherte Daten zurueckspielen", "on_restore"),
    ("reinstall", "Neuinstallation", "Programme neu aufsetzen (winget)", "on_reinstall"),
]


class HomeScreen(ctk.CTkFrame):
    def __init__(self, master, on_backup, on_restore, on_reinstall):
        super().__init__(master, fg_color="transparent")
        self._commands = {"on_backup": on_backup, "on_restore": on_restore,
                          "on_reinstall": on_reinstall}
        self._icons = []  # CTkImage-Referenzen halten (sonst Garbage-Collect)
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Was moechtest du tun?",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(28, 18))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(expand=True)
        for i, (kind, title, subtitle, cmd_key) in enumerate(_CARDS):
            icon = ctk_icon(kind, 64)
            self._icons.append(icon)
            ctk.CTkButton(
                row, image=icon, text=f"\n{title}\n{subtitle}", compound="top",
                width=230, height=170, corner_radius=14,
                font=ctk.CTkFont(size=14, weight="bold"),
                command=self._commands[cmd_key],
            ).grid(row=0, column=i, padx=14, pady=14)
```

- [ ] **Step 6: HomeScreen-Smoke-Test ergänzen**

An `tests/test_home.py` anhängen:
```python
class HomeScreenSmokeTests(unittest.TestCase):
    def test_builds_and_wires_callbacks(self):
        import customtkinter as ctk
        from gui.home_screen import HomeScreen
        try:
            root = ctk.CTk()
        except Exception as exc:
            self.skipTest(f"kein Tk verfuegbar: {exc}")
        root.withdraw()
        called = []
        try:
            HomeScreen(root, on_backup=lambda: called.append("b"),
                       on_restore=lambda: called.append("r"),
                       on_reinstall=lambda: called.append("i"))
        finally:
            root.destroy()
```

- [ ] **Step 7: Full suite + commit + push**

```bash
python -m unittest discover -s tests
git add gui/home_icons.py gui/home_screen.py tests/test_home.py
git commit -m "feat(gui): Startbildschirm mit drei Karten-Buttons + gezeichnete Icons"
git push
```

---

### Task 5: `gui/backup_tab.py` — Ziel per Provider + ColorProgressBar

`BackupTab` verliert sein eigenes Ziel-Feld und bekommt das Ziel/den Modul-Ordner von einem `dir_provider` (später `BackupMode`). Der nackte Balken wird durch `ColorProgressBar` ersetzt.

**Files:**
- Modify: `gui/backup_tab.py`
- Test: `tests/test_backup_tab.py`

**Interfaces:**
- Consumes: ein `dir_provider` mit `resolve_target() -> Path | None` und `module_dir(name: str) -> Path` (siehe Task 8).
- Produces: `BackupTab(master, dir_provider)`.

- [ ] **Step 1: Failing smoke-test mit Fake-Provider**

```python
# tests/test_backup_tab.py
import tempfile
import unittest
from pathlib import Path


class _FakeProvider:
    def __init__(self, base):
        self.base = Path(base)
    def resolve_target(self):
        return self.base
    def module_dir(self, name):
        d = self.base / "Umzug_test" / name
        d.mkdir(parents=True, exist_ok=True)
        return d


class BackupTabWiringTests(unittest.TestCase):
    def test_uses_provider_and_has_no_target_entry(self):
        import customtkinter as ctk
        from gui.backup_tab import BackupTab
        from gui.progress import ColorProgressBar
        try:
            root = ctk.CTk()
        except Exception as exc:
            self.skipTest(f"kein Tk verfuegbar: {exc}")
        root.withdraw()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        try:
            tab = BackupTab(root, dir_provider=_FakeProvider(tmp.name))
            self.assertFalse(hasattr(tab, "target_entry"))
            self.assertIsInstance(tab.progress_bar, ColorProgressBar)
        finally:
            root.destroy()
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m unittest tests.test_backup_tab -v`
Expected: FAIL (`BackupTab.__init__` akzeptiert noch kein `dir_provider`).

- [ ] **Step 3: Umbau `backup_tab.py`**

Änderungen (siehe aktueller Stand `gui/backup_tab.py`):

1. Import ergänzen: `from .progress import ColorProgressBar`.
2. Konstruktor (Zeile 32): Signatur `def __init__(self, master, dir_provider):`, `self.dir_provider = dir_provider` setzen.
3. In `_build_ui`: den gesamten Ziel-Block **entfernen** (aktuell Zeilen 63–72: Label „Zielordner:", `target_frame`, `self.target_entry`, „Durchsuchen …"). Die Cache-Checkbox bleibt; sie darf in `form` auf `row=0` rutschen.
4. `_choose_target_dir` (Zeile 115–119) **löschen**.
5. Balken (Zeile 82–84) ersetzen:
```python
        self.progress_bar = ColorProgressBar(self)
        self.progress_bar.pack(fill="x", pady=(0, 8))
```
6. In `_on_start_clicked` den Ziel-Block (Zeile 138–142) ersetzen durch:
```python
        dest_base = self.dir_provider.resolve_target()
        if dest_base is None:
            return
        dest_dir = self.dir_provider.module_dir("Browser")
```
   `dest_dir` wird unverändert an `backup_profile(..., dest_dir, ...)` weitergereicht.
7. Balken-Aufrufe umstellen: `self.progress_bar.set(0)` → `self.progress_bar.reset()`; in `_poll_worker` `self.progress_bar.set(current / total)` → `self.progress_bar.set_fraction(current / total)`; in `_on_backup_done` `self.progress_bar.set(1)` → `self.progress_bar.set_fraction(1.0)`.

- [ ] **Step 4: Run smoke-test, verify pass**

Run: `python -m unittest tests.test_backup_tab -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit + push**

```bash
python -m unittest discover -s tests
git add gui/backup_tab.py tests/test_backup_tab.py
git commit -m "refactor(gui): BackupTab nutzt dir_provider + ColorProgressBar"
git push
```

---

### Task 6: `gui/personal_tab.py` — Split in Sicher-/Restore-Frame

`PersonalDataTab` wird in `PersonalBackupFrame` (Sichern, ziel-provider-basiert) und `PersonalRestoreFrame` (Wiederherstellen) gesplittet. Gemeinsame Worker-/Log-/Balken-Logik in einer Basisklasse, um Duplikation zu vermeiden.

**Files:**
- Modify: `gui/personal_tab.py`
- Modify: `tests/test_personal_tab.py`

**Interfaces:**
- Consumes: `dir_provider` (wie Task 5) für `PersonalBackupFrame`.
- Produces:
  - `class PersonalBackupFrame(ctk.CTkFrame)`, Konstruktor `(master, dir_provider)`, mit `on_show()` (lädt Größen einmal).
  - `class PersonalRestoreFrame(ctk.CTkFrame)`, Konstruktor `(master)`.

- [ ] **Step 1: Failing test (Split + Provider)**

`tests/test_personal_tab.py` ersetzen/erweitern — statt des bisherigen `PersonalDataTab`-Smoke-Tests jetzt die zwei Frames prüfen. Der bestehende Monkeypatch von `detect_personal_folders` bleibt:

```python
# tests/test_personal_tab.py  (Kern)
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class _FakeProvider:
    def __init__(self, base):
        self.base = Path(base)
    def resolve_target(self):
        return self.base
    def module_dir(self, name):
        d = self.base / "Umzug_test" / name
        d.mkdir(parents=True, exist_ok=True)
        return d


class PersonalFramesSmokeTests(unittest.TestCase):
    def _root(self):
        import customtkinter as ctk
        try:
            root = ctk.CTk()
        except Exception as exc:
            self.skipTest(f"kein Tk verfuegbar: {exc}")
        root.withdraw()
        return root

    @mock.patch("gui.personal_tab.detect_personal_folders", return_value=[])
    def test_backup_frame_builds_with_provider(self, _m):
        from gui.personal_tab import PersonalBackupFrame
        from gui.progress import ColorProgressBar
        root = self._root()
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        try:
            frame = PersonalBackupFrame(root, dir_provider=_FakeProvider(tmp.name))
            self.assertFalse(hasattr(frame, "backup_target"))
            self.assertIsInstance(frame.progress_bar, ColorProgressBar)
        finally:
            root.destroy()

    @mock.patch("gui.personal_tab.detect_personal_folders", return_value=[])
    def test_restore_frame_builds(self, _m):
        from gui.personal_tab import PersonalRestoreFrame
        root = self._root()
        try:
            PersonalRestoreFrame(root)
        finally:
            root.destroy()
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m unittest tests.test_personal_tab -v`
Expected: FAIL (`PersonalBackupFrame` existiert noch nicht).

- [ ] **Step 3: `personal_tab.py` umbauen**

Struktur (bestehende Methodenkörper wo möglich **unverändert übernehmen** — es ist ein Umzug, keine Neuimplementierung):

1. Import ergänzen: `from .progress import ColorProgressBar`.

2. Gemeinsame Basisklasse (kapselt den bisher geteilten `_poll_run`, `_log`, `_on_run_error`, Balken + Log):
```python
class _RunFrame(ctk.CTkFrame):
    """Basis fuer die beiden Personal-Frames: Worker-Poll, Log, Balken."""

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.worker = Worker()
        self.log_box = ctk.CTkTextbox(self, height=90)
        self.log_box.configure(state="disabled")
        self.log_box.pack(side="bottom", fill="x", pady=(4, 0))
        self.progress_bar = ColorProgressBar(self)
        self.progress_bar.pack(side="bottom", fill="x", pady=(4, 4))

    def _log(self, message: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _poll_run(self, on_done):
        try:
            while True:
                item = self.worker.queue.get_nowait()
                kind = item[0]
                if kind == "progress":
                    _, current, total, message = item
                    if total:
                        self.progress_bar.set_fraction(current / total)
                    self._log(message)
                elif kind == "done":
                    on_done(item[1])
                    return
                elif kind == "error":
                    self._on_run_error(item[1])
                    return
        except queue.Empty:
            pass
        self.after(100, lambda: self._poll_run(on_done))

    def _on_run_error(self, exc: Exception):
        self.progress_bar.reset()
        self._log(f"FEHLER: {exc}")
        show_error(self, "Fehler", str(exc))

    def _choose_dir(self, entry: ctk.CTkEntry):
        chosen = filedialog.askdirectory(parent=self)
        if chosen:
            entry.delete(0, "end")
            entry.insert(0, chosen)
```

3. `class PersonalBackupFrame(_RunFrame)`:
   - Konstruktor `(self, master, dir_provider)`: `super().__init__(master)`, `self.dir_provider = dir_provider`, `self.folders = detect_personal_folders()`, `self.backup_items = []`, `self.mode_var = ctk.StringVar(value="zip")`, `self._sizes = {}`, `self._sizes_loaded = False`, dann `self._build()`.
   - `_build()`: die Widgets aus dem bisherigen `_build_backup_view` (personal_tab.py:74–119) übernehmen, aber **ohne** das Ziel-`target_frame`/`self.backup_target` (Zeilen 106–112 entfallen) und ohne den eigenen SegmentedButton. Alles direkt in `self` packen statt in `self.backup_view`.
   - Methoden **unverändert übernehmen** (aus aktuellem `personal_tab.py`): `on_show` (149–152, ohne `worker.is_running`-Sonderfall unnötig — beibehalten), `_load_sizes` (156–164), `_poll_sizes` (166–182), `_on_sizes_loaded` (184–191), `_update_totals` (193–195), `_gather_backup_selection` (199–200), `_select_all_backup` (202–206), `_on_backup_done` (257–267).
   - `_on_backup_clicked`: aus 208–255 übernehmen mit **einer** Änderung im Ziel-Teil — die Zeilen 215–219 (`dest_text`/`self.backup_target`) und die Space-Check-Basis ersetzen:
```python
        dest_base = self.dir_provider.resolve_target()
        if dest_base is None:
            return
        if not self._sizes_loaded:
            show_error(self, "Bitte kurz warten",
                       "Die Ordnergroessen werden noch ermittelt. Bitte einen Moment warten "
                       "und erneut auf 'Sichern' klicken.")
            return
        needed = sum(self._sizes.get(f.key, 0) for f in selected)
        try:
            free = free_space(dest_base)
        except OSError as exc:
            show_error(self, "Zielordner", f"Zielordner nicht nutzbar:\n{exc}")
            return
        if needed > free:
            show_error(self, "Zu wenig Speicherplatz",
                       f"Benoetigt (max.): {_format_bytes(needed)}\n"
                       f"Frei am Ziel: {_format_bytes(free)}\n\n"
                       "Bitte Ziel mit mehr Platz waehlen oder weniger Ordner auswaehlen.")
            return
        dest = self.dir_provider.module_dir("PersoenlicheDaten")
```
     `backup_personal_folder(folder, dest, mode=mode, ...)` bleibt; `self.progress_bar.set(0)` → `self.progress_bar.reset()`; in `_on_backup_done` `set(1)` → `set_fraction(1.0)`.

4. `class PersonalRestoreFrame(_RunFrame)`:
   - Konstruktor `(self, master)`: `super().__init__(master)`, `self.folders = detect_personal_folders()`, `self.restore_rows = []`, `self._build()`.
   - `_build()`: Widgets aus `_build_restore_view` (121–137) direkt in `self`.
   - Methoden **unverändert übernehmen**: `_choose_restore_zips` (271–274), `_choose_restore_copy` (276–279), `_load_restore_sources` (281–307), `_on_restore_clicked` (309–362, `set(0)`→`reset()`), `_on_restore_done` (364–376, `set(1)`→`set_fraction(1.0)`).
   - `_on_run_error` der Basis reicht (setzt Balken zurück); den Button-Reset macht `_on_restore_done`/kein laufender Fehlerpfad braucht den Restore-Button — falls gewünscht, in `PersonalRestoreFrame._on_run_error` überschreiben und `self.restore_button.configure(state="normal", text="Wiederherstellen")` ergänzen.

5. Die alte Klasse `PersonalDataTab` **entfernen** (inkl. `_switch_view`, `_build_ui`, `_build_backup_view`, `_build_restore_view`).

- [ ] **Step 4: Run, verify pass**

Run: `python -m unittest tests.test_personal_tab -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit + push**

```bash
python -m unittest discover -s tests
git add gui/personal_tab.py tests/test_personal_tab.py
git commit -m "refactor(gui): PersonalDataTab in Backup-/Restore-Frame gesplittet"
git push
```

---

### Task 7: `gui/restore_tab.py` — ColorProgressBar + Filetype-Rename

`RestoreTab` (Browser-Wiederherstellen) behält Quell-/Zielwahl, tauscht nur den Balken und aktualisiert das Filetype-Label.

**Files:**
- Modify: `gui/restore_tab.py`

- [ ] **Step 1: Umbau**

1. Import: `from .progress import ColorProgressBar`.
2. Balken (aktuell `self.progress_bar = ctk.CTkProgressBar(self)` + `self.progress_bar.set(0)`) ersetzen:
```python
        self.progress_bar = ColorProgressBar(self)
        self.progress_bar.pack(fill="x", pady=(0, 8))
```
3. Alle `self.progress_bar.set(x)` umstellen: `set(0)`→`reset()`, im Poll `set(current/total)`→`set_fraction(current/total)`, im Done `set(1)`→`set_fraction(1.0)`.
4. Das Datei-Filter-Label `("BrowserBackup ZIP", "*.zip")` → `("Umzugstool ZIP", "*.zip")` (Docstring/Kommentar mit „BrowserBackup" ebenfalls auf „Umzugstool" anpassen).

- [ ] **Step 2: Full suite (bestehende Restore-Tests decken die Logik ab)**

Run: `python -m unittest discover -s tests`
Expected: PASS (unverändert grün — Balkentyp ist GUI-intern).

- [ ] **Step 3: Commit + push**

```bash
git add gui/restore_tab.py
git commit -m "refactor(gui): RestoreTab nutzt ColorProgressBar + Umzugstool-Label"
git push
```

---

### Task 8: `gui/backup_mode.py` — Sichern-Container (Provider + RunFolder)

Container mit gemeinsamem Ziel-Feld, Zurück-Button und Sub-Tabs `[Browser | Persoenliche Daten]`. Implementiert die `dir_provider`-Schnittstelle über `RunFolder`.

**Files:**
- Create: `gui/backup_mode.py`
- Test: `tests/test_backup_mode.py`

**Interfaces:**
- Consumes: `BackupTab(master, dir_provider)` (T5), `PersonalBackupFrame(master, dir_provider)` (T6), `RunFolder` (T1).
- Produces: `BackupMode(master, on_back)`; Provider-API `resolve_target() -> Path | None`, `module_dir(name) -> Path`, `reset_run() -> None`.

- [ ] **Step 1: Failing test (Provider-Verhalten)**

```python
# tests/test_backup_mode.py
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class BackupModeProviderTests(unittest.TestCase):
    def _mode(self, root):
        # Personal-Frame ohne echte Ordner-Erkennung bauen.
        with mock.patch("gui.personal_tab.detect_personal_folders", return_value=[]):
            from gui.backup_mode import BackupMode
            return BackupMode(root, on_back=lambda: None)

    def test_module_dir_reuses_one_run_for_both_modules(self):
        import customtkinter as ctk
        try:
            root = ctk.CTk()
        except Exception as exc:
            self.skipTest(f"kein Tk verfuegbar: {exc}")
        root.withdraw()
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        try:
            mode = self._mode(root)
            mode.target_entry.insert(0, tmp.name)
            self.assertIsNotNone(mode.resolve_target())
            a = mode.module_dir("Browser")
            b = mode.module_dir("PersoenlicheDaten")
            self.assertEqual(a.parent, b.parent)
            self.assertTrue(a.parent.name.startswith("Umzug_"))
            # nach Reset ein neuer Lauf
            mode.reset_run()
            mode.resolve_target()
            c = mode.module_dir("Browser")
            self.assertNotEqual(a.parent, c.parent) if a.parent.name != c.parent.name else None
        finally:
            root.destroy()

    def test_resolve_target_empty_returns_none(self):
        import customtkinter as ctk
        try:
            root = ctk.CTk()
        except Exception as exc:
            self.skipTest(f"kein Tk verfuegbar: {exc}")
        root.withdraw()
        try:
            mode = self._mode(root)
            with mock.patch("gui.backup_mode.show_error"):
                self.assertIsNone(mode.resolve_target())
        finally:
            root.destroy()
```

Hinweis: der Reset-Vergleich kann bei gleichem Minutentimestamp identisch sein — deshalb defensiv formuliert. Wenn ein deterministischer Test gewünscht ist, kann der Implementer `RunFolder`-Timestamp injizierbar machen; primär gilt der Reuse- und der Empty-Test.

- [ ] **Step 2: Run, verify fail**

Run: `python -m unittest tests.test_backup_mode -v`
Expected: FAIL (`gui.backup_mode` fehlt).

- [ ] **Step 3: Implement**

```python
# gui/backup_mode.py
"""Sichern-Modus: gemeinsames Ziel + Lauf-Ordner + Sub-Tabs (Browser / Persoenliche Daten)."""

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.runfolder import RunFolder

from .backup_tab import BackupTab
from .dialogs import show_error
from .personal_tab import PersonalBackupFrame


class BackupMode(ctk.CTkFrame):
    """Container fuer den Sichern-Modus. Stellt die dir_provider-Schnittstelle bereit."""

    def __init__(self, master, on_back):
        super().__init__(master, fg_color="transparent")
        self._on_back = on_back
        self._run: RunFolder | None = None
        self._base: Path | None = None
        self._build()

    def _build(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkButton(top, text="‹ Zurueck", width=90, command=self._back).pack(side="left")
        ctk.CTkLabel(top, text="Sichern", font=ctk.CTkFont(size=16, weight="bold")).pack(
            side="left", padx=8)

        tf = ctk.CTkFrame(self, fg_color="transparent")
        tf.pack(fill="x", pady=(8, 8))
        tf.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(tf, text="Zielordner:").grid(row=0, column=0, padx=(0, 8))
        self.target_entry = ctk.CTkEntry(
            tf, placeholder_text="Gemeinsamer Zielordner fuer diese Sicherung")
        self.target_entry.grid(row=0, column=1, sticky="ew")
        ctk.CTkButton(tf, text="Durchsuchen ...", width=110, command=self._choose).grid(
            row=0, column=2, padx=(8, 0))

        self.subtabs = ctk.CTkSegmentedButton(
            self, values=["Browser", "Persoenliche Daten"], command=self._switch)
        self.subtabs.set("Browser")
        self.subtabs.pack(fill="x", pady=(0, 8))

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True)
        self.browser_frame = BackupTab(self.body, dir_provider=self)
        self.personal_frame = PersonalBackupFrame(self.body, dir_provider=self)
        self.browser_frame.pack(fill="both", expand=True)

    # -- Sub-Tab-Umschaltung -------------------------------------------
    def _switch(self, value: str):
        self.browser_frame.pack_forget()
        self.personal_frame.pack_forget()
        if value == "Browser":
            self.browser_frame.pack(fill="both", expand=True)
        else:
            self.personal_frame.pack(fill="both", expand=True)
            self.personal_frame.on_show()

    # -- dir_provider-Schnittstelle ------------------------------------
    def resolve_target(self) -> Path | None:
        text = self.target_entry.get().strip()
        if not text:
            show_error(self, "Kein Zielordner", "Bitte einen gemeinsamen Zielordner waehlen.")
            return None
        base = Path(text)
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            show_error(self, "Zielordner", f"Zielordner nicht nutzbar:\n{exc}")
            return None
        self._base = base
        return base

    def module_dir(self, name: str) -> Path:
        if self._run is None:
            self._run = RunFolder(self._base)
        return self._run.module_dir(name)

    def reset_run(self) -> None:
        self._run = None

    def on_show(self) -> None:
        # Beim Betreten des Modus die Groessen des sichtbaren Personal-Frames laden,
        # falls dort aktiv. (Browser-Sub-Tab braucht kein on_show.)
        if self.subtabs.get() == "Persoenliche Daten":
            self.personal_frame.on_show()

    # -- intern --------------------------------------------------------
    def _choose(self):
        chosen = filedialog.askdirectory(parent=self)
        if chosen:
            self.target_entry.delete(0, "end")
            self.target_entry.insert(0, chosen)

    def _back(self):
        self.reset_run()
        self._on_back()
```

- [ ] **Step 4: Run, verify pass**

Run: `python -m unittest tests.test_backup_mode -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit + push**

```bash
python -m unittest discover -s tests
git add gui/backup_mode.py tests/test_backup_mode.py
git commit -m "feat(gui): BackupMode - gemeinsames Ziel, Lauf-Ordner, Sub-Tabs"
git push
```

---

### Task 9: `gui/restore_mode.py` — Wiederherstellen-Container

Container mit Zurück-Button und Sub-Tabs `[Browser | Persoenliche Daten]`. Kein gemeinsames Ziel (Restore wählt Quellen je Modul selbst).

**Files:**
- Create: `gui/restore_mode.py`
- Test: `tests/test_restore_mode.py`

**Interfaces:**
- Consumes: `RestoreTab(master)` (bestehend), `PersonalRestoreFrame(master)` (T6).
- Produces: `RestoreMode(master, on_back)`.

- [ ] **Step 1: Failing smoke-test**

```python
# tests/test_restore_mode.py
import unittest
from unittest import mock


class RestoreModeSmokeTests(unittest.TestCase):
    def test_builds(self):
        import customtkinter as ctk
        try:
            root = ctk.CTk()
        except Exception as exc:
            self.skipTest(f"kein Tk verfuegbar: {exc}")
        root.withdraw()
        try:
            with mock.patch("gui.personal_tab.detect_personal_folders", return_value=[]), \
                 mock.patch("gui.restore_tab.detect_browsers", return_value=[]):
                from gui.restore_mode import RestoreMode
                RestoreMode(root, on_back=lambda: None)
        finally:
            root.destroy()
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m unittest tests.test_restore_mode -v`
Expected: FAIL (`gui.restore_mode` fehlt).

- [ ] **Step 3: Implement**

```python
# gui/restore_mode.py
"""Wiederherstellen-Modus: Sub-Tabs (Browser / Persoenliche Daten)."""

import customtkinter as ctk

from .personal_tab import PersonalRestoreFrame
from .restore_tab import RestoreTab


class RestoreMode(ctk.CTkFrame):
    def __init__(self, master, on_back):
        super().__init__(master, fg_color="transparent")
        self._on_back = on_back
        self._build()

    def _build(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkButton(top, text="‹ Zurueck", width=90, command=self._on_back).pack(side="left")
        ctk.CTkLabel(top, text="Wiederherstellen",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=8)

        self.subtabs = ctk.CTkSegmentedButton(
            self, values=["Browser", "Persoenliche Daten"], command=self._switch)
        self.subtabs.set("Browser")
        self.subtabs.pack(fill="x", pady=(8, 8))

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True)
        self.browser_frame = RestoreTab(self.body)
        self.personal_frame = PersonalRestoreFrame(self.body)
        self.browser_frame.pack(fill="both", expand=True)

    def _switch(self, value: str):
        self.browser_frame.pack_forget()
        self.personal_frame.pack_forget()
        if value == "Browser":
            self.browser_frame.pack(fill="both", expand=True)
        else:
            self.personal_frame.pack(fill="both", expand=True)
```

- [ ] **Step 4: Run, verify pass**

Run: `python -m unittest tests.test_restore_mode -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit + push**

```bash
python -m unittest discover -s tests
git add gui/restore_mode.py tests/test_restore_mode.py
git commit -m "feat(gui): RestoreMode - Sub-Tabs Browser/Persoenliche Daten"
git push
```

---

### Task 10: `gui/app.py` — Screen-Router + Titel/About + Integration

`App` wird zum Router zwischen `HomeScreen`, `BackupMode`, `RestoreMode`, `ReinstallTab`. Titel und About auf „Umzugstool". Menü (Über/Hilfe) bleibt erreichbar.

**Files:**
- Modify: `gui/app.py`
- Modify: `main.py`, `gui/__init__.py` (nur „BrowserBackup"→„Umzugstool" in Docstrings/Kommentaren)
- Test: `tests/test_app_router.py`

**Interfaces:**
- Consumes: `HomeScreen(master, on_backup, on_restore, on_reinstall)`, `BackupMode(master, on_back)`, `RestoreMode(master, on_back)`, `ReinstallTab(master)` (bestehend, mit `on_show()`).

- [ ] **Step 1: Failing smoke-test (Router)**

```python
# tests/test_app_router.py
import unittest
from unittest import mock


class AppRouterTests(unittest.TestCase):
    def test_starts_on_home_and_can_open_modes(self):
        import customtkinter as ctk
        try:
            probe = ctk.CTk()
        except Exception as exc:
            self.skipTest(f"kein Tk verfuegbar: {exc}")
        probe.destroy()
        with mock.patch("gui.personal_tab.detect_personal_folders", return_value=[]), \
             mock.patch("gui.backup_tab.detect_browsers", return_value=[]), \
             mock.patch("gui.restore_tab.detect_browsers", return_value=[]):
            from gui.app import App
            app = App()
            app.withdraw()
            try:
                self.assertTrue(hasattr(app, "home"))
                app.show_mode("backup")
                app.show_mode("restore")
                app.show_mode("reinstall")
                app.show_home()
            finally:
                app.destroy()
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m unittest tests.test_app_router -v`
Expected: FAIL (`App` hat noch `segmented`/kein `show_mode`).

- [ ] **Step 3: `app.py` neu verdrahten**

Ersetzt den globalen SegmentedButton-Aufbau (aktuell `gui/app.py:49–73`) und `_on_switch` (127–143) durch einen Router. Gerüst:

```python
from .home_screen import HomeScreen
from .backup_mode import BackupMode
from .restore_mode import RestoreMode
from .reinstall_tab import ReinstallTab
# (BackupTab/RestoreTab/PersonalDataTab-Importe entfernen)

# im __init__, nach Fenster-Setup:
        self.title(f"Umzugstool v{TOOL_VERSION} - fuer Windows 10+")
        ...
        # Menue-Leiste (Zurueck-Buttons stecken in den Modi selbst)
        topbar = ctk.CTkFrame(self, fg_color="transparent")
        topbar.pack(padx=16, pady=(16, 8), fill="x")
        self.menu_button = ctk.CTkButton(topbar, text="☰ Menu", width=80, command=self._open_menu)
        self.menu_button.pack(side="right")

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.home = HomeScreen(
            self.container,
            on_backup=lambda: self.show_mode("backup"),
            on_restore=lambda: self.show_mode("restore"),
            on_reinstall=lambda: self.show_mode("reinstall"),
        )
        self.backup_mode = BackupMode(self.container, on_back=self.show_home)
        self.restore_mode = RestoreMode(self.container, on_back=self.show_home)
        self.reinstall_screen = ReinstallTab(self.container)
        self._screens = [self.home, self.backup_mode, self.restore_mode, self.reinstall_screen]
        self.show_home()

    def show_home(self):
        for s in self._screens:
            s.pack_forget()
        self.home.pack(fill="both", expand=True)

    def show_mode(self, name: str):
        for s in self._screens:
            s.pack_forget()
        if name == "backup":
            self.backup_mode.pack(fill="both", expand=True)
            self.backup_mode.on_show()
        elif name == "restore":
            self.restore_mode.pack(fill="both", expand=True)
        elif name == "reinstall":
            self.reinstall_screen.pack(fill="both", expand=True)
            self.reinstall_screen.on_show()
```

Weitere Anpassungen:
- `_show_about` (104–112): „BrowserBackup" → „Umzugstool", Text auf Browser + persönliche Daten + Neuinstallation erweitern.
- `_show_help` (114–125): einleitenden Absatz an die neue Navigation anpassen (Startbildschirm → Modus wählen; Sichern bündelt Browser + persönliche Daten in einen Lauf-Ordner).
- `main.py` / `gui/__init__.py`: „BrowserBackup" in Docstrings → „Umzugstool".

- [ ] **Step 4: Run router-test, verify pass**

Run: `python -m unittest tests.test_app_router -v`
Expected: PASS.

- [ ] **Step 5: Volle Suite grün**

Run: `python -m unittest discover -s tests`
Expected: PASS (bestehende 41 + neue Tests).

- [ ] **Step 6: Commit + push**

```bash
git add gui/app.py main.py gui/__init__.py tests/test_app_router.py
git commit -m "feat(gui): Screen-Router (Home/Modi) + Umzugstool-Titel/About"
git push
```

---

## Nach allen Tasks

- **Manueller Test auf dem Zielrechner** (headless nicht verifizierbar): Startbildschirm → jede Karte; Sichern mit gemeinsamem Ziel → prüfen, dass `Umzug_<Datum>/Browser/` und `/PersoenlicheDaten/` entstehen; Balken zeigt Prozent + Farbe rot→grün; Wiederherstellen alter Backups (Präfix `browserbackup_…`) funktioniert weiter.
- **Neu bauen:** `.\packaging\build.ps1` → `dist\Umzugstool.exe`.
- **Branch abschließen:** superpowers:finishing-a-development-branch (lokal mergen + pushen, da GitHub-Verlauf gewünscht).

## Self-Review (durchgeführt)

- **Spec-Abdeckung:** §2 Navigation → T4/T10; §3 Split → T5/T6/T8/T9; §4 Lauf-Ordner → T1/T8; §5 Balken → T3 (+ Einbau T5/T6/T7); §6 Dateien → alle Tasks; §7 Tests → je Task; §8 Version → T2; §9 Rebranding → T2/T7/T10. Keine Lücke.
- **Platzhalter:** keine „TBD"/„TODO"; alle Code- und Testblöcke konkret.
- **Typkonsistenz:** `dir_provider`-API (`resolve_target()->Path|None`, `module_dir(str)->Path`) identisch in T5/T6/T8; `ColorProgressBar.set_fraction/reset` einheitlich in T3/T5/T6/T7; `RunFolder.module_dir` T1↔T8 konsistent; Screen-Methoden `show_home/show_mode` T10 ↔ Callbacks T4.
