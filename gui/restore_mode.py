"""Wiederherstellen-Modus: Sub-Tabs (Browser / Persoenliche Daten)."""

import customtkinter as ctk

from .personal_tab import PersonalRestoreFrame
from .restore_tab import RestoreTab


class RestoreMode(ctk.CTkFrame):
    def __init__(self, master, on_back):
        super().__init__(master, fg_color="transparent")
        self._on_back = on_back
        self._build()

    def _build(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkButton(top, text="‹ Zurueck", width=90, command=self._on_back).pack(side="left")
        ctk.CTkLabel(top, text="Wiederherstellen",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=8)

        self.subtabs = ctk.CTkSegmentedButton(
            self, values=["Browser", "Persoenliche Daten"], command=self._switch)
        self.subtabs.set("Browser")
        self.subtabs.pack(fill="x", pady=(8, 8))

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True)
        self.browser_frame = RestoreTab(self.body)
        self.personal_frame = PersonalRestoreFrame(self.body)
        self.browser_frame.pack(fill="both", expand=True)

    def _switch(self, value: str):
        self.browser_frame.pack_forget()
        self.personal_frame.pack_forget()
        if value == "Browser":
            self.browser_frame.pack(fill="both", expand=True)
        else:
            self.personal_frame.pack(fill="both", expand=True)
