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


if __name__ == "__main__":
    unittest.main()
