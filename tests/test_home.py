import unittest

from gui.home_icons import draw_icon


class DrawIconTests(unittest.TestCase):
    def test_known_kinds_return_rgba_image_of_size(self):
        for kind in ("save", "restore", "reinstall", "remove"):
            img = draw_icon(kind, 48)
            self.assertEqual(img.size, (48, 48))
            self.assertEqual(img.mode, "RGBA")

    def test_unknown_kind_raises(self):
        with self.assertRaises(ValueError):
            draw_icon("nope", 48)


class HomeScreenSmokeTests(unittest.TestCase):
    def test_builds_and_wires_callbacks(self):
        import customtkinter as ctk
        from gui.home_screen import HomeScreen
        try:
            root = ctk.CTk()
        except Exception as exc:
            self.skipTest(f"kein Tk verfuegbar: {exc}")
        root.withdraw()
        called = []
        try:
            HomeScreen(root, on_backup=lambda: called.append("b"),
                       on_restore=lambda: called.append("r"),
                       on_reinstall=lambda: called.append("i"),
                       on_uninstall=lambda: called.append("u"))
        finally:
            root.destroy()
