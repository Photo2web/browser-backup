"""Unit-Tests fuer core.installplan (Erzeugung der drei Ausgabedateien).

Ausfuehren:  python -m unittest tests.test_installplan
"""

import json
import unittest

from core.installed_apps import InstalledApp
from core import installplan


def _apps():
    return [
        InstalledApp("7-Zip", "7zip.7zip", "26.02", "winget"),
        InstalledApp("Advanced Renamer", "XP9MD3S1KFCPH1", "4.23", "msstore"),
        InstalledApp("O'Reilly Tool", "Test.Apostrophe", "1.0", "winget"),
        InstalledApp("Canon Treiber", None, "1.2", None),   # manuell
    ]


class MarkdownTests(unittest.TestCase):

    def test_lists_installable_and_manual_with_counts(self):
        md = installplan.build_instruction_markdown(_apps(), host="TEST-PC")
        self.assertIn("## Automatisch installierbar (winget) - 3", md)
        self.assertIn("- 7-Zip - `7zip.7zip` (Quelle: winget)", md)
        self.assertIn("- Advanced Renamer - `XP9MD3S1KFCPH1` (Quelle: msstore)", md)
        self.assertIn("## Manuell zu installieren - 1", md)
        self.assertIn("- Canon Treiber (Version 1.2)", md)
        self.assertIn("Quelle: TEST-PC", md)

    def test_empty_sections_show_keine(self):
        md = installplan.build_instruction_markdown([])
        self.assertIn("## Automatisch installierbar (winget) - 0", md)
        self.assertIn("## Manuell zu installieren - 0", md)
        self.assertIn("_(keine)_", md)


class PowerShellTests(unittest.TestCase):

    def test_contains_safety_structure(self):
        ps = installplan.build_powershell_script(_apps())
        self.assertIn("-Verb RunAs", ps)                       # Selbst-Elevation
        self.assertIn("Get-Command pwsh", ps)                  # PS7-Pruefung
        self.assertIn("function Ensure-WinGet", ps)            # winget-Bootstrap
        self.assertIn("Microsoft.DesktopAppInstaller_8wekyb3d8bbwe", ps)
        self.assertIn("Repair-WinGetPackageManager", ps)
        self.assertIn("ms-windows-store://pdp/?ProductId=9NBLGGH4NNS1", ps)
        self.assertIn(
            "winget install --id $app.Id --source $app.Source --exact --silent "
            "--accept-package-agreements --accept-source-agreements",
            ps,
        )

    def test_apps_array_contains_entries_and_escapes_apostrophes(self):
        ps = installplan.build_powershell_script(_apps())
        self.assertIn("@{ Id = '7zip.7zip'; Name = '7-Zip'; Source = 'winget' }", ps)
        self.assertIn("Source = 'msstore'", ps)
        # Apostroph im Namen wird PowerShell-konform verdoppelt.
        self.assertIn("Name = 'O''Reilly Tool'", ps)

    def test_no_installable_yields_empty_array(self):
        ps = installplan.build_powershell_script(
            [InstalledApp("Canon Treiber", None, "1.2", None)]
        )
        self.assertNotIn("@{ Id =", ps)     # keine Eintraege
        self.assertIn("$apps = @(", ps)     # Geruest bleibt


class BundleTests(unittest.TestCase):

    def test_valid_json_schema_version_and_manager(self):
        bundle = json.loads(installplan.build_unigetui_bundle(_apps()))
        self.assertEqual(bundle["export_version"], 3)
        self.assertEqual(len(bundle["packages"]), 3)
        for pkg in bundle["packages"]:
            self.assertEqual(pkg["ManagerName"], "Winget")
            self.assertIn(pkg["Source"], {"winget", "msstore"})
            self.assertIn("Id", pkg)
            self.assertIn("Name", pkg)
            self.assertIn("Version", pkg)

    def test_msstore_package_keeps_source(self):
        bundle = json.loads(installplan.build_unigetui_bundle(_apps()))
        adv = next(p for p in bundle["packages"] if p["Name"] == "Advanced Renamer")
        self.assertEqual(adv["Source"], "msstore")
        self.assertEqual(adv["Id"], "XP9MD3S1KFCPH1")

    def test_manual_apps_go_to_incompatible(self):
        bundle = json.loads(installplan.build_unigetui_bundle(_apps()))
        self.assertEqual(len(bundle["incompatible_packages"]), 1)
        self.assertEqual(bundle["incompatible_packages"][0]["Name"], "Canon Treiber")
        self.assertEqual(bundle["incompatible_packages"][0]["Source"], "Local PC")


class WriteAllTests(unittest.TestCase):

    def test_writes_three_files(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            result = installplan.write_install_plan(_apps(), tmp, host="TEST-PC")
            self.assertTrue(result.instructions_path.exists())
            self.assertTrue(result.script_path.exists())
            self.assertTrue(result.bundle_path.exists())
            self.assertEqual(result.installable_count, 3)
            self.assertEqual(result.manual_count, 1)
            # Bundle-Datei ist gueltiges JSON.
            json.loads(Path(result.bundle_path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
