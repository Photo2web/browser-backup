"""
app.py — Hauptfenster von BrowserBackup.

Dark-Theme, Segmented Button zum Umschalten zwischen "Sichern" und
"Wiederherstellen" (PROJEKT.md §10). Backup-/Restore-Logik liegt komplett
in core/ — diese Datei kuemmert sich nur um Fenster + Tab-Umschaltung.
"""

import sys
from pathlib import Path

import customtkinter as ctk

from core import TOOL_VERSION

from .backup_tab import BackupTab
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

        self.segmented = ctk.CTkSegmentedButton(
            self,
            values=["Sichern", "Wiederherstellen", "Neuinstallation"],
            command=self._on_switch,
        )
        self.segmented.set("Sichern")
        self.segmented.pack(padx=16, pady=(16, 8), fill="x")

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
