import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from core import personal_data as pd


class DiskReservationTests(unittest.TestCase):
    def test_no_files_no_slack(self):
        self.assertEqual(pd.disk_reservation(0, 0, 4096), 0)

    def test_adds_one_cluster_per_file(self):
        self.assertEqual(pd.disk_reservation(1000, 1, 4096), 1000 + 4096)
        self.assertEqual(pd.disk_reservation(10_000, 3, 131072), 10_000 + 3 * 131072)

    def test_is_upper_bound_of_real_on_disk_size(self):
        # Reale Belegung = sum(ceil(size/cluster)*cluster); die Reservierung
        # darf sie nie unterschaetzen.
        cluster = 4096
        sizes = [1, 4096, 4097, 100_000, 0]
        real = sum(-(-s // cluster) * cluster for s in sizes)  # ceil-Division
        raw = sum(sizes)
        reservation = pd.disk_reservation(raw, len(sizes), cluster)
        self.assertGreaterEqual(reservation, real)

    def test_bad_cluster_falls_back(self):
        self.assertEqual(pd.disk_reservation(500, 2, 0), 500 + 2 * 4096)


class ClusterSizeTests(unittest.TestCase):
    def test_returns_positive_for_existing_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertGreater(pd.cluster_size(tmp), 0)

    def test_returns_positive_for_nonexistent_child(self):
        # Nicht existierendes Ziel -> sucht existierenden Elternpfad.
        with tempfile.TemporaryDirectory() as tmp:
            self.assertGreater(pd.cluster_size(Path(tmp) / "gibtsnicht" / "auchnicht"), 0)


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
    (src / "sub").mkdir(parents=True, exist_ok=True)
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
            self.assertTrue(res.target.name.startswith("umzug_data_documents_"))
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

    def test_restore_records_skipped_file_paths(self):
        # Fuer die TXT-Liste: uebersprungene Dateien werden namentlich gemerkt.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_target = self._backup(root, "copy")
            dest = root / "restore_here"
            dest.mkdir()
            (dest / "a.txt").write_bytes(b"KEEP")
            res = pd.restore_personal_folder(copy_target, dest, conflict="skip")
            self.assertIn("a.txt", res.skipped_files)
            self.assertEqual(len(res.skipped_files), res.skipped_existing)

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


class FindPersonalBackupsTests(unittest.TestCase):
    """find_personal_backups: Umzugsordner rekursiv nach Datensicherungen scannen."""

    def _make_run_folder(self, root: Path) -> tuple[Path, Path]:
        """Legt Umzug_x/PersoenlicheDaten/ mit je einem ZIP- und Kopie-Backup an."""
        pd_dir = root / "Umzug_2026-07-31_1200" / "PersoenlicheDaten"
        pd_dir.mkdir(parents=True)
        docs = _make_folder(root, key="documents")   # legt root/src an
        pd.backup_personal_folder(docs, pd_dir, mode="zip")
        pics = pd.PersonalFolder(key="pictures", display_name="Bilder",
                                 path=root / "src", exists=True)
        pd.backup_personal_folder(pics, pd_dir, mode="copy")
        return root / "Umzug_2026-07-31_1200", pd_dir

    def test_finds_zip_and_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_folder, _pd_dir = self._make_run_folder(root)
            found = pd.find_personal_backups(run_folder)
            keys = sorted(m["folder_key"] for _p, m in found)
            self.assertEqual(keys, ["documents", "pictures"])

    def test_scanning_subfolder_finds_same(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _run_folder, pd_dir = self._make_run_folder(root)
            self.assertEqual(len(pd.find_personal_backups(pd_dir)), 2)

    def test_ignores_foreign_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Passt zum Namenspraefix, hat aber kein gueltiges Manifest -> kein Fund.
            bad = root / "umzug_data_fake.zip"
            with zipfile.ZipFile(bad, "w") as z:
                z.writestr("hello.txt", "x")
            self.assertEqual(pd.find_personal_backups(root), [])

    def test_ignores_unrelated_named_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "urlaub.zip").write_bytes(b"nicht mal ein zip")
            self.assertEqual(pd.find_personal_backups(root), [])

    def test_does_not_descend_into_copy_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = _make_folder(root)
            res = pd.backup_personal_folder(folder, root / "dest", mode="copy")
            found = pd.find_personal_backups(root)
            # Genau ein Fund (das Kopie-Backup), kein Doppelfund aus dessen data/.
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0][0], res.target)

    def test_empty_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(pd.find_personal_backups(Path(tmp)), [])

    def test_missing_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(pd.find_personal_backups(Path(tmp) / "gibtsnicht"), [])

    def test_sorted_by_display_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_folder, _pd_dir = self._make_run_folder(root)
            names = [(m.get("folder_display_name") or "") for _p, m in
                     pd.find_personal_backups(run_folder)]
            self.assertEqual(names, sorted(names, key=str.lower))
