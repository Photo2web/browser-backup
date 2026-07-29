import unittest
from unittest import mock


class AppRouterTests(unittest.TestCase):
    def test_starts_on_home_and_can_open_modes(self):
        import customtkinter as ctk
        try:
            probe = ctk.CTk()
        except Exception as exc:
            self.skipTest(f"kein Tk verfuegbar: {exc}")
        probe.destroy()
        with mock.patch("gui.personal_tab.detect_personal_folders", return_value=[]), \
             mock.patch("gui.backup_tab.detect_browsers", return_value=[]), \
             mock.patch("gui.restore_tab.detect_browsers", return_value=[]):
            from gui.app import App
            app = App()
            app.withdraw()
            try:
                self.assertTrue(hasattr(app, "home"))
                app.show_mode("backup")
                app.show_mode("restore")
                app.show_mode("reinstall")
                app.show_home()
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()
