# Persönliche Daten sichern & wiederherstellen — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Einen neuen Tab „Persönliche Daten" bauen, der die persönlichen Windows-Ordner (Dokumente, Bilder, Musik, Videos, Desktop, Downloads) wahlweise als ZIP oder 1:1-Kopie sichert und wiederherstellt — mit Speicherplatz-Prüfung und Fortschrittsbalken.

**Architecture:** Neues, GUI-unabhängiges Kernmodul `core/personal_data.py` (Ordner-Erkennung via Known-Folder-API, Größe/Freiplatz, Backup, Restore) und ein neuer Tab `gui/personal_tab.py` mit interner Sichern/Wiederherstellen-Umschaltung. Wiederverwendet das bestehende `Worker`+Queue+`after()`-Poll-Muster. Kein Eingriff in die Browser-Logik.

**Tech Stack:** Python 3.11+, `customtkinter`, `ctypes` (SHGetKnownFolderPath), `zipfile`, `shutil`, `os.walk`, `unittest`.

## Global Constraints

- `TOOL_VERSION` wird auf **"1.2.0"** gesetzt (`core/__init__.py`).
- **Deutsch** in UI-Texten und Code-Kommentaren.
- **Keine Adminrechte**, rein lokal, portabel.
- Tests laufen mit **`unittest`**: `python -m unittest discover -s tests` (nicht pytest).
- Tests fassen **niemals echte Nutzerordner** an — nur Temp-Ordner.
- Gesperrte/unlesbare Dateien werden **einzeln übersprungen**, der Lauf bricht nicht ab (wie in `core/backup.py`).
- Fortschritt nutzt die vorhandene Signatur `ProgressCallback = Callable[[int, int, str], None]`.
- ZIP-Inhalt liegt unter `data/…`, Manifest heißt `backup_manifest.json` und enthält `folder_key` + `source_path`.
- Dateibenennung: `browserbackup_data_<key>_<YYYY-MM-DD_HHMM>` (ZIP: `.zip`, Kopie: Ordner).

---

## File Structure

- **Create** `core/personal_data.py` — Erkennung, Größe/Freiplatz, Backup (zip/copy), Restore (skip/overwrite/newer), Manifest, `_format_bytes`.
- **Create** `gui/personal_tab.py` — Tab mit interner Sichern/Wiederherstellen-Umschaltung, Größenanzeige, Speicher-Check, Fortschrittsbalken.
- **Create** `tests/test_personal_data.py` — Unit-Tests gegen Temp-Ordner.
- **Modify** `core/__init__.py` — Version → 1.2.0.
- **Modify** `gui/app.py` — 4. Segment „Persönliche Daten" + Verdrahtung.
- **Modify** `docs/FORTSCHRITT.md`, `README.md` — Doku.

---

### Task 1: Ordner-Erkennung + Byte-Formatierung

**Files:**
- Create: `core/personal_data.py`
- Test: `tests/test_personal_data.py`

**Interfaces:**
- Produces:
  - `@dataclass PersonalFolder(key: str, display_name: str, path: Path, exists: bool)`
  - `_resolve_known_folder(guid_str: str) -> Path | None` (monkeypatch-bar)
  - `detect_personal_folders() -> list[PersonalFolder]`
  - `_format_bytes(n: int) -> str`

- [ ] **Step 1: Failing test**

```python
# tests/test_personal_data.py
import os
import unittest
from pathlib import Path

from core import personal_data as pd


class FormatBytesTests(unittest.TestCase):
    def test_units(self):
        self.assertEqual(pd._format_bytes(0), "0 B")
        self.assertEqual(pd._format_bytes(512), "512 B")
        self.assertEqual(pd._format_bytes(1500), "1.5 KB")
        self.assertEqual(pd._format_bytes(2_500_000), "2.5 MB")
        self.assertEqual(pd._format_bytes(3_200_000_000), "3.2 GB")


class DetectFoldersTests(unittest.TestCase):
    def test_uses_resolver_and_marks_existence(self):
        real = Path(os.path.expanduser("~"))

        def fake_resolver(guid):
            return real  # existierender Pfad fuer alle sechs

        orig = pd._resolve_known_folder
        pd._resolve_known_folder = fake_resolver
        try:
            folders = pd.detect_personal_folders()
        finally:
            pd._resolve_known_folder = orig

        keys = [f.key for f in folders]
        self.assertEqual(keys, ["documents", "pictures", "music", "videos", "desktop", "downloads"])
        self.assertTrue(all(f.exists for f in folders))
        self.assertEqual(folders[0].display_name, "Dokumente")

    def test_fallback_when_resolver_returns_none(self):
        orig = pd._resolve_known_folder
        pd._resolve_known_folder = lambda guid: None
        try:
            folders = pd.detect_personal_folders()
        finally:
            pd._resolve_known_folder = orig
        profile = Path(os.path.expanduser("~"))
        self.assertEqual(folders[0].path, profile / "Documents")
```

- [ ] **Step 2: Run, expect fail**

Run: `python -m unittest tests.test_personal_data -v`
Expected: FAIL (`ModuleNotFoundError` / attribute missing).

- [ ] **Step 3: Implement**

```python
# core/personal_data.py
"""
personal_data.py — Sichern/Wiederherstellen persoenlicher Windows-Ordner.

GUI-unabhaengig und testbar. Erfasst Dokumente/Bilder/Musik/Videos/Desktop/
Downloads ueber die Windows-Known-Folder-API (respektiert Umleitungen wie
OneDrive/NextCloud), berechnet Groessen/freien Platz und sichert je Ordner
wahlweise als ZIP oder 1:1-Kopie. Restore mit waehlbarem Konfliktverhalten.
"""

import ctypes
import datetime
import json
import os
import platform
import shutil
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import TOOL_VERSION

# Fortschritt: (aktuell, gesamt, meldung) — identisch zu core/backup.py.
ProgressCallback = Callable[[int, int, str], None]

# key -> (Anzeigename, KNOWNFOLDERID-GUID, Fallback-Unterordner in %USERPROFILE%)
_KNOWN_FOLDERS = (
    ("documents", "Dokumente", "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}", "Documents"),
    ("pictures",  "Bilder",    "{33E28130-4E1E-4676-835A-98395C3BC3BB}", "Pictures"),
    ("music",     "Musik",     "{4BD8D571-6D19-48D3-BE97-422220080E43}", "Music"),
    ("videos",    "Videos",    "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}", "Videos"),
    ("desktop",   "Desktop",   "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}", "Desktop"),
    ("downloads", "Downloads", "{374DE290-123F-4565-9164-39C4925E467B}", "Downloads"),
)


@dataclass
class PersonalFolder:
    key: str
    display_name: str
    path: Path
    exists: bool


def _resolve_known_folder(guid_str: str) -> Path | None:
    """Loest eine KNOWNFOLDERID (GUID-String) ueber SHGetKnownFolderPath zum
    echten Pfad auf — respektiert Umleitungen (OneDrive/NextCloud). Gibt None
    zurueck, wenn die API nicht verfuegbar ist oder scheitert (Nicht-Windows
    oder Fehler); der Aufrufer nutzt dann einen Fallback-Pfad."""
    if os.name != "nt":
        return None
    try:
        class _GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", ctypes.c_uint32),
                ("Data2", ctypes.c_uint16),
                ("Data3", ctypes.c_uint16),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        u = uuid.UUID(guid_str)
        guid = _GUID()
        guid.Data1, guid.Data2, guid.Data3 = u.time_low, u.time_mid, u.time_hi_version
        for i, b in enumerate(u.bytes[8:]):
            guid.Data4[i] = b

        ptr = ctypes.c_wchar_p()
        res = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(guid), 0, None, ctypes.byref(ptr)
        )
        if res != 0 or not ptr.value:
            return None
        path = ptr.value
        ctypes.windll.ole32.CoTaskMemFree(ptr)
        return Path(path)
    except Exception:
        return None


def detect_personal_folders() -> list[PersonalFolder]:
    """Liefert die sechs persoenlichen Ordner mit echtem Pfad + Existenz-Flag."""
    profile = Path(os.path.expanduser("~"))
    folders: list[PersonalFolder] = []
    for key, name, guid, fallback in _KNOWN_FOLDERS:
        resolved = _resolve_known_folder(guid)
        if resolved is None:
            resolved = profile / fallback
        folders.append(
            PersonalFolder(key=key, display_name=name, path=resolved, exists=resolved.is_dir())
        )
    return folders


def _format_bytes(n: int) -> str:
    """Menschenlesbare Groesse (dezimal, 1000er-Schritte)."""
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(n)
    for unit in units:
        if value < 1000.0 or unit == units[-1]:
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1000.0
```

- [ ] **Step 4: Run, expect pass**

Run: `python -m unittest tests.test_personal_data -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add core/personal_data.py tests/test_personal_data.py
git commit -m "feat(personal): Ordner-Erkennung (Known Folders) + Byte-Format"
```

---

### Task 2: Größe & freier Speicherplatz

**Files:**
- Modify: `core/personal_data.py`
- Test: `tests/test_personal_data.py`

**Interfaces:**
- Consumes: nichts aus Task 1 außer dem Modul.
- Produces:
  - `@dataclass FolderSize(total_bytes: int, file_count: int, walk_errors: list[str])`
  - `_iter_files(root) -> list[tuple[Path, str]]` (abs, rel-posix)
  - `_total_size(files) -> int`
  - `folder_size(path) -> FolderSize`
  - `free_space(path) -> int`

- [ ] **Step 1: Failing test** (an `tests/test_personal_data.py` anhängen)

```python
import tempfile


class SizeTests(unittest.TestCase):
    def test_folder_size_counts_bytes_and_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_bytes(b"12345")           # 5
            (root / "sub").mkdir()
            (root / "sub" / "b.txt").write_bytes(b"abc")      # 3
            size = pd.folder_size(root)
            self.assertEqual(size.total_bytes, 8)
            self.assertEqual(size.file_count, 2)
            self.assertEqual(size.walk_errors, [])

    def test_iter_files_relative_posix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sub").mkdir()
            (root / "sub" / "b.txt").write_bytes(b"x")
            rels = sorted(rel for _abs, rel in pd._iter_files(root))
            self.assertEqual(rels, ["sub/b.txt"])

    def test_free_space_uses_existing_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "does" / "not" / "exist"
            self.assertGreater(pd.free_space(target), 0)
```

- [ ] **Step 2: Run, expect fail**

Run: `python -m unittest tests.test_personal_data.SizeTests -v`
Expected: FAIL (attributes missing).

- [ ] **Step 3: Implement** (an `core/personal_data.py` anhängen)

```python
@dataclass
class FolderSize:
    total_bytes: int
    file_count: int
    walk_errors: list[str] = field(default_factory=list)


def _iter_files(root) -> list[tuple[Path, str]]:
    """(absoluter Pfad, relativer POSIX-Pfad) fuer alle Dateien unter root."""
    root = Path(root)
    out: list[tuple[Path, str]] = []
    if not root.is_dir():
        return out
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            abs_path = Path(dirpath) / name
            out.append((abs_path, abs_path.relative_to(root).as_posix()))
    return out


def _total_size(files) -> int:
    total = 0
    for abs_path, _rel in files:
        try:
            total += abs_path.stat().st_size
        except OSError:
            pass
    return total


def folder_size(path) -> FolderSize:
    """Gesamtgroesse + Dateizahl eines Ordners; unlesbare Unterordner werden
    gesammelt statt lautlos ignoriert (os.walk onerror)."""
    path = Path(path)
    total = 0
    count = 0
    errors: list[str] = []

    def _on_error(exc: OSError) -> None:
        errors.append(f"{exc.filename} ({exc.strerror or exc})")

    for dirpath, _dirnames, filenames in os.walk(path, onerror=_on_error):
        for name in filenames:
            fp = Path(dirpath) / name
            try:
                total += fp.stat().st_size
                count += 1
            except OSError as exc:
                errors.append(f"{fp} ({exc})")
    return FolderSize(total_bytes=total, file_count=count, walk_errors=errors)


def free_space(path) -> int:
    """Freier Platz am Ziel. Sucht den naechsten existierenden Elternpfad,
    falls das Ziel noch nicht angelegt wurde."""
    p = Path(path)
    while not p.exists():
        if p.parent == p:
            break
        p = p.parent
    return shutil.disk_usage(str(p)).free
```

- [ ] **Step 4: Run, expect pass**

Run: `python -m unittest tests.test_personal_data.SizeTests -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/personal_data.py tests/test_personal_data.py
git commit -m "feat(personal): Ordnergroesse + freier Speicherplatz"
```

---

### Task 3: Sicherung (ZIP + Kopie) mit Manifest

**Files:**
- Modify: `core/personal_data.py`
- Test: `tests/test_personal_data.py`

**Interfaces:**
- Consumes: `PersonalFolder`, `_iter_files`, `_total_size`, `TOOL_VERSION`.
- Produces:
  - `@dataclass PersonalBackupResult(target: Path, folder_key: str, mode: str, file_count: int, skipped: list[str], manifest: dict)`
  - `_timestamp() -> str`
  - `_build_manifest(folder, mode, file_count, total_bytes, skipped) -> dict`
  - `backup_personal_folder(folder, dest_dir, mode="zip", progress_callback=None) -> PersonalBackupResult`

- [ ] **Step 1: Failing test** (anhängen)

```python
def _make_folder(tmp_root: Path, key="documents") -> "pd.PersonalFolder":
    src = tmp_root / "src"
    (src / "sub").mkdir(parents=True)
    (src / "a.txt").write_bytes(b"hello")
    (src / "sub" / "b.txt").write_bytes(b"world!")
    return pd.PersonalFolder(key=key, display_name="Dokumente", path=src, exists=True)


class BackupTests(unittest.TestCase):
    def test_zip_backup_contains_data_and_manifest(self):
        import zipfile as zf_mod
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = _make_folder(root)
            dest = root / "dest"
            res = pd.backup_personal_folder(folder, dest, mode="zip")
            self.assertEqual(res.mode, "zip")
            self.assertEqual(res.file_count, 2)
            self.assertTrue(res.target.suffix == ".zip")
            self.assertTrue(res.target.name.startswith("browserbackup_data_documents_"))
            with zf_mod.ZipFile(res.target) as z:
                names = z.namelist()
                self.assertIn("data/a.txt", names)
                self.assertIn("data/sub/b.txt", names)
                self.assertIn("backup_manifest.json", names)
                manifest = json.loads(z.read("backup_manifest.json"))
            self.assertEqual(manifest["folder_key"], "documents")
            self.assertEqual(manifest["kind"], "personal_data")
            self.assertEqual(manifest["mode"], "zip")
            self.assertIn("source_path", manifest)

    def test_copy_backup_mirrors_files_and_writes_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = _make_folder(root)
            dest = root / "dest"
            res = pd.backup_personal_folder(folder, dest, mode="copy")
            self.assertEqual(res.mode, "copy")
            self.assertTrue(res.target.is_dir())
            self.assertEqual((res.target / "data" / "a.txt").read_bytes(), b"hello")
            self.assertEqual((res.target / "data" / "sub" / "b.txt").read_bytes(), b"world!")
            self.assertTrue((res.target / "backup_manifest.json").is_file())

    def test_progress_callback_called(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = _make_folder(root)
            pd.backup_personal_folder(
                folder, root / "dest", mode="copy",
                progress_callback=lambda c, t, m: calls.append((c, t, m)),
            )
        self.assertTrue(calls)
        self.assertEqual(calls[-1][0], calls[-1][1])  # am Ende current == total

    def test_invalid_mode_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = _make_folder(Path(tmp))
            with self.assertRaises(ValueError):
                pd.backup_personal_folder(folder, Path(tmp) / "d", mode="rar")
```

- [ ] **Step 2: Run, expect fail**

Run: `python -m unittest tests.test_personal_data.BackupTests -v`
Expected: FAIL.

- [ ] **Step 3: Implement** (anhängen)

```python
@dataclass
class PersonalBackupResult:
    target: Path
    folder_key: str
    mode: str
    file_count: int
    skipped: list[str] = field(default_factory=list)
    manifest: dict = field(default_factory=dict)


def _timestamp() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d_%H%M")


def _build_manifest(folder, mode, file_count, total_bytes, skipped) -> dict:
    return {
        "tool": "BrowserBackup",
        "tool_version": TOOL_VERSION,
        "kind": "personal_data",
        "created_at": datetime.datetime.now().isoformat(),
        "folder_key": folder.key,
        "folder_display_name": folder.display_name,
        "source_path": str(folder.path),
        "mode": mode,
        "file_count": file_count,
        "total_bytes": total_bytes,
        "source_host": platform.node(),
        "source_os": f"{platform.system()} {platform.release()}",
        "skipped": skipped,
    }


def backup_personal_folder(folder, dest_dir, mode="zip", progress_callback=None) -> PersonalBackupResult:
    """Sichert einen persoenlichen Ordner als ZIP (data/... + Manifest im ZIP)
    oder als 1:1-Kopie (Ordner mit data/ + backup_manifest.json daneben).
    Gesperrte Dateien werden uebersprungen und in skipped gesammelt."""
    if mode not in ("zip", "copy"):
        raise ValueError(f"Unbekannter Modus: {mode!r}")
    if not folder.path.is_dir():
        raise FileNotFoundError(f"Ordner existiert nicht: {folder.path}")

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    files = _iter_files(folder.path)
    total = len(files)
    total_bytes = _total_size(files)
    skipped: list[str] = []
    written = 0
    if progress_callback:
        progress_callback(0, total, "Sicherung wird vorbereitet ...")

    base = f"browserbackup_data_{folder.key}_{_timestamp()}"

    if mode == "zip":
        target = dest_dir / f"{base}.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for abs_path, rel in files:
                try:
                    zf.write(abs_path, f"data/{rel}")
                    written += 1
                except (OSError, PermissionError) as exc:
                    skipped.append(f"{rel} ({exc})")
                if progress_callback:
                    progress_callback(written + len(skipped), total, rel)
            manifest = _build_manifest(folder, mode, written, total_bytes, skipped)
            zf.writestr("backup_manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    else:
        target = dest_dir / base
        data_root = target / "data"
        data_root.mkdir(parents=True, exist_ok=True)
        for abs_path, rel in files:
            out = data_root / rel
            try:
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(abs_path, out)
                written += 1
            except (OSError, PermissionError) as exc:
                skipped.append(f"{rel} ({exc})")
            if progress_callback:
                progress_callback(written + len(skipped), total, rel)
        manifest = _build_manifest(folder, mode, written, total_bytes, skipped)
        (target / "backup_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    return PersonalBackupResult(
        target=target, folder_key=folder.key, mode=mode,
        file_count=written, skipped=skipped, manifest=manifest,
    )
```

- [ ] **Step 4: Run, expect pass**

Run: `python -m unittest tests.test_personal_data.BackupTests -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/personal_data.py tests/test_personal_data.py
git commit -m "feat(personal): Sicherung als ZIP/Kopie mit Manifest"
```

---

### Task 4: Wiederherstellung mit Konfliktverhalten

**Files:**
- Modify: `core/personal_data.py`
- Test: `tests/test_personal_data.py`

**Interfaces:**
- Consumes: `_iter_files`, `backup_personal_folder` (in Tests).
- Produces:
  - `@dataclass PersonalRestoreResult(folder_key, dest, restored, skipped_existing, overwritten, errors)`
  - `read_backup_manifest(source) -> dict`
  - `_zip_mtime(zinfo) -> float`
  - `_should_write(dest_file: Path, src_mtime: float, conflict: str) -> str` (→ "write"|"skip"|"overwrite")
  - `restore_personal_folder(source, dest, conflict="skip", progress_callback=None) -> PersonalRestoreResult`

- [ ] **Step 1: Failing test** (anhängen)

```python
class RestoreTests(unittest.TestCase):
    def _backup(self, root: Path, mode: str) -> Path:
        folder = _make_folder(root)
        res = pd.backup_personal_folder(folder, root / "dest", mode=mode)
        return res.target

    def test_read_manifest_from_zip_and_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zip_target = self._backup(root, "zip")
            self.assertEqual(pd.read_backup_manifest(zip_target)["folder_key"], "documents")
            copy_target = self._backup(root, "copy")
            self.assertEqual(pd.read_backup_manifest(copy_target)["folder_key"], "documents")

    def test_restore_zip_into_empty_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zip_target = self._backup(root, "zip")
            dest = root / "restore_here"
            res = pd.restore_personal_folder(zip_target, dest, conflict="skip")
            self.assertEqual((dest / "a.txt").read_bytes(), b"hello")
            self.assertEqual((dest / "sub" / "b.txt").read_bytes(), b"world!")
            self.assertEqual(res.restored, 2)
            self.assertEqual(res.skipped_existing, 0)

    def test_restore_copy_skip_keeps_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_target = self._backup(root, "copy")
            dest = root / "restore_here"
            dest.mkdir()
            (dest / "a.txt").write_bytes(b"KEEP")
            res = pd.restore_personal_folder(copy_target, dest, conflict="skip")
            self.assertEqual((dest / "a.txt").read_bytes(), b"KEEP")   # unveraendert
            self.assertEqual(res.skipped_existing, 1)
            self.assertEqual(res.restored, 1)                          # b.txt neu

    def test_restore_overwrite_replaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_target = self._backup(root, "copy")
            dest = root / "restore_here"
            dest.mkdir()
            (dest / "a.txt").write_bytes(b"OLD")
            res = pd.restore_personal_folder(copy_target, dest, conflict="overwrite")
            self.assertEqual((dest / "a.txt").read_bytes(), b"hello")
            self.assertEqual(res.overwritten, 1)

    def test_restore_newer_only_overwrites_when_backup_newer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_target = self._backup(root, "copy")
            dest = root / "restore_here"
            dest.mkdir()
            older = dest / "a.txt"
            older.write_bytes(b"OLD")
            # Ziel deutlich in die Vergangenheit setzen -> Backup ist neuer.
            os.utime(older, (1000, 1000))
            res = pd.restore_personal_folder(copy_target, dest, conflict="newer")
            self.assertEqual(older.read_bytes(), b"hello")
            self.assertEqual(res.overwritten, 1)
```

- [ ] **Step 2: Run, expect fail**

Run: `python -m unittest tests.test_personal_data.RestoreTests -v`
Expected: FAIL.

- [ ] **Step 3: Implement** (anhängen)

```python
@dataclass
class PersonalRestoreResult:
    folder_key: str
    dest: Path
    restored: int = 0
    skipped_existing: int = 0
    overwritten: int = 0
    errors: list[str] = field(default_factory=list)


def read_backup_manifest(source) -> dict:
    """Liest backup_manifest.json aus einem Backup — ZIP-Datei oder Kopie-Ordner."""
    source = Path(source)
    if source.is_file() and source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as zf:
            with zf.open("backup_manifest.json") as fh:
                return json.load(fh)
    return json.loads((source / "backup_manifest.json").read_text(encoding="utf-8"))


def _zip_mtime(zinfo) -> float:
    """mtime eines ZIP-Eintrags aus dessen date_time-Tupel (0.0 bei Fehler)."""
    try:
        return time.mktime(zinfo.date_time + (0, 0, -1))
    except (OverflowError, ValueError, OSError):
        return 0.0


def _should_write(dest_file: Path, src_mtime: float, conflict: str) -> str:
    """Entscheidet fuer eine Datei: 'write' (Ziel fehlt), 'skip' oder 'overwrite'."""
    if not dest_file.exists():
        return "write"
    if conflict == "overwrite":
        return "overwrite"
    if conflict == "newer":
        try:
            return "overwrite" if src_mtime > dest_file.stat().st_mtime else "skip"
        except OSError:
            return "overwrite"
    return "skip"  # Default + conflict == "skip"


def restore_personal_folder(source, dest, conflict="skip", progress_callback=None) -> PersonalRestoreResult:
    """Stellt ein Backup (ZIP oder Kopie-Ordner) nach dest wieder her.
    conflict: 'skip' (Default, zerstoerungsfrei), 'overwrite', 'newer'."""
    source = Path(source)
    dest = Path(dest)
    manifest = read_backup_manifest(source)
    result = PersonalRestoreResult(folder_key=manifest.get("folder_key", ""), dest=dest)
    dest.mkdir(parents=True, exist_ok=True)

    def _apply(action: str) -> None:
        if action == "skip":
            result.skipped_existing += 1
        elif action == "overwrite":
            result.overwritten += 1
        else:
            result.restored += 1

    if source.is_file() and source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as zf:
            members = [m for m in zf.infolist()
                       if m.filename.startswith("data/") and not m.is_dir()]
            total = len(members)
            for i, m in enumerate(members, start=1):
                rel = m.filename[len("data/"):]
                out = dest / rel
                src_mtime = _zip_mtime(m)
                action = _should_write(out, src_mtime, conflict)
                try:
                    if action != "skip":
                        out.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(m) as fh, open(out, "wb") as target:
                            shutil.copyfileobj(fh, target)
                        if src_mtime:
                            os.utime(out, (src_mtime, src_mtime))
                    _apply(action)
                except OSError as exc:
                    result.errors.append(f"{rel} ({exc})")
                if progress_callback:
                    progress_callback(i, total, rel)
    else:
        files = _iter_files(source / "data")
        total = len(files)
        for i, (abs_path, rel) in enumerate(files, start=1):
            out = dest / rel
            try:
                src_mtime = abs_path.stat().st_mtime
            except OSError:
                src_mtime = 0.0
            action = _should_write(out, src_mtime, conflict)
            try:
                if action != "skip":
                    out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(abs_path, out)
                _apply(action)
            except OSError as exc:
                result.errors.append(f"{rel} ({exc})")
            if progress_callback:
                progress_callback(i, total, rel)
    return result
```

- [ ] **Step 4: Run, expect pass**

Run: `python -m unittest tests.test_personal_data.RestoreTests -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/personal_data.py tests/test_personal_data.py
git commit -m "feat(personal): Wiederherstellung mit Konfliktverhalten (skip/overwrite/newer)"
```

---

### Task 5: GUI-Tab „Persönliche Daten" + Verdrahtung + Version

**Files:**
- Create: `gui/personal_tab.py`
- Modify: `gui/app.py` (Segment + Instanziierung + `_on_switch`)
- Modify: `core/__init__.py:10` (Version → 1.2.0)
- Test: `tests/test_personal_tab.py`

**Interfaces:**
- Consumes: `core.personal_data.{detect_personal_folders, folder_size, free_space, backup_personal_folder, restore_personal_folder, read_backup_manifest, _format_bytes, PersonalFolder}`, `gui.worker.Worker`, `gui.dialogs.{show_info, show_error, ask_yes_no}`.
- Produces: `class PersonalDataTab(ctk.CTkFrame)` mit `on_show()`.

- [ ] **Step 1: Version bump**

`core/__init__.py`, Zeile 10 ersetzen:

```python
TOOL_VERSION = "1.2.0"  # v1.2.0: Persoenliche Daten sichern/wiederherstellen + Fortschrittsbalken
```

- [ ] **Step 2: Failing test**

```python
# tests/test_personal_tab.py
"""Headless-Smoke-Test fuer den Persoenliche-Daten-Tab (keine echten Nutzerordner)."""
import tempfile
import unittest
from pathlib import Path

import customtkinter as ctk

from core import personal_data as pd
import gui.personal_tab as ptab


class PersonalTabBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = ctk.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_builds_with_mocked_folders_and_gathers_selection(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        src = Path(tmp.name) / "Documents"
        src.mkdir()
        (src / "a.txt").write_bytes(b"x")

        fake = [pd.PersonalFolder("documents", "Dokumente", src, True)]
        orig = ptab.detect_personal_folders
        ptab.detect_personal_folders = lambda: fake
        try:
            tab = ptab.PersonalDataTab(self.root)
        finally:
            ptab.detect_personal_folders = orig

        # Standard-Modus ist ZIP, ein Ordner in der Backup-Checkliste.
        self.assertEqual(tab.mode_var.get(), "zip")
        self.assertEqual(len(tab.backup_items), 1)
        tab.backup_items[0][1].set(True)
        selected = tab._gather_backup_selection()
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].key, "documents")
```

- [ ] **Step 3: Run, expect fail**

Run: `python -m unittest tests.test_personal_tab -v`
Expected: FAIL (`ModuleNotFoundError: gui.personal_tab`).

- [ ] **Step 4: Implement the tab**

```python
# gui/personal_tab.py
"""
personal_tab.py — Tab "Persoenliche Daten".

Sichert/stellt die persoenlichen Windows-Ordner (Dokumente, Bilder, Musik,
Videos, Desktop, Downloads) wieder her — wahlweise als ZIP oder 1:1-Kopie,
mit Speicherplatz-Pruefung und Fortschrittsbalken. Intern per SegmentedButton
zwischen "Sichern" und "Wiederherstellen" umschaltbar. Lange Laeufe laufen im
Worker-Thread (Poll per after()), damit die GUI nicht einfriert.
"""

import queue
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.personal_data import (
    PersonalFolder,
    _format_bytes,
    backup_personal_folder,
    detect_personal_folders,
    folder_size,
    free_space,
    read_backup_manifest,
    restore_personal_folder,
)

from .dialogs import ask_yes_no, show_error, show_info
from .worker import Worker

_MODE_HINT = ("Hinweis: Fotos/Musik/Videos sind schon komprimiert - eine "
             "1:1-Kopie ist dort meist schneller als ZIP.")


class PersonalDataTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.worker = Worker()
        self.folders: list[PersonalFolder] = detect_personal_folders()
        # (PersonalFolder, BooleanVar, size_label) je Ordner
        self.backup_items: list[tuple[PersonalFolder, ctk.BooleanVar, ctk.CTkLabel]] = []
        self.mode_var = ctk.StringVar(value="zip")
        self._sizes: dict[str, int] = {}
        self._sizes_loaded = False
        # Restore: Liste (manifest, source_path, target_var-Entry)
        self.restore_rows: list[tuple[dict, Path, ctk.CTkEntry]] = []
        self._build_ui()

    # -- UI -------------------------------------------------------------

    def _build_ui(self):
        # Unten fest: Fortschrittsbalken + Log (immer sichtbar).
        self.log_box = ctk.CTkTextbox(self, height=90)
        self.log_box.configure(state="disabled")
        self.log_box.pack(side="bottom", fill="x", pady=(4, 0))
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.set(0)
        self.progress_bar.pack(side="bottom", fill="x", pady=(4, 4))

        # Umschaltung Sichern | Wiederherstellen.
        self.inner_switch = ctk.CTkSegmentedButton(
            self, values=["Sichern", "Wiederherstellen"], command=self._switch_view
        )
        self.inner_switch.set("Sichern")
        self.inner_switch.pack(side="top", fill="x", pady=(0, 8))

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(side="top", fill="both", expand=True)

        self._build_backup_view()
        self._build_restore_view()
        self.backup_view.pack(fill="both", expand=True)

    def _build_backup_view(self):
        self.backup_view = ctk.CTkFrame(self.body, fg_color="transparent")

        header = ctk.CTkFrame(self.backup_view, fg_color="transparent")
        header.pack(fill="x")
        ctk.CTkLabel(header, text="Zu sichernde Ordner:").pack(side="left", padx=(0, 8))
        ctk.CTkButton(header, text="Alle auswaehlen", width=120,
                      command=self._select_all_backup).pack(side="left", padx=4)

        self.backup_list = ctk.CTkScrollableFrame(self.backup_view, height=170)
        self.backup_list.pack(fill="x", pady=(4, 8))
        for folder in self.folders:
            row = ctk.CTkFrame(self.backup_list, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=1)
            var = ctk.BooleanVar(value=False)
            state = "normal" if folder.exists else "disabled"
            text = folder.display_name if folder.exists else f"{folder.display_name} (nicht vorhanden)"
            ctk.CTkCheckBox(row, text=text, variable=var, state=state).pack(side="left")
            size_label = ctk.CTkLabel(row, text="", text_color="gray70")
            size_label.pack(side="right")
            self.backup_items.append((folder, var, size_label))

        mode_frame = ctk.CTkFrame(self.backup_view, fg_color="transparent")
        mode_frame.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(mode_frame, text="Format:").pack(side="left", padx=(0, 8))
        ctk.CTkRadioButton(mode_frame, text="ZIP", variable=self.mode_var,
                           value="zip").pack(side="left", padx=6)
        ctk.CTkRadioButton(mode_frame, text="Kopie", variable=self.mode_var,
                           value="copy").pack(side="left", padx=6)
        ctk.CTkLabel(self.backup_view, text=_MODE_HINT, text_color="gray70",
                     wraplength=820, justify="left").pack(fill="x", pady=(0, 4))

        target_frame = ctk.CTkFrame(self.backup_view, fg_color="transparent")
        target_frame.pack(fill="x", pady=(0, 4))
        target_frame.grid_columnconfigure(0, weight=1)
        self.backup_target = ctk.CTkEntry(target_frame, placeholder_text="Zielordner fuer die Sicherung")
        self.backup_target.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(target_frame, text="Durchsuchen ...", width=110,
                      command=lambda: self._choose_dir(self.backup_target)).grid(row=0, column=1, padx=(8, 0))

        self.totals_label = ctk.CTkLabel(self.backup_view, text="Groessen werden geladen ...",
                                         text_color="gray70")
        self.totals_label.pack(fill="x", pady=(2, 4))
        self.backup_button = ctk.CTkButton(self.backup_view, text="Sichern",
                                           command=self._on_backup_clicked)
        self.backup_button.pack(pady=(0, 4))

    def _build_restore_view(self):
        self.restore_view = ctk.CTkFrame(self.body, fg_color="transparent")

        btns = ctk.CTkFrame(self.restore_view, fg_color="transparent")
        btns.pack(fill="x")
        ctk.CTkButton(btns, text="Backup-ZIP(s) waehlen ...", command=self._choose_restore_zips).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Kopie-Ordner waehlen ...", command=self._choose_restore_copy).pack(side="left", padx=4)

        self.restore_list = ctk.CTkScrollableFrame(self.restore_view, height=200)
        self.restore_list.pack(fill="both", expand=True, pady=(6, 6))
        self.restore_hint = ctk.CTkLabel(self.restore_list,
                                         text="Noch kein Backup gewaehlt.", text_color="gray70")
        self.restore_hint.pack(anchor="w", padx=8, pady=8)

        self.restore_button = ctk.CTkButton(self.restore_view, text="Wiederherstellen",
                                            command=self._on_restore_clicked)
        self.restore_button.pack(pady=(0, 4))

    # -- Umschaltung / on_show -----------------------------------------

    def _switch_view(self, value: str):
        self.backup_view.pack_forget()
        self.restore_view.pack_forget()
        if value == "Sichern":
            self.backup_view.pack(fill="both", expand=True)
        else:
            self.restore_view.pack(fill="both", expand=True)

    def on_show(self):
        """Beim Anzeigen des Tabs die Ordnergroessen einmal im Hintergrund laden."""
        if not self._sizes_loaded and not self.worker.is_running():
            self._load_sizes()

    # -- Groessen laden -------------------------------------------------

    def _load_sizes(self):
        existing = [f for f, _v, _l in self.backup_items if f.exists]

        def run(_progress):
            return {f.key: folder_size(f.path).total_bytes for f in existing}

        self.worker.start(run)
        self.after(120, self._poll_sizes)

    def _poll_sizes(self):
        try:
            while True:
                item = self.worker.queue.get_nowait()
                if item[0] == "done":
                    self._on_sizes_loaded(item[1])
                    return
                if item[0] == "error":
                    self._log(f"Groessen konnten nicht geladen werden: {item[1]}")
                    return
        except queue.Empty:
            pass
        self.after(120, self._poll_sizes)

    def _on_sizes_loaded(self, sizes: dict):
        self._sizes = sizes
        self._sizes_loaded = True
        for folder, _var, label in self.backup_items:
            if folder.key in sizes:
                label.configure(text=_format_bytes(sizes[folder.key]))
        self._update_totals()

    def _update_totals(self):
        total = sum(self._sizes.get(f.key, 0) for f, v, _l in self.backup_items if v.get())
        self.totals_label.configure(text=f"Auswahl gesamt: {_format_bytes(total)}")

    # -- Sichern --------------------------------------------------------

    def _gather_backup_selection(self) -> list[PersonalFolder]:
        return [f for f, v, _l in self.backup_items if v.get() and f.exists]

    def _select_all_backup(self):
        for f, v, _l in self.backup_items:
            if f.exists:
                v.set(True)
        self._update_totals()

    def _on_backup_clicked(self):
        if self.worker.is_running():
            return
        selected = self._gather_backup_selection()
        if not selected:
            show_error(self, "Keine Auswahl", "Bitte mindestens einen vorhandenen Ordner auswaehlen.")
            return
        dest_text = self.backup_target.get().strip()
        if not dest_text:
            show_error(self, "Kein Zielordner", "Bitte einen Zielordner auswaehlen.")
            return
        dest = Path(dest_text)

        needed = sum(self._sizes.get(f.key, 0) for f in selected)
        try:
            free = free_space(dest)
        except OSError as exc:
            show_error(self, "Zielordner", f"Zielordner nicht nutzbar:\n{exc}")
            return
        if needed > free:
            show_error(self, "Zu wenig Speicherplatz",
                       f"Benoetigt (max.): {_format_bytes(needed)}\n"
                       f"Frei am Ziel: {_format_bytes(free)}\n\n"
                       "Bitte Ziel mit mehr Platz waehlen oder weniger Ordner auswaehlen.")
            return

        mode = self.mode_var.get()
        self.backup_button.configure(state="disabled", text="Sicherung laeuft ...")
        self.progress_bar.set(0)
        self._log(f"Sichere {len(selected)} Ordner ({mode}) ...")
        total_items = len(selected)

        def run(progress_callback):
            results = []
            for index, folder in enumerate(selected, start=1):
                def cb(c, t, m, _f=folder, _i=index):
                    progress_callback(c, t, f"[{_i}/{total_items}] {_f.display_name}: {m}")
                results.append(backup_personal_folder(folder, dest, mode=mode, progress_callback=cb))
            return results

        self.worker.start(run)
        self.after(100, lambda: self._poll_run(self._on_backup_done))

    def _on_backup_done(self, results):
        self.progress_bar.set(1)
        self.backup_button.configure(state="normal", text="Sichern")
        total_files = sum(r.file_count for r in results)
        total_skipped = sum(len(r.skipped) for r in results)
        self._log(f"Fertig. {len(results)} Ordner gesichert, {total_files} Dateien.")
        lines = [f"{len(results)} Ordner gesichert.", f"Dateien insgesamt: {total_files}"]
        if total_skipped:
            lines.append(f"Uebersprungene (gesperrte) Dateien: {total_skipped}")
        lines.append(f"Zielordner: {results[0].target.parent}")
        show_info(self, "Sicherung abgeschlossen", "\n".join(lines))

    # -- Wiederherstellen ----------------------------------------------

    def _choose_restore_zips(self):
        paths = filedialog.askopenfilenames(parent=self, title="Backup-ZIP(s) waehlen",
                                            filetypes=[("ZIP", "*.zip")])
        self._load_restore_sources([Path(p) for p in paths])

    def _choose_restore_copy(self):
        chosen = filedialog.askdirectory(parent=self, title="Kopie-Ordner waehlen")
        if chosen:
            self._load_restore_sources([Path(chosen)])

    def _load_restore_sources(self, sources: list[Path]):
        if not sources:
            return
        for child in self.restore_list.winfo_children():
            child.destroy()
        self.restore_rows = []
        by_key = {f.key: f for f in self.folders}
        for source in sources:
            try:
                manifest = read_backup_manifest(source)
            except (OSError, KeyError, ValueError) as exc:
                self._log(f"Kein gueltiges Backup: {source.name} ({exc})")
                continue
            row = ctk.CTkFrame(self.restore_list, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=2)
            name = manifest.get("folder_display_name", manifest.get("folder_key", "?"))
            ctk.CTkLabel(row, text=f"{name}  <-  {source.name}").pack(side="left", padx=(4, 8))
            target_entry = ctk.CTkEntry(row, width=280)
            default = by_key.get(manifest.get("folder_key", ""))
            target_entry.insert(0, str(default.path) if default else "")
            target_entry.pack(side="left", padx=4)
            ctk.CTkButton(row, text="Anderen Ordner ...", width=130,
                          command=lambda e=target_entry: self._choose_dir(e)).pack(side="left", padx=4)
            self.restore_rows.append((manifest, source, target_entry))
        if not self.restore_rows:
            ctk.CTkLabel(self.restore_list, text="Keine gueltigen Backups gefunden.",
                         text_color="gray70").pack(anchor="w", padx=8, pady=8)

    def _on_restore_clicked(self):
        if self.worker.is_running() or not self.restore_rows:
            if not self.restore_rows:
                show_error(self, "Kein Backup", "Bitte zuerst ein Backup waehlen.")
            return

        jobs = []
        for manifest, source, entry in self.restore_rows:
            target = entry.get().strip()
            if not target:
                show_error(self, "Kein Ziel", f"Bitte Zielordner fuer {source.name} angeben.")
                return
            jobs.append((source, Path(target)))

        conflict = self._ask_conflict()
        if conflict is None:
            return

        self.restore_button.configure(state="disabled", text="Laeuft ...")
        self.progress_bar.set(0)
        self._log(f"Stelle {len(jobs)} Ordner wieder her (Konflikt: {conflict}) ...")
        total_items = len(jobs)

        def run(progress_callback):
            results = []
            for index, (source, target) in enumerate(jobs, start=1):
                def cb(c, t, m, _s=source, _i=index):
                    progress_callback(c, t, f"[{_i}/{total_items}] {_s.name}: {m}")
                results.append(restore_personal_folder(source, target, conflict=conflict, progress_callback=cb))
            return results

        self.worker.start(run)
        self.after(100, lambda: self._poll_run(self._on_restore_done))

    def _ask_conflict(self) -> str | None:
        """Dialog: Konfliktverhalten waehlen. Gibt 'skip'|'overwrite'|'newer'
        oder None (Abbruch) zurueck. Nutzt ask_yes_no gestaffelt, um ohne neuen
        Dialogtyp auszukommen (Default = zerstoerungsfrei)."""
        keep = ask_yes_no(self, "Vorhandene Dateien",
                          "Vorhandene Dateien am Ziel NICHT ueberschreiben?\n\n"
                          "Ja  = vorhandene ueberspringen (sicher)\n"
                          "Nein = ueberschreiben")
        if keep:
            return "skip"
        only_newer = ask_yes_no(self, "Nur neuere?",
                                "Nur ueberschreiben, wenn die Datei im Backup NEUER ist?\n\n"
                                "Ja  = nur neuere ueberschreiben\n"
                                "Nein = immer ueberschreiben")
        return "newer" if only_newer else "overwrite"

    def _on_restore_done(self, results):
        self.progress_bar.set(1)
        self.restore_button.configure(state="normal", text="Wiederherstellen")
        restored = sum(r.restored for r in results)
        overwritten = sum(r.overwritten for r in results)
        skipped = sum(r.skipped_existing for r in results)
        errors = sum(len(r.errors) for r in results)
        self._log(f"Fertig. {restored} neu, {overwritten} ueberschrieben, {skipped} uebersprungen.")
        lines = [f"Ordner: {len(results)}", f"Neu geschrieben: {restored}",
                 f"Ueberschrieben: {overwritten}", f"Uebersprungen: {skipped}"]
        if errors:
            lines.append(f"Fehler: {errors}")
        show_info(self, "Wiederherstellung abgeschlossen", "\n".join(lines))

    # -- gemeinsame Helfer ---------------------------------------------

    def _poll_run(self, on_done):
        try:
            while True:
                item = self.worker.queue.get_nowait()
                kind = item[0]
                if kind == "progress":
                    _, current, total, message = item
                    if total:
                        self.progress_bar.set(current / total)
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
        self.progress_bar.set(0)
        self.backup_button.configure(state="normal", text="Sichern")
        self.restore_button.configure(state="normal", text="Wiederherstellen")
        self._log(f"FEHLER: {exc}")
        show_error(self, "Fehler", str(exc))

    def _choose_dir(self, entry: ctk.CTkEntry):
        chosen = filedialog.askdirectory(parent=self)
        if chosen:
            entry.delete(0, "end")
            entry.insert(0, chosen)

    def _log(self, message: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
```

- [ ] **Step 5: Wire into `gui/app.py`**

`gui/app.py` — Import ergänzen (bei den anderen Tab-Imports, nach Zeile 19):

```python
from .personal_tab import PersonalDataTab
```

Segmented-Button-Werte erweitern (Zeile 51-55) — neuen Wert anhängen:

```python
        self.segmented = ctk.CTkSegmentedButton(
            topbar,
            values=["Sichern", "Wiederherstellen", "Neuinstallation", "Persoenliche Daten"],
            command=self._on_switch,
        )
```

Tab instanziieren (nach Zeile 69, `self.reinstall_tab = ...`):

```python
        self.personal_tab = PersonalDataTab(self.container)
```

`_on_switch` (Zeile 125-137) komplett ersetzen durch explizite Zweige:

```python
    def _on_switch(self, value: str) -> None:
        # Alle Tabs ausblenden, dann den gewaehlten einblenden.
        self.backup_tab.pack_forget()
        self.restore_tab.pack_forget()
        self.reinstall_tab.pack_forget()
        self.personal_tab.pack_forget()

        if value == "Sichern":
            self.backup_tab.pack(fill="both", expand=True)
        elif value == "Wiederherstellen":
            self.restore_tab.pack(fill="both", expand=True)
        elif value == "Neuinstallation":
            self.reinstall_tab.pack(fill="both", expand=True)
            self.reinstall_tab.on_show()
        else:
            self.personal_tab.pack(fill="both", expand=True)
            self.personal_tab.on_show()
```

- [ ] **Step 6: Run tab test + full suite, expect pass**

Run: `python -m unittest tests.test_personal_tab -v`
Expected: PASS.
Run: `python -m unittest discover -s tests -v`
Expected: alle grün (bestehende + neue).

- [ ] **Step 7: Manueller Startcheck (kein echter Lauf)**

Run: `python -c "import gui.app"` und `python main.py` kurz starten; Tab „Persoenliche Daten" öffnen, umschalten. **Kein** echtes Sichern/Wiederherstellen der eigenen Ordner auslösen.

- [ ] **Step 8: Commit**

```bash
git add gui/personal_tab.py gui/app.py core/__init__.py tests/test_personal_tab.py
git commit -m "feat(personal): Tab 'Persoenliche Daten' + Fortschrittsbalken (v1.2.0)"
```

---

### Task 6: Doku aktualisieren

**Files:**
- Modify: `docs/FORTSCHRITT.md`
- Modify: `README.md`

**Interfaces:** keine (nur Doku).

- [ ] **Step 1: `docs/FORTSCHRITT.md`** — neuen Abschnitt am Ende einfügen:

```markdown
## v1.2 — Persönliche Daten sichern & wiederherstellen

### Erledigt
- Neues Kernmodul `core/personal_data.py`: Known-Folder-Erkennung
  (Dokumente/Bilder/Musik/Videos/Desktop/Downloads via SHGetKnownFolderPath,
  respektiert OneDrive/NextCloud-Umleitung), Größe/freier Platz, Sicherung als
  ZIP oder 1:1-Kopie (Manifest mit `folder_key`), Wiederherstellung mit
  Konfliktverhalten (skip/overwrite/newer).
- Neuer Tab `gui/personal_tab.py` (intern Sichern/Wiederherstellen), Größen-
  anzeige, Speicherplatz-Prüfung (Quelle-Auswahl vs. freier Platz am Ziel),
  determinierter Fortschrittsbalken.
- Tests `tests/test_personal_data.py` + `tests/test_personal_tab.py`.

### Offen / Annahmen
- **Speicherbedarf** wird konservativ als Rohgröße geschätzt (ZIP kann kleiner
  sein) — nie zu optimistisch.
- **Lange Pfade (>260 Zeichen):** noch nicht per `\\?\`-Präfix abgesichert.
- Echter Restore der Nutzerordner wird erst auf dem neuen Gerät end-to-end
  getestet; Unit-Tests decken die Logik gegen Temp-Ordner ab.
```

- [ ] **Step 2: `README.md`** — im Abschnitt „Funktionen" einen Punkt ergänzen:

```markdown
- **Persönliche Daten (v1.2):** sichert die persönlichen Windows-Ordner
  (Dokumente, Bilder, Musik, Videos, Desktop, Downloads) wahlweise als ZIP oder
  1:1-Kopie und stellt sie wieder her. Mit Speicherplatz-Prüfung (Medium +
  Zielrechner) und Fortschrittsbalken. Bekannt-Ordner werden über die
  Windows-API aufgelöst (OneDrive/NextCloud-Umleitung wird berücksichtigt).
```

Und im Struktur-Baum (Abschnitt „Projektstruktur") ergänzen:

```markdown
  personal_data.py      Persoenliche Ordner sichern/wiederherstellen (v1.2)
```
```markdown
  personal_tab.py       Tab "Persoenliche Daten"
```

- [ ] **Step 3: Full test run**

Run: `python -m unittest discover -s tests -v`
Expected: alle grün.

- [ ] **Step 4: Commit**

```bash
git add docs/FORTSCHRITT.md README.md
git commit -m "docs: Persoenliche-Daten-Feature dokumentiert (v1.2)"
```

---

## Self-Review

**Spec-Abdeckung:**
- §2 Known Folders → Task 1 (`_resolve_known_folder`, `detect_personal_folders`, Fallback). ✅
- §3 Datenmodell → Tasks 1-4 (alle Dataclasses + Funktionen). ✅
- §4 Sicherung (zip/copy + Manifest) → Task 3. ✅
- §5 Speicherplatz-Prüfung → Task 2 (`folder_size`/`free_space`) + Task 5 (UI-Check vor Start, Größenanzeige). ✅
- §6 Wiederherstellung (auto-Zuordnung, skip/overwrite/newer) → Task 4 (Logik) + Task 5 (`_load_restore_sources`, `_ask_conflict`). ✅
- §7 GUI + interne Umschaltung → Task 5. ✅
- §8 Fortschrittsbalken → Task 5 (neuer Tab); Browser-Tabs haben bereits Balken (kein Retrofit nötig); Neuinstallation bewusst ohne. ✅
- §9 Tests → Tasks 1-5. ✅
- §10 Version + Doku → Task 5 (Version) + Task 6 (Doku). ✅

**Platzhalter-Scan:** keine TBD/TODO; alle Code-Steps enthalten vollständigen Code.

**Typ-Konsistenz:** `PersonalFolder`, `folder_size`, `free_space`, `backup_personal_folder(folder, dest_dir, mode, progress_callback)`, `restore_personal_folder(source, dest, conflict, progress_callback)`, `read_backup_manifest`, `_format_bytes`, `_gather_backup_selection` — Namen in Tab (Task 5) stimmen mit Kernmodul (Tasks 1-4) und Tests überein. `mode` ∈ {"zip","copy"}, `conflict` ∈ {"skip","overwrite","newer"} durchgängig.
