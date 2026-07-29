"""
app.py — Hauptfenster von Umzugstool.

Router zwischen Startbildschirm (HomeScreen) und den drei Modi
(Sichern / Wiederherstellen / Neuinstallation, PROJEKT.md §2). Die
eigentliche Backup-/Restore-/Neuinstallations-Logik liegt komplett in
core/ und den jeweiligen Modus-Klassen — diese Datei kuemmert sich nur
um Fenster + Screen-Umschaltung.
"""

import sys
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

from core import TOOL_VERSION

from .backup_mode import BackupMode
from .dialogs import show_info
from .home_screen import HomeScreen
from .reinstall_tab import ReinstallTab
from .restore_mode import RestoreMode


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        # Kompaktere Schrift/Widgets (Nutzerwunsch) - spart zugleich Hoehe.
        ctk.set_widget_scaling(0.8)

        self.title(f"Umzugstool v{TOOL_VERSION} - fuer Windows 10+")
        self._set_window_icon()
        self.geometry("880x680")
        self.minsize(700, 480)

        # Fenster nie hoeher als der Bildschirm oeffnen, sonst sind die unteren
        # Buttons abgeschnitten (v.a. auf Laptops mit hoher DPI-Skalierung).
        self.update_idletasks()
        try:
            window_scaling = ctk.ScalingTracker.get_window_scaling(self)
        except Exception:
            window_scaling = 1.0
        usable_height = int(self.winfo_screenheight() / window_scaling) - 70
        if usable_height < 680:
            self.geometry(f"880x{max(usable_height, 480)}")

        # Menue-Leiste (Zurueck-Buttons stecken in den Modi selbst).
        topbar = ctk.CTkFrame(self, fg_color="transparent")
        topbar.pack(padx=16, pady=(16, 8), fill="x")
        self.menu_button = ctk.CTkButton(
            topbar, text="☰ Menu", width=80, command=self._open_menu
        )
        self.menu_button.pack(side="right")

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.home = HomeScreen(
            self.container,
            on_backup=lambda: self.show_mode("backup"),
            on_restore=lambda: self.show_mode("restore"),
            on_reinstall=lambda: self.show_mode("reinstall"),
        )
        self.backup_mode = BackupMode(self.container, on_back=self.show_home)
        self.restore_mode = RestoreMode(self.container, on_back=self.show_home)
        self.reinstall_screen = ReinstallTab(self.container)
        self._screens = [self.home, self.backup_mode, self.restore_mode, self.reinstall_screen]
        self.show_home()

    def show_home(self) -> None:
        for s in self._screens:
            s.pack_forget()
        self.home.pack(fill="both", expand=True)

    def show_mode(self, name: str) -> None:
        for s in self._screens:
            s.pack_forget()
        if name == "backup":
            self.backup_mode.pack(fill="both", expand=True)
            self.backup_mode.on_show()
        elif name == "restore":
            self.restore_mode.pack(fill="both", expand=True)
        elif name == "reinstall":
            self.reinstall_screen.pack(fill="both", expand=True)
            self.reinstall_screen.on_show()

    def _set_window_icon(self) -> None:
        """Setzt das Fenster-/Taskleisten-Icon. Funktioniert aus dem Quellcode
        und aus der --onefile-Exe (dort liegt die Datei unter sys._MEIPASS).
        Icon ist optional - schlaegt es fehl, startet die App trotzdem."""
        try:
            base = getattr(sys, "_MEIPASS", None) or Path(__file__).resolve().parent.parent
            ico = Path(base) / "assets" / "icon.ico"
            if ico.is_file():
                self.iconbitmap(str(ico))
        except Exception:
            pass

    def _open_menu(self) -> None:
        """Oeffnet das Menue oben rechts (Copyright / Hilfe) als Dropdown."""
        menu = tk.Menu(self, tearoff=0)
        # An das Dark-Theme angelehnt einfaerben.
        menu.configure(
            bg="#2b2b2b", fg="#dcdcdc", bd=0, activebackground="#1f6aa5",
            activeforeground="white", relief="flat",
        )
        menu.add_command(label="Copyright / Ueber", command=self._show_about)
        menu.add_command(label="Hilfe", command=self._show_help)
        x = self.menu_button.winfo_rootx()
        y = self.menu_button.winfo_rooty() + self.menu_button.winfo_height()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _show_about(self) -> None:
        show_info(
            self,
            "Ueber Umzugstool",
            f"Umzugstool v{TOOL_VERSION}\n\n"
            "(c) 2026 photo2web (p2w)\n\n"
            "Sichern, Wiederherstellen und Neuinstallieren von Browser-Profilen, "
            "persoenlichen Daten (Dokumente, Bilder, Desktop, ...) und Programmen "
            "unter Windows. Portabel, ohne Adminrechte zum Start.",
        )

    def _show_help(self) -> None:
        show_info(
            self,
            "Hilfe",
            "Auf dem Startbildschirm einen Modus waehlen:\n\n"
            "Sichern: Browser-Profile und persoenliche Daten in einem gemeinsamen "
            "Zielordner sichern (Unterordner Browser/ und PersoenlicheDaten/ im "
            "selben Lauf-Ordner).\n\n"
            "Wiederherstellen: Gesicherte Browser-ZIPs und/oder persoenliche Daten "
            "auswaehlen und zurueckspielen (optional mit Sicherheits-Backup).\n\n"
            "Neuinstallation: Grundausstattung und/oder installierte Programme "
            "auswaehlen, Installationsdateien erzeugen und optional direkt via "
            "winget installieren (Internetverbindung noetig).\n\n"
            "Mehr Details stehen in der README.md im Programmordner.",
        )


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
