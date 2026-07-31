"""
app.py — Hauptfenster von Umzugstool.

Router zwischen Startbildschirm (HomeScreen) und den drei Modi
(Sichern / Wiederherstellen / Neuinstallation, PROJEKT.md §2). Die
eigentliche Backup-/Restore-/Neuinstallations-Logik liegt komplett in
core/ und den jeweiligen Modus-Klassen — diese Datei kümmert sich nur
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
from .theme import (ACCENT, CORNER, PANEL_BG, PANEL_BORDER, TEXT_MUTED,
                    WINDOW_BG, apply_purple_theme)
from .uninstall_screen import UninstallScreen


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Einheitliches Lila-Glas-Farbschema (Dark-Mode + Akzentfarben).
        apply_purple_theme()
        self.configure(fg_color=WINDOW_BG)

        # Widget-/Schriftgröße an den Bildschirm anpassen: auf großen
        # 4K-Monitoren (ohne Windows-Skalierung) ist die Schrift sonst winzig,
        # auf kleinen Laptops darf es kompakt bleiben.
        self._apply_adaptive_scaling()

        self.title(f"Umzugstool v{TOOL_VERSION} - für Windows 10+")
        self._set_window_icon()
        self.geometry("880x680")
        self.minsize(700, 480)

        # Fenster nie höher als der Bildschirm öffnen, sonst sind die unteren
        # Buttons abgeschnitten (v.a. auf Laptops mit hoher DPI-Skalierung).
        self.update_idletasks()
        try:
            window_scaling = ctk.ScalingTracker.get_window_scaling(self)
        except Exception:
            window_scaling = 1.0
        usable_height = int(self.winfo_screenheight() / window_scaling) - 70
        if usable_height < 680:
            self.geometry(f"880x{max(usable_height, 480)}")

        # Menü-Leiste (Zurück-Buttons stecken in den Modi selbst).
        topbar = ctk.CTkFrame(self, fg_color="transparent")
        topbar.pack(padx=16, pady=(16, 8), fill="x")
        self.menu_button = ctk.CTkButton(
            topbar, text="☰ Menu", width=80, command=self._open_menu
        )
        self.menu_button.pack(side="right")

        # Content-Box als rundes Lila-Glas-Panel (dezente Kante). Der Fensterrand
        # (dunkleres Lila) rahmt das Panel; darin sitzen die Screens.
        self.panel = ctk.CTkFrame(self, fg_color=PANEL_BG, corner_radius=CORNER,
                                  border_width=1, border_color=PANEL_BORDER)
        self.panel.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        # Dezente Branding-Fußzeile ganz unten im Panel (immer sichtbar).
        self.branding = ctk.CTkLabel(
            self.panel,
            text=f"© 2026 photo2web · Umzugstool v{TOOL_VERSION}",
            text_color=TEXT_MUTED, font=ctk.CTkFont(size=11))
        self.branding.pack(side="bottom", pady=(0, 8))

        self.home = HomeScreen(
            self.panel,
            on_backup=lambda: self.show_mode("backup"),
            on_restore=lambda: self.show_mode("restore"),
            on_reinstall=lambda: self.show_mode("reinstall"),
            on_uninstall=lambda: self.show_mode("uninstall"),
        )
        self.backup_mode = BackupMode(self.panel, on_back=self.show_home)
        self.restore_mode = RestoreMode(self.panel, on_back=self.show_home)
        self.reinstall_screen = ReinstallTab(self.panel, on_back=self.show_home)
        self.uninstall_screen = UninstallScreen(self.panel, on_back=self.show_home)
        self._screens = [self.home, self.backup_mode, self.restore_mode,
                         self.reinstall_screen, self.uninstall_screen]
        self.show_home()

    # Screens sitzen im Glas-Panel: etwas Innenabstand lässt die runde Kante
    # sichtbar, die Branding-Fußzeile (side="bottom") bleibt darunter frei.
    _SCREEN_PACK = {"side": "top", "fill": "both", "expand": True,
                    "padx": 8, "pady": (8, 4)}

    def _apply_adaptive_scaling(self) -> None:
        """Setzt die customtkinter-Widget-Skalierung passend zum Bildschirm.

        Logik:
        - Skaliert Windows bereits per DPI (window_scaling >= ~1.4), bleiben wir
          fast neutral, sonst würde alles doppelt vergrößert.
        - Sonst richten wir uns nach der (physischen) Bildschirmhöhe: 4K/große
          Displays -> vergrößern, Standard -> neutral, Laptop -> kompakt.
        """
        try:
            window_scaling = ctk.ScalingTracker.get_window_scaling(self)
        except Exception:
            window_scaling = 1.0
        screen_h = self.winfo_screenheight()

        if window_scaling >= 1.4:
            widget_scaling = 0.9          # Windows vergrößert schon selbst
        elif screen_h >= 2000:
            widget_scaling = 1.15         # 4K nativ -> deutlich lesbarer
        elif screen_h >= 1400:
            widget_scaling = 1.0          # QHD / große FHD
        else:
            widget_scaling = 0.85         # Laptop-FHD/HD -> kompakt
        ctk.set_widget_scaling(widget_scaling)

    def show_home(self) -> None:
        for s in self._screens:
            s.pack_forget()
        self.home.pack(**self._SCREEN_PACK)

    def show_mode(self, name: str) -> None:
        for s in self._screens:
            s.pack_forget()
        if name == "backup":
            self.backup_mode.pack(**self._SCREEN_PACK)
            self.backup_mode.on_show()
        elif name == "restore":
            self.restore_mode.pack(**self._SCREEN_PACK)
        elif name == "reinstall":
            self.reinstall_screen.pack(**self._SCREEN_PACK)
            self.reinstall_screen.on_show()
        elif name == "uninstall":
            self.uninstall_screen.pack(**self._SCREEN_PACK)
            self.uninstall_screen.on_show()

    def _set_window_icon(self) -> None:
        """Setzt das Fenster-/Taskleisten-Icon. Funktioniert aus dem Quellcode
        und aus der --onefile-Exe (dort liegt die Datei unter sys._MEIPASS).
        Icon ist optional - schlägt es fehl, startet die App trotzdem."""
        try:
            base = getattr(sys, "_MEIPASS", None) or Path(__file__).resolve().parent.parent
            ico = Path(base) / "assets" / "icon.ico"
            if ico.is_file():
                self.iconbitmap(str(ico))
        except Exception:
            pass

    def _open_menu(self) -> None:
        """Oeffnet das Menü oben rechts (Copyright / Hilfe) als Dropdown."""
        menu = tk.Menu(self, tearoff=0)
        # An das Lila-Glas-Theme angelehnt einfärben.
        menu.configure(
            bg=PANEL_BG, fg="#dcdcdc", bd=0, activebackground=ACCENT,
            activeforeground="white", relief="flat",
        )
        menu.add_command(label="Copyright / Über", command=self._show_about)
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
            "Über Umzugstool",
            f"Umzugstool v{TOOL_VERSION}\n\n"
            "(c) 2026 photo2web (p2w)\n\n"
            "Sichern, Wiederherstellen und Neuinstallieren von Browser-Profilen, "
            "persönlichen Daten (Dokumente, Bilder, Desktop, ...) und Programmen "
            "unter Windows. Portabel, ohne Adminrechte zum Start.",
        )

    def _show_help(self) -> None:
        show_info(
            self,
            "Hilfe",
            "Auf dem Startbildschirm einen Modus wählen:\n\n"
            "Sichern: Browser-Profile und persönliche Daten in einem gemeinsamen "
            "Zielordner sichern (Unterordner Browser/ und PersoenlicheDaten/ im "
            "selben Lauf-Ordner).\n\n"
            "Wiederherstellen: Gesicherte Browser-ZIPs und/oder persönliche Daten "
            "auswählen und zurückspielen (optional mit Sicherheits-Backup).\n\n"
            "Neuinstallation: Grundausstattung und/oder installierte Programme "
            "auswählen, Installationsdateien erzeugen und optional direkt via "
            "winget installieren (Internetverbindung nötig).\n\n"
            "Mehr Details stehen in der README.md im Programmordner.",
        )


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
