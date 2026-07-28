"""
app.py — Hauptfenster von BrowserBackup.

Dark-Theme, Segmented Button zum Umschalten zwischen "Sichern" und
"Wiederherstellen" (PROJEKT.md §10). Backup-/Restore-Logik liegt komplett
in core/ — diese Datei kuemmert sich nur um Fenster + Tab-Umschaltung.
"""

import sys
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

from core import TOOL_VERSION

from .backup_tab import BackupTab
from .dialogs import show_info
from .reinstall_tab import ReinstallTab
from .restore_tab import RestoreTab


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        # Kompaktere Schrift/Widgets (Nutzerwunsch) - spart zugleich Hoehe.
        ctk.set_widget_scaling(0.8)

        self.title(f"BrowserBackup v{TOOL_VERSION}")
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

        topbar = ctk.CTkFrame(self, fg_color="transparent")
        topbar.pack(padx=16, pady=(16, 8), fill="x")

        self.segmented = ctk.CTkSegmentedButton(
            topbar,
            values=["Sichern", "Wiederherstellen", "Neuinstallation"],
            command=self._on_switch,
        )
        self.segmented.set("Sichern")
        self.segmented.pack(side="left", fill="x", expand=True)

        self.menu_button = ctk.CTkButton(
            topbar, text="☰ Menu", width=80, command=self._open_menu
        )
        self.menu_button.pack(side="left", padx=(8, 0))

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.backup_tab = BackupTab(self.container)
        self.restore_tab = RestoreTab(self.container)
        self.reinstall_tab = ReinstallTab(self.container)

        self.backup_tab.pack(fill="both", expand=True)

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
            "Ueber BrowserBackup",
            f"BrowserBackup v{TOOL_VERSION}\n\n"
            "(c) 2026 photo2web (p2w)\n\n"
            "Sichern, Wiederherstellen und Neuinstallieren von Browser-Profilen "
            "und Programmen unter Windows. Portabel, ohne Adminrechte zum Start.",
        )

    def _show_help(self) -> None:
        show_info(
            self,
            "Hilfe",
            "Sichern: Ausgewaehlte Browser-Profile als ZIP-Datei(en) sichern.\n\n"
            "Wiederherstellen: Gesicherte ZIPs auswaehlen und in das passende "
            "Profil zurueckspielen (optional mit Sicherheits-Backup).\n\n"
            "Neuinstallation: Grundausstattung und/oder installierte Programme "
            "auswaehlen, Installationsdateien erzeugen und optional direkt via "
            "winget installieren (Internetverbindung noetig).\n\n"
            "Mehr Details stehen in der README.md im Programmordner.",
        )

    def _on_switch(self, value: str) -> None:
        # Alle Tabs ausblenden, dann den gewaehlten einblenden.
        self.backup_tab.pack_forget()
        self.restore_tab.pack_forget()
        self.reinstall_tab.pack_forget()

        if value == "Sichern":
            self.backup_tab.pack(fill="both", expand=True)
        elif value == "Wiederherstellen":
            self.restore_tab.pack(fill="both", expand=True)
        else:
            self.reinstall_tab.pack(fill="both", expand=True)
            self.reinstall_tab.on_show()


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
