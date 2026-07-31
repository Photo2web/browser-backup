"""Startbildschirm: vier Karten-Buttons (Sichern / Wiederherstellen /
Neuinstallation / Software entfernen), im 2x2-Raster."""

import customtkinter as ctk

from .home_icons import ctk_icon

_CARDS = [
    ("save", "Sichern", "Browser-Profile & persoenliche Daten sichern", "on_backup"),
    ("restore", "Wiederherstellen", "Gesicherte Daten zurueckspielen", "on_restore"),
    ("reinstall", "Neuinstallation", "Programme neu aufsetzen (winget)", "on_reinstall"),
    ("remove", "Software entfernen", "Vorinstallierte Programme deinstallieren", "on_uninstall"),
]


class HomeScreen(ctk.CTkFrame):
    def __init__(self, master, on_backup, on_restore, on_reinstall, on_uninstall):
        super().__init__(master, fg_color="transparent")
        self._commands = {"on_backup": on_backup, "on_restore": on_restore,
                          "on_reinstall": on_reinstall, "on_uninstall": on_uninstall}
        self._icons = []  # CTkImage-Referenzen halten (sonst Garbage-Collect)
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Was moechtest du tun?",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(24, 14))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(expand=True)
        # 2 Karten pro Zeile - vier Karten passen so ins Fenster (880 breit).
        for i, (kind, title, subtitle, cmd_key) in enumerate(_CARDS):
            icon = ctk_icon(kind, 60)
            self._icons.append(icon)
            ctk.CTkButton(
                row, image=icon, text=f"\n{title}\n{subtitle}", compound="top",
                width=230, height=150, corner_radius=14,
                font=ctk.CTkFont(size=14, weight="bold"),
                command=self._commands[cmd_key],
            ).grid(row=i // 2, column=i % 2, padx=14, pady=12)
