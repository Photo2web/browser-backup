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
            # nach Reset ein neuer Lauf: reset_run() muss _run verwerfen, und
            # der naechste module_dir()-Aufruf muss ein NEUES RunFolder-Objekt
            # anlegen (deterministisch pruefbar per id(), unabhaengig vom
            # Minuten-Zeitstempel).
            run_before = mode._run
            mode.reset_run()
            self.assertIsNone(mode._run)
            mode.resolve_target()
            c = mode.module_dir("Browser")
            self.assertIsNotNone(mode._run)
            self.assertIsNot(mode._run, run_before)
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
