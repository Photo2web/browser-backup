import os
import tempfile
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
