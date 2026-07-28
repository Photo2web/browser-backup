"""Tests fuer core.essential_apps und core.installplan.launch_install_script.

Ausfuehren:  python -m unittest tests.test_essential_apps

Es wird KEIN echter Installations-Lauf ausgeloest - launch_install_script wird
ueber ein gepatchtes subprocess.Popen geprueft.
"""

import unittest
from pathlib import Path
from unittest import mock

from core import essential_apps, installplan
from core.essential_apps import EssentialApp


class EssentialAppsTests(unittest.TestCase):

    def test_all_entries_are_winget_installable(self):
        for app in essential_apps.essential_apps():
            ia = app.to_installed_app()
            self.assertTrue(ia.winget_installable, f"{app.name} sollte winget-faehig sein")
            self.assertEqual(ia.source, "winget")
            self.assertTrue(ia.package_id)

    def test_no_duplicate_package_ids(self):
        ids = [a.package_id for a in essential_apps.essential_apps()]
        self.assertEqual(len(ids), len(set(ids)), "Grundausstattung enthaelt doppelte IDs")

    def test_list_is_non_empty_and_has_categories(self):
        apps = essential_apps.essential_apps()
        self.assertGreater(len(apps), 0)
        self.assertTrue(all(a.category for a in apps))

    def test_to_installed_app_keeps_name_and_id(self):
        ea = EssentialApp("Beispiel", "Vendor.Beispiel", "Test")
        ia = ea.to_installed_app()
        self.assertEqual(ia.name, "Beispiel")
        self.assertEqual(ia.package_id, "Vendor.Beispiel")
        self.assertIsNone(ia.version)


class LaunchInstallScriptTests(unittest.TestCase):

    def test_missing_script_raises(self):
        with self.assertRaises(FileNotFoundError):
            installplan.launch_install_script(Path("does_not_exist_12345.ps1"))

    def test_launches_powershell_with_script(self):
        # Reales Skript in ein Temp-Verzeichnis schreiben, Popen mocken.
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "Install-Apps.ps1"
            script.write_text("# test", encoding="utf-8")
            with mock.patch("core.installplan.subprocess.Popen") as popen:
                installplan.launch_install_script(script)
                popen.assert_called_once()
                args = popen.call_args.args[0]
                self.assertEqual(args[0], "powershell")
                self.assertIn("-File", args)
                self.assertEqual(args[-1], str(script))


if __name__ == "__main__":
    unittest.main()
