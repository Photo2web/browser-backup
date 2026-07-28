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
