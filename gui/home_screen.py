"""Startbildschirm: drei Karten-Buttons (Sichern / Wiederherstellen / Neuinstallation)."""

import customtkinter as ctk

from .home_icons import ctk_icon

_CARDS = [
    ("save", "Sichern", "Browser-Profile & persoenliche Daten sichern", "on_backup"),
    ("restore", "Wiederherstellen", "Gesicherte Daten zurueckspielen", "on_restore"),
    ("reinstall", "Neuinstallation", "Programme neu aufsetzen (winget)", "on_reinstall"),
]


class HomeScreen(ctk.CTkFrame):
    def __init__(self, master, on_backup, on_restore, on_reinstall):
        super().__init__(master, fg_color="transparent")
        self._commands = {"on_backup": on_backup, "on_restore": on_restore,
                          "on_reinstall": on_reinstall}
        self._icons = []  # CTkImage-Referenzen halten (sonst Garbage-Collect)
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Was moechtest du tun?",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(28, 18))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(expand=True)
        for i, (kind, title, subtitle, cmd_key) in enumerate(_CARDS):
            icon = ctk_icon(kind, 64)
            self._icons.append(icon)
            ctk.CTkButton(
                row, image=icon, text=f"\n{title}\n{subtitle}", compound="top",
                width=230, height=170, corner_radius=14,
                font=ctk.CTkFont(size=14, weight="bold"),
                command=self._commands[cmd_key],
            ).grid(row=0, column=i, padx=14, pady=14)
