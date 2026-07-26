"""
app.py — Hauptfenster von BrowserBackup.

Dark-Theme, Segmented Button zum Umschalten zwischen "Sichern" und
"Wiederherstellen" (PROJEKT.md §10). Backup-/Restore-Logik liegt komplett
in core/ — diese Datei kuemmert sich nur um Fenster + Tab-Umschaltung.
"""

import customtkinter as ctk

from core import TOOL_VERSION

from .backup_tab import BackupTab
from .restore_tab import RestoreTab


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title(f"BrowserBackup v{TOOL_VERSION}")
        self.geometry("860x680")
        self.minsize(720, 560)

        self.segmented = ctk.CTkSegmentedButton(
            self, values=["Sichern", "Wiederherstellen"], command=self._on_switch
        )
        self.segmented.set("Sichern")
        self.segmented.pack(padx=16, pady=(16, 8), fill="x")

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.backup_tab = BackupTab(self.container)
        self.restore_tab = RestoreTab(self.container)

        self.backup_tab.pack(fill="both", expand=True)

    def _on_switch(self, value: str) -> None:
        if value == "Sichern":
            self.restore_tab.pack_forget()
            self.backup_tab.pack(fill="both", expand=True)
        else:
            self.backup_tab.pack_forget()
            self.restore_tab.pack(fill="both", expand=True)


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
