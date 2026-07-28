"""Unit-Tests fuer den winget-list-Parser (core.installed_apps).

Ausfuehren aus dem Projekt-Root:
    python -m unittest tests.test_installed_apps

Die Testdaten sind an der realen `winget list`-Ausgabe auf Mikes System
orientiert (lokalisierte Kopfzeile, ARP-/MSIX-Eintraege ohne Quelle,
optionale Spalte "Verfuegbar"). Damit die Spaltenoffsets eindeutig sind,
werden die Zeilen ueber feste Spaltenbreiten zusammengesetzt.
"""

import unittest

from core.installed_apps import InstalledApp, _parse_winget_list


def _row(*fields_and_widths):
    """Baut eine Tabellenzeile aus (Wert, Breite)-Paaren; letztes Feld ohne Breite."""
    out = []
    for item in fields_and_widths:
        if isinstance(item, tuple):
            value, width = item
            out.append(str(value).ljust(width))
        else:
            out.append(str(item))
    return "".join(out).rstrip()


# Spaltenbreiten (Name, ID, Version, Verfuegbar); Quelle steht am Ende.
_W_NAME, _W_ID, _W_VER, _W_AVAIL = 30, 40, 12, 10


def _build_output(rows, with_available=True):
    """Erzeugt einen kompletten winget-list-Textblock (dt. Header + Trennlinie)."""
    if with_available:
        header = _row(("Name", _W_NAME), ("ID", _W_ID), ("Version", _W_VER),
                      ("Verfügbar", _W_AVAIL), "Quelle")
    else:
        header = _row(("Name", _W_NAME), ("ID", _W_ID), ("Version", _W_VER), "Quelle")
    separator = "-" * 120
    return "\n".join([header, separator] + rows)


class ParseWingetListTests(unittest.TestCase):

    def test_winget_row_is_installable(self):
        row = _row(("7-Zip 26.02 (x64)", _W_NAME), ("7zip.7zip", _W_ID),
                   ("26.02", _W_VER), ("", _W_AVAIL), "winget")
        apps = _parse_winget_list(_build_output([row]))
        self.assertEqual(len(apps), 1)
        app = apps[0]
        self.assertEqual(app.name, "7-Zip 26.02 (x64)")
        self.assertEqual(app.package_id, "7zip.7zip")
        self.assertEqual(app.source, "winget")
        self.assertTrue(app.winget_installable)

    def test_msstore_row_is_installable(self):
        row = _row(("Advanced Renamer", _W_NAME), ("XP9MD3S1KFCPH1", _W_ID),
                   ("4.23", _W_VER), ("", _W_AVAIL), "msstore")
        app = _parse_winget_list(_build_output([row]))[0]
        self.assertEqual(app.package_id, "XP9MD3S1KFCPH1")
        self.assertEqual(app.source, "msstore")
        self.assertTrue(app.winget_installable)

    def test_arp_row_without_source_is_manual(self):
        row = _row(("Amazon Photos", _W_NAME), (r"ARP\User\X64\Amazon Photos", _W_ID),
                   ("11.2.0", _W_VER), ("", _W_AVAIL), "")
        app = _parse_winget_list(_build_output([row]))[0]
        self.assertEqual(app.name, "Amazon Photos")
        self.assertIsNone(app.package_id)   # ARP-Bezeichner ist kein winget-Paket
        self.assertIsNone(app.source)
        self.assertFalse(app.winget_installable)

    def test_msix_row_without_source_is_manual(self):
        row = _row(("AMD Radeon Software", _W_NAME),
                   (r"MSIX\AdvancedMicroDevicesInc-RSXCM_22.10.0.0_x64__v2es6h43hjn86", _W_ID),
                   ("22.10.0.0", _W_VER), ("", _W_AVAIL), "")
        app = _parse_winget_list(_build_output([row]))[0]
        self.assertIsNone(app.package_id)
        self.assertFalse(app.winget_installable)

    def test_row_with_available_update_still_parses_source(self):
        row = _row(("AnyDesk", _W_NAME), ("AnyDesk.AnyDesk", _W_ID),
                   ("ad 9.7.11", _W_VER), ("9.7.12", _W_AVAIL), "winget")
        app = _parse_winget_list(_build_output([row]))[0]
        self.assertEqual(app.package_id, "AnyDesk.AnyDesk")
        self.assertEqual(app.version, "ad 9.7.11")
        self.assertEqual(app.source, "winget")
        self.assertTrue(app.winget_installable)

    def test_four_column_output_without_available(self):
        # Kein Update vorhanden -> winget laesst die Spalte "Verfuegbar" weg.
        row = _row(("calibre 64bit", _W_NAME), ("calibre.calibre", _W_ID),
                   ("9.11.0", _W_VER), "winget")
        app = _parse_winget_list(_build_output([row], with_available=False))[0]
        self.assertEqual(app.name, "calibre 64bit")
        self.assertEqual(app.package_id, "calibre.calibre")
        self.assertEqual(app.source, "winget")
        self.assertTrue(app.winget_installable)

    def test_mixed_block_counts_installable_and_manual(self):
        rows = [
            _row(("7-Zip", _W_NAME), ("7zip.7zip", _W_ID), ("26.02", _W_VER), ("", _W_AVAIL), "winget"),
            _row(("Amazon Photos", _W_NAME), (r"ARP\User\X64\Amazon Photos", _W_ID), ("11.2.0", _W_VER), ("", _W_AVAIL), ""),
            _row(("Advanced Renamer", _W_NAME), ("XP9MD3S1KFCPH1", _W_ID), ("4.23", _W_VER), ("", _W_AVAIL), "msstore"),
        ]
        apps = _parse_winget_list(_build_output(rows))
        self.assertEqual(len(apps), 3)
        installable = [a for a in apps if a.winget_installable]
        self.assertEqual({a.name for a in installable}, {"7-Zip", "Advanced Renamer"})

    def test_leading_spinner_junk_before_header_is_ignored(self):
        block = _build_output([
            _row(("7-Zip", _W_NAME), ("7zip.7zip", _W_ID), ("26.02", _W_VER), ("", _W_AVAIL), "winget"),
        ])
        noisy = "   \n\\\n  |\n" + block   # simulierte Fortschritts-Ausgabe davor
        apps = _parse_winget_list(noisy)
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0].package_id, "7zip.7zip")

    def test_empty_or_headerless_text_returns_empty_list(self):
        self.assertEqual(_parse_winget_list(""), [])
        self.assertEqual(_parse_winget_list("kein Header hier\nirgendwas"), [])


if __name__ == "__main__":
    unittest.main()
