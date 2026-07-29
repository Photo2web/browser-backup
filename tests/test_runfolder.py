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
