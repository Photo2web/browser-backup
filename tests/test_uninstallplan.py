import unittest
from dataclasses import dataclass

from core import uninstallplan as up


@dataclass(frozen=True)
class FakeProgram:
    name: str
    scope: str = "user"
    uninstall_string: str | None = None
    quiet_uninstall_string: str | None = None


class CommandForTests(unittest.TestCase):
    def test_prefers_quiet_uninstall_string(self):
        p = FakeProgram("A", uninstall_string="x /uninstall",
                        quiet_uninstall_string="x /silent")
        cmd, silent = up.command_for(p)
        self.assertEqual(cmd, "x /silent")
        self.assertTrue(silent)

    def test_msi_is_rewritten_to_silent(self):
        guid = "{12345678-1234-1234-1234-1234567890AB}"
        p = FakeProgram("MSI", uninstall_string=f"MsiExec.exe /X{guid}")
        cmd, silent = up.command_for(p)
        self.assertEqual(cmd, f"msiexec.exe /x{guid} /qn /norestart")
        self.assertTrue(silent)

    def test_plain_uninstall_string_is_interactive(self):
        p = FakeProgram("B", uninstall_string=r'"C:\App\unins.exe"')
        cmd, silent = up.command_for(p)
        self.assertEqual(cmd, r'"C:\App\unins.exe"')
        self.assertFalse(silent)


class BuildScriptTests(unittest.TestCase):
    def test_elevates_only_when_machine_scope_present(self):
        user_only = up.build_uninstall_script([FakeProgram("U", scope="user",
                                                            uninstall_string="x")])
        self.assertIn("$needsAdmin = $false", user_only)

        with_machine = up.build_uninstall_script([
            FakeProgram("U", scope="user", uninstall_string="x"),
            FakeProgram("M", scope="machine", uninstall_string="y"),
        ])
        self.assertIn("$needsAdmin = $true", with_machine)

    def test_script_lists_each_program(self):
        script = up.build_uninstall_script([
            FakeProgram("Alpha", uninstall_string="a"),
            FakeProgram("Beta", quiet_uninstall_string="b /S"),
        ])
        self.assertIn("Name = 'Alpha'", script)
        self.assertIn("Name = 'Beta'", script)
        self.assertIn("Silent = $true", script)   # Beta hat QuietUninstallString
        self.assertIn("Silent = $false", script)  # Alpha nicht

    def test_single_quotes_are_escaped(self):
        script = up.build_uninstall_script([FakeProgram("O'Neil", uninstall_string="x")])
        self.assertIn("Name = 'O''Neil'", script)

    def test_empty_selection_has_no_entries(self):
        script = up.build_uninstall_script([])
        self.assertIn("$apps = @(\n\n)", script)


if __name__ == "__main__":
    unittest.main()
