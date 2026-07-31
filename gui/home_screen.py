"""Startbildschirm: vier gleich grosse Kacheln mit Lila-Verlauf
(Sichern / Wiederherstellen / Neuinstallation / Software entfernen), 2x2-Raster."""

import customtkinter as ctk

from .home_icons import ctk_gradient, ctk_icon

_CARDS = [
    ("save", "Sichern", "Browser-Profile & persoenliche Daten sichern", "on_backup"),
    ("restore", "Wiederherstellen", "Gesicherte Daten zurueckspielen", "on_restore"),
    ("reinstall", "Neuinstallation", "Programme neu aufsetzen (winget)", "on_reinstall"),
    ("remove", "Software entfernen", "Vorinstallierte Programme deinstallieren", "on_uninstall"),
]

# Einheitliche Kachelgroesse (alle Kacheln exakt gleich) + Lila-Verlauf.
_CARD_W, _CARD_H, _RADIUS = 230, 150, 16
_TOP = (124, 58, 237)          # #7c3aed - kraeftiges Violett oben
_BOTTOM = (46, 16, 101)        # #2e1065 - dunkles Lila unten
_TOP_HOVER = (150, 92, 250)    # etwas heller beim Ueberfahren
_BOTTOM_HOVER = (68, 28, 132)
_CARD_TEXT = "#f2ecff"


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

        # Eine Verlaufs-Grafik fuer alle Kacheln (dadurch garantiert identisch).
        self._grad = ctk_gradient(_CARD_W, _CARD_H, _RADIUS, _TOP, _BOTTOM)
        self._grad_hover = ctk_gradient(_CARD_W, _CARD_H, _RADIUS, _TOP_HOVER, _BOTTOM_HOVER)

        for i, (kind, title, subtitle, cmd_key) in enumerate(_CARDS):
            self._make_card(row, i, kind, title, subtitle, self._commands[cmd_key])

    def _make_card(self, parent, index, kind, title, subtitle, command):
        card = ctk.CTkFrame(parent, width=_CARD_W, height=_CARD_H, fg_color="transparent")
        card.grid(row=index // 2, column=index % 2, padx=14, pady=12)
        card.grid_propagate(False)  # feste Groesse - alle Kacheln exakt gleich

        bg = ctk.CTkLabel(card, text="", image=self._grad, fg_color="transparent")
        bg.place(relx=0, rely=0, anchor="nw")

        icon = ctk_icon(kind, 56)
        self._icons.append(icon)
        icon_lbl = ctk.CTkLabel(card, text="", image=icon, fg_color="transparent")
        icon_lbl.place(relx=0.5, rely=0.30, anchor="center")

        text_lbl = ctk.CTkLabel(
            card, text=f"{title}\n{subtitle}", fg_color="transparent",
            text_color=_CARD_TEXT, justify="center", wraplength=_CARD_W - 26,
            font=ctk.CTkFont(size=13, weight="bold"))
        text_lbl.place(relx=0.5, rely=0.72, anchor="center")

        # Klick + Hover auf allen Teilflaechen, damit die ganze Kachel reagiert.
        for widget in (card, bg, icon_lbl, text_lbl):
            widget.bind("<Button-1>", lambda _e, c=command: c())
            widget.bind("<Enter>", lambda _e: bg.configure(image=self._grad_hover))
            widget.bind("<Leave>", lambda _e: bg.configure(image=self._grad))
