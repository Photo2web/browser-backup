"""Startbildschirm: vier gleich grosse, edle Lila-Kacheln (dunkles Panel mit
Leucht-Rand, hellem Icon, Titel + Untertitel), 2x2-Raster.

Jede Kachel wird als EIN Bild gerendert (home_icons.ctk_card), damit kein
ueberlagertes transparentes Label die dunkle Fensterfarbe zeigt."""

import customtkinter as ctk

from .home_icons import ctk_card

_CARDS = [
    ("save", "Sichern", "Browser & persoenliche Daten", "on_backup"),
    ("restore", "Wiederherstellen", "Gesicherte Daten zurueckspielen", "on_restore"),
    ("reinstall", "Neuinstallation", "Programme neu aufsetzen", "on_reinstall"),
    ("remove", "Software entfernen", "Programme deinstallieren", "on_uninstall"),
]

# Einheitliche Kachelgroesse (alle Kacheln exakt gleich).
_CARD_W, _CARD_H = 235, 172


class HomeScreen(ctk.CTkFrame):
    def __init__(self, master, on_backup, on_restore, on_reinstall, on_uninstall):
        super().__init__(master, fg_color="transparent")
        self._commands = {"on_backup": on_backup, "on_restore": on_restore,
                          "on_reinstall": on_reinstall, "on_uninstall": on_uninstall}
        self._images = []  # CTkImage-Referenzen halten (sonst Garbage-Collect)
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Was moechtest du tun?",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(24, 14))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(expand=True)
        for i, (kind, title, subtitle, cmd_key) in enumerate(_CARDS):
            self._make_card(row, i, kind, title, subtitle, self._commands[cmd_key])

    def _make_card(self, parent, index, kind, title, subtitle, command):
        normal = ctk_card(_CARD_W, _CARD_H, kind, title, subtitle)
        hover = ctk_card(_CARD_W, _CARD_H, kind, title, subtitle, hover=True)
        self._images.append((normal, hover))

        label = ctk.CTkLabel(parent, text="", image=normal, fg_color="transparent")
        label.grid(row=index // 2, column=index % 2, padx=12, pady=10)
        label.bind("<Button-1>", lambda _e, c=command: c())
        label.bind("<Enter>", lambda _e, lbl=label, h=hover: lbl.configure(image=h))
        label.bind("<Leave>", lambda _e, lbl=label, n=normal: lbl.configure(image=n))
