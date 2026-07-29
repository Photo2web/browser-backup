import tempfile
import unittest
from pathlib import Path

from core.backup import backup_profile
from core.browsers import Browser, Profile
from core.restore import restore_profile


def _make_browser_and_profile(profile_dir: Path, name: str = "Default") -> tuple[Browser, Profile]:
    """Baut ein minimales Browser/Profile-Paar auf einem echten Temp-Ordner
    auf (keine Logik gemockt) — analog zu den Fixtures in test_personal_data.py."""
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "Bookmarks").write_text("dummy", encoding="utf-8")
    profile = Profile(id=name, name=name, path=profile_dir, is_default=True)
    browser = Browser(key="chrome", display_name="Chrome", profiles=[profile])
    return browser, profile


class RestoreSafetyBackupTests(unittest.TestCase):
    def test_safety_backup_filename_has_umzug_safety_prefix(self):
        """Regressionstest fuer den Rebranding-Fund: das Sicherheits-Backup
        beim Restore muss weiterhin klar als SAFETY gekennzeichnet werden,
        auch nachdem die Backup-Dateipraefixe von "browserbackup_" auf
        "umzug_" umgestellt wurden (core/restore.py:81)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            # Quell-Backup-ZIP erzeugen, aus dem wiederhergestellt wird.
            source_browser, source_profile = _make_browser_and_profile(root / "source_profile", "Quelle")
            backup_result = backup_profile(
                source_browser, source_profile, root / "backups", exclude_cache=False
            )

            # Vorhandenes Ziel-Profil, das ueberschrieben wird — nur wenn es
            # existiert, wird ueberhaupt ein Sicherheits-Backup ausgeloest.
            target_dir = root / "target_profile"
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / "existing.txt").write_text("alt", encoding="utf-8")
            target_profile = Profile(id="Default", name="Default", path=target_dir, is_default=True)
            target_browser = Browser(key="chrome", display_name="Chrome", profiles=[target_profile])

            result = restore_profile(
                backup_result.zip_path,
                target_browser,
                target_profile,
                make_safety_backup=True,
            )

            self.assertIsNotNone(result.safety_backup_path)
            self.assertIn("umzug_SAFETY_", result.safety_backup_path.name)
            self.assertTrue(result.safety_backup_path.exists())


if __name__ == "__main__":
    unittest.main()
