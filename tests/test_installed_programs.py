import unittest

from core import installed_programs as ip


def _raw(name="App", scope="machine", key="k", **overrides):
    """Erzeugt ein (values, scope, key_path)-Tupel fuer build_programs."""
    values = {
        "DisplayName": name,
        "UninstallString": r'"C:\Program Files\App\unins.exe"',
        "DisplayVersion": "1.0",
        "Publisher": "ACME",
    }
    values.update(overrides)
    return (values, scope, key)


class BuildProgramsTests(unittest.TestCase):
    def test_basic_entry_becomes_program(self):
        progs = ip.build_programs([_raw(name="Firefox", scope="machine")])
        self.assertEqual(len(progs), 1)
        p = progs[0]
        self.assertEqual(p.name, "Firefox")
        self.assertEqual(p.version, "1.0")
        self.assertEqual(p.publisher, "ACME")
        self.assertEqual(p.scope, "machine")
        self.assertTrue(p.needs_admin)

    def test_user_scope_no_admin(self):
        progs = ip.build_programs([_raw(scope="user")])
        self.assertEqual(progs[0].scope, "user")
        self.assertFalse(progs[0].needs_admin)

    def test_drops_entry_without_displayname(self):
        self.assertEqual(ip.build_programs([_raw(DisplayName="")]), [])
        self.assertEqual(ip.build_programs([({"UninstallString": "x"}, "machine", "k")]), [])

    def test_drops_entry_without_uninstall_string(self):
        vals = {"DisplayName": "NoUninstall", "DisplayVersion": "1"}
        self.assertEqual(ip.build_programs([(vals, "machine", "k")]), [])

    def test_quiet_uninstall_string_alone_is_enough(self):
        vals = {"DisplayName": "QuietOnly", "QuietUninstallString": "x /S"}
        progs = ip.build_programs([(vals, "machine", "k")])
        self.assertEqual(len(progs), 1)
        self.assertEqual(progs[0].quiet_uninstall_string, "x /S")
        self.assertIsNone(progs[0].uninstall_string)

    def test_drops_system_component(self):
        self.assertEqual(ip.build_programs([_raw(SystemComponent=1)]), [])
        # SystemComponent=0 bleibt erhalten.
        self.assertEqual(len(ip.build_programs([_raw(SystemComponent=0)])), 1)

    def test_drops_updates(self):
        self.assertEqual(ip.build_programs([_raw(ReleaseType="Update")]), [])
        self.assertEqual(ip.build_programs([_raw(ReleaseType="Security Update")]), [])
        self.assertEqual(ip.build_programs([_raw(ParentKeyName="SomeParent")]), [])

    def test_dedupe_same_name_version_scope(self):
        # Gleicher Eintrag aus 64- und 32-Bit-View -> nur einmal.
        progs = ip.build_programs([_raw(name="Dup"), _raw(name="Dup")])
        self.assertEqual(len(progs), 1)

    def test_same_name_different_scope_kept(self):
        progs = ip.build_programs([_raw(name="Both", scope="machine"),
                                   _raw(name="Both", scope="user")])
        self.assertEqual(len(progs), 2)

    def test_sorted_by_name(self):
        progs = ip.build_programs([_raw(name="Zeta"), _raw(name="alpha"), _raw(name="Beta")])
        self.assertEqual([p.name for p in progs], ["alpha", "Beta", "Zeta"])


if __name__ == "__main__":
    unittest.main()
