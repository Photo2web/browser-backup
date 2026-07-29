"""Headless-Smoke-Tests fuer die Persoenliche-Daten-Frames (keine echten Nutzerordner)."""
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
    def test_backup_frame_resets_button_after_error(self, _m):
        """Regression: Sichern-Button darf nach einem Fehler nicht dauerhaft
        gesperrt bleiben (Frame wird in App.__init__ nur einmal gebaut)."""
        from gui.personal_tab import PersonalBackupFrame
        root = self._root()
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        try:
            frame = PersonalBackupFrame(root, dir_provider=_FakeProvider(tmp.name))
            frame.backup_button.configure(state="disabled", text="Sicherung laeuft ...")
            with mock.patch("gui.personal_tab.show_error"):
                frame._on_run_error(RuntimeError("x"))
            self.assertEqual(str(frame.backup_button.cget("state")), "normal")
            self.assertEqual(frame.backup_button.cget("text"), "Sichern")
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


class PersonalBackupFrameSelectionTests(unittest.TestCase):
    """Verhaltensbewahrung: Groessen-Auswahl-Logik nach dem Split."""

    def _root(self):
        import customtkinter as ctk
        try:
            root = ctk.CTk()
        except Exception as exc:
            self.skipTest(f"kein Tk verfuegbar: {exc}")
        root.withdraw()
        return root

    def test_builds_with_mocked_folders_and_gathers_selection(self):
        from core import personal_data as pd
        import gui.personal_tab as ptab

        root = self._root()
        try:
            tmp = tempfile.TemporaryDirectory()
            self.addCleanup(tmp.cleanup)
            src = Path(tmp.name) / "Documents"
            src.mkdir()
            (src / "a.txt").write_bytes(b"x")

            fake = [pd.PersonalFolder("documents", "Dokumente", src, True)]
            orig = ptab.detect_personal_folders
            ptab.detect_personal_folders = lambda: fake
            try:
                frame = ptab.PersonalBackupFrame(root, dir_provider=_FakeProvider(tmp.name))
            finally:
                ptab.detect_personal_folders = orig

            # Standard-Modus ist ZIP, ein Ordner in der Backup-Checkliste.
            self.assertEqual(frame.mode_var.get(), "zip")
            self.assertEqual(len(frame.backup_items), 1)
            frame.backup_items[0][1].set(True)
            selected = frame._gather_backup_selection()
            self.assertEqual(len(selected), 1)
            self.assertEqual(selected[0].key, "documents")
        finally:
            root.destroy()
