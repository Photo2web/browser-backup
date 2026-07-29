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
