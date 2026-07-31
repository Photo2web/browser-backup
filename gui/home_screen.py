"""Startbildschirm: kreativer Lila-Hintergrund (Radialverlauf + leuchtende
Blobs) mit vier gleich großen, edlen Lila-Kacheln im 2x2-Raster.

Der Hintergrund wird als Bild gerendert (home_icons.home_background) und liegt
in einem einfachen tk.Label hinter den Kacheln - so bleibt er von der CTk-
Skalierung unberührt und füllt exakt das Fenster. Die Kacheln sind einzelne,
klickbare Bild-Labels (opak), die sauber darauf sitzen. Beide werden bei
Größenänderung neu ausgelegt."""

import tkinter as tk

import customtkinter as ctk
from PIL import ImageTk

from .home_icons import ctk_card, home_background

_CARDS = [
    ("save", "Sichern", "Browser & persönliche Daten", "on_backup"),
    ("restore", "Wiederherstellen", "Gesicherte Daten zurückspielen", "on_restore"),
    ("reinstall", "Neuinstallation", "Programme neu aufsetzen", "on_reinstall"),
    ("remove", "Software entfernen", "Programme deinstallieren", "on_uninstall"),
]

# Einheitliche Kachelgröße (alle Kacheln exakt gleich).
_CARD_W, _CARD_H = 235, 172
_TITLE = "Was möchtest du tun?"
# Relative Kachel-Mittelpunkte (2x2), skalierungsunabhängig.
_CARD_POS = [(0.30, 0.44), (0.70, 0.44), (0.30, 0.75), (0.70, 0.75)]
_FALLBACK_BG = "#140c22"   # bis das erste Hintergrundbild gerendert ist
# Füllfarbe der Kachel-Labels: passt zum Lila-Hintergrund an den Kachel-
# positionen (Mittelwert ~#462373), damit die runden Kachelecken NICHT schwarz
# wirken, sondern im Hintergrund untergehen. (Ein CTk-"transparentes" Label
# zeigt die dunkle Fensterfarbe, nicht das dahinterliegende Hintergrundbild.)
_CARD_FILL = "#42236f"


class HomeScreen(ctk.CTkFrame):
    def __init__(self, master, on_backup, on_restore, on_reinstall, on_uninstall):
        super().__init__(master, fg_color=_FALLBACK_BG)
        self._commands = {"on_backup": on_backup, "on_restore": on_restore,
                          "on_reinstall": on_reinstall, "on_uninstall": on_uninstall}
        self._images = []          # (normal, hover) CTkImage-Referenzen halten
        self._bg_photo = None      # ImageTk-Referenz halten (sonst Garbage-Collect)
        self._bg_size = (0, 0)
        self._resize_job = None
        self._build()

    def _build(self):
        # Hintergrund als einfaches tk.Label (nicht CTk -> keine Skalierung).
        self._bg_label = tk.Label(self, bd=0, highlightthickness=0, bg=_FALLBACK_BG)
        self._bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        for (kind, title, subtitle, cmd_key), (relx, rely) in zip(_CARDS, _CARD_POS):
            self._make_card(kind, title, subtitle, self._commands[cmd_key], relx, rely)

        self.bind("<Configure>", self._on_resize)

    def _make_card(self, kind, title, subtitle, command, relx, rely):
        normal = ctk_card(_CARD_W, _CARD_H, kind, title, subtitle)
        hover = ctk_card(_CARD_W, _CARD_H, kind, title, subtitle, hover=True)
        self._images.append((normal, hover))

        label = ctk.CTkLabel(self, text="", image=normal, fg_color=_CARD_FILL)
        label.place(relx=relx, rely=rely, anchor="center")
        # Explizit über das Hintergrund-Label heben (Stapelreihenfolge sichern).
        label.lift(self._bg_label)
        label.bind("<Button-1>", lambda _e, c=command: c())
        label.bind("<Enter>", lambda _e, lbl=label, h=hover: lbl.configure(image=h))
        label.bind("<Leave>", lambda _e, lbl=label, n=normal: lbl.configure(image=n))

    # -- Hintergrund bei Größenänderung neu rendern (entprellt) --------

    def _on_resize(self, event):
        size = (event.width, event.height)
        if event.width < 40 or event.height < 40 or size == self._bg_size:
            return
        self._pending_size = size
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(60, self._render_bg)

    def _render_bg(self):
        self._resize_job = None
        width, height = self._pending_size
        self._bg_size = (width, height)
        image = home_background(width, height, title=_TITLE)
        self._bg_photo = ImageTk.PhotoImage(image)
        self._bg_label.configure(image=self._bg_photo)
        # NICHT .lower() aufrufen: das würde das Label unter die interne
        # Zeichenfläche des CTkFrame schieben und damit unsichtbar machen. Die
        # Kacheln liegen über dem Label, weil sie danach erzeugt+gehoben werden.
