import unittest

from gui.progress import color_for_fraction


def _rgb(hexstr):
    hexstr = hexstr.lstrip("#")
    return int(hexstr[0:2], 16), int(hexstr[2:4], 16), int(hexstr[4:6], 16)


class ColorForFractionTests(unittest.TestCase):
    def test_zero_is_reddish(self):
        r, g, b = _rgb(color_for_fraction(0.0))
        self.assertGreater(r, 150)
        self.assertLess(g, 90)

    def test_one_is_greenish(self):
        r, g, b = _rgb(color_for_fraction(1.0))
        self.assertGreater(g, 150)
        self.assertLess(r, 90)

    def test_half_is_yellowish(self):
        r, g, b = _rgb(color_for_fraction(0.5))
        self.assertGreater(r, 150)
        self.assertGreater(g, 150)

    def test_clamps_out_of_range(self):
        self.assertEqual(color_for_fraction(-1.0), color_for_fraction(0.0))
        self.assertEqual(color_for_fraction(2.0), color_for_fraction(1.0))


class ColorProgressBarWidgetTests(unittest.TestCase):
    def test_set_fraction_updates_label(self):
        import customtkinter as ctk
        from gui.progress import ColorProgressBar
        try:
            root = ctk.CTk()
        except Exception as exc:  # kein Display (CI) -> ueberspringen
            self.skipTest(f"kein Tk verfuegbar: {exc}")
        root.withdraw()
        try:
            bar = ColorProgressBar(root)
            bar.set_fraction(0.42)
            self.assertEqual(bar._label.cget("text"), "42 %")
        finally:
            root.destroy()
