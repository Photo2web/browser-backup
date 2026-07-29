"""Wiederverwendbarer Fortschrittsbalken mit Prozentzahl und rot->gruen-Farbe.

Die Fuellfarbe wandert fortschrittsabhaengig von Rot (0 %) ueber Gelb (~50 %)
nach Gruen (100 %). Ein zentriertes Label zeigt die Prozentzahl.
"""

import colorsys

import customtkinter as ctk


def color_for_fraction(frac: float) -> str:
    """#rrggbb fuer den Fortschritt frac (0..1): Hue 0deg(rot)->120deg(gruen)."""
    frac = max(0.0, min(1.0, frac))
    hue = (120.0 * frac) / 360.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.9, 0.85)
    return f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"


class ColorProgressBar(ctk.CTkFrame):
    """CTkProgressBar mit ueberlagerter Prozentzahl und wandernder Farbe."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        # Feste, ausreichende Hoehe: der Balken bestimmt die Rahmenhoehe, und
        # das mittig platzierte Prozentlabel (11px, fett) braucht Platz, sonst
        # wird die Zahl oben/unten abgeschnitten.
        self._bar = ctk.CTkProgressBar(self, height=24)
        self._bar.set(0)
        self._bar.pack(fill="x", expand=True)
        # Prozentlabel mittig ueber dem Balken.
        self._label = ctk.CTkLabel(self, text="0 %", font=ctk.CTkFont(size=11, weight="bold"))
        self._label.place(relx=0.5, rely=0.5, anchor="center")
        self.reset()

    def set_fraction(self, frac: float) -> None:
        frac = max(0.0, min(1.0, frac))
        self._bar.set(frac)
        self._bar.configure(progress_color=color_for_fraction(frac))
        self._label.configure(text=f"{round(frac * 100)} %")

    def reset(self) -> None:
        self.set_fraction(0.0)
