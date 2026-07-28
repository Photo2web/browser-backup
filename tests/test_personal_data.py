import json
import os
import tempfile
import unittest
import zipfile
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

    def test_copy_backup_skips_locked_file_without_aborting(self):
        import shutil as _shutil
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = _make_folder(root)   # a.txt + sub/b.txt
            dest = root / "dest"
            real_copy2 = _shutil.copy2

            def flaky_copy2(src, dst, *a, **k):
                if str(src).endswith("a.txt"):
                    raise PermissionError("gesperrt (Test)")
                return real_copy2(src, dst, *a, **k)

            with mock.patch("core.personal_data.shutil.copy2", side_effect=flaky_copy2):
                res = pd.backup_personal_folder(folder, dest, mode="copy")

            # Lauf ist NICHT abgebrochen, b.txt wurde gesichert, a.txt landet in skipped.
            self.assertEqual(res.file_count, 1)
            self.assertEqual(len(res.skipped), 1)
            self.assertIn("a.txt", res.skipped[0])
            self.assertTrue((res.target / "data" / "sub" / "b.txt").is_file())
            self.assertFalse((res.target / "data" / "a.txt").exists())
            # Manifest total_bytes zaehlt nur die tatsaechlich gesicherte Datei (Finding 1).
            self.assertEqual(res.manifest["file_count"], 1)
            self.assertEqual(res.manifest["total_bytes"], len(b"world!"))  # nur b.txt
