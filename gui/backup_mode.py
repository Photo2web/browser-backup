"""Sichern-Modus: gemeinsames Ziel + Lauf-Ordner + Sub-Tabs (Browser / Persönliche Daten)."""

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.runfolder import RunFolder

from .backup_tab import BackupTab
from .dialogs import show_error
from .personal_tab import PersonalBackupFrame


class BackupMode(ctk.CTkFrame):
    """Container für den Sichern-Modus. Stellt die dir_provider-Schnittstelle bereit."""

    def __init__(self, master, on_back):
        super().__init__(master, fg_color="transparent")
        self._on_back = on_back
        self._run: RunFolder | None = None
        self._base: Path | None = None
        self._build()

    def _build(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkButton(top, text="‹ Zurück", width=90, command=self._back).pack(side="left")
        ctk.CTkLabel(top, text="Sichern", font=ctk.CTkFont(size=16, weight="bold")).pack(
            side="left", padx=8)

        tf = ctk.CTkFrame(self, fg_color="transparent")
        tf.pack(fill="x", pady=(8, 8))
        tf.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(tf, text="Zielordner:").grid(row=0, column=0, padx=(0, 8))
        self.target_entry = ctk.CTkEntry(
            tf, placeholder_text="Gemeinsamer Zielordner für diese Sicherung")
        self.target_entry.grid(row=0, column=1, sticky="ew")
        ctk.CTkButton(tf, text="Durchsuchen ...", width=110, command=self._choose).grid(
            row=0, column=2, padx=(8, 0))

        self.subtabs = ctk.CTkSegmentedButton(
            self, values=["Browser", "Persönliche Daten"], command=self._switch)
        self.subtabs.set("Browser")
        self.subtabs.pack(fill="x", pady=(0, 8))

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True)
        self.browser_frame = BackupTab(self.body, dir_provider=self)
        self.personal_frame = PersonalBackupFrame(self.body, dir_provider=self)
        self.browser_frame.pack(fill="both", expand=True)

    # -- Sub-Tab-Umschaltung -------------------------------------------
    def _switch(self, value: str):
        self.browser_frame.pack_forget()
        self.personal_frame.pack_forget()
        if value == "Browser":
            self.browser_frame.pack(fill="both", expand=True)
        else:
            self.personal_frame.pack(fill="both", expand=True)
            self.personal_frame.on_show()

    # -- dir_provider-Schnittstelle ------------------------------------
    def resolve_target(self) -> Path | None:
        text = self.target_entry.get().strip()
        if not text:
            show_error(self, "Kein Zielordner", "Bitte einen gemeinsamen Zielordner wählen.")
            return None
        base = Path(text)
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            show_error(self, "Zielordner", f"Zielordner nicht nutzbar:\n{exc}")
            return None
        self._base = base
        return base

    def module_dir(self, name: str) -> Path:
        if self._base is None:
            raise RuntimeError("resolve_target() muss zuerst erfolgreich aufgerufen werden")
        if self._run is None:
            self._run = RunFolder(self._base)
        return self._run.module_dir(name)

    def reset_run(self) -> None:
        self._run = None

    def on_show(self) -> None:
        # Beim Betreten des Modus die Größen des sichtbaren Personal-Frames laden,
        # falls dort aktiv. (Browser-Sub-Tab braucht kein on_show.)
        if self.subtabs.get() == "Persönliche Daten":
            self.personal_frame.on_show()

    # -- intern --------------------------------------------------------
    def _choose(self):
        chosen = filedialog.askdirectory(parent=self)
        if chosen:
            self.target_entry.delete(0, "end")
            self.target_entry.insert(0, chosen)

    def _back(self):
        self.reset_run()
        self._on_back()
