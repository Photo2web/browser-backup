"""theme.py — zentrales Lila-Glas-Farbschema fuer Umzugstool.

Passt das customtkinter-Standardtheme EINMALIG beim App-Start an (vor dem
Erzeugen der Widgets), damit ALLE Elemente - Buttons, Checkboxen,
Fortschrittsbalken, Scrollbalken, Menues, Dialoge - im selben dezenten
Lila-Ton erscheinen statt im Standard-Blau. Die Palette ist an den
Startbildschirm-Hintergrund (home_icons.home_background) angelehnt, damit alles
harmonisch wirkt.

Zentrale Anlaufstelle: Farbe hier aendern -> wirkt in der ganzen App.
"""

import customtkinter as ctk

# -- Farbpalette (dunkles Lila, an die Startbildschirm-Kacheln angelehnt) ----
WINDOW_BG = "#140c22"      # sehr dunkles Lila (Fensterhintergrund/Rand)
PANEL_BG = "#211735"       # Glas-Panel (etwas heller als das Fenster)
PANEL_BORDER = "#3a2a5c"   # dezente Glaskante
ACCENT = "#6d4bc9"         # Akzent (Buttons, Auswahl, Fortschritt)
ACCENT_HOVER = "#5a3cae"   # Akzent beim Ueberfahren
ACCENT_LIGHT = "#8c68dc"   # heller Akzent (Raender, Kontrast)
CHECK_MARK = "#f2ecfb"     # fast weiss (Haken, Schalterknauf)
TEXT_MUTED = "#9c8fc4"     # gedaempfter Lila-Grauton (Branding, Fusszeile)
CORNER = 16                # Eckenradius fuer das Content-Panel


def apply_purple_theme() -> None:
    """Setzt Dark-Mode + kompakte Skalierung und faerbt das Theme lila um.
    Muss VOR dem Erstellen von Widgets laufen (customtkinter liest die Farben
    beim Anlegen jedes Widgets aus ThemeManager.theme)."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")   # Basis - Akzente werden unten ersetzt
    ctk.set_widget_scaling(0.8)           # kompaktere Schrift/Widgets

    theme = ctk.ThemeManager.theme

    def both(color: str) -> list:
        """Gleiche Farbe fuer Hell-/Dunkel-Modus (App ist auf Dark fixiert)."""
        return [color, color]

    def override(widget: str, **colors) -> None:
        """Setzt nur Farbschluessel, die im geladenen Theme wirklich existieren
        (robust gegen customtkinter-Versionsunterschiede)."""
        section = theme.get(widget)
        if not section:
            return
        for key, value in colors.items():
            if key in section:
                section[key] = value

    override("CTk", fg_color=both(WINDOW_BG))
    override("CTkToplevel", fg_color=both(WINDOW_BG))
    override("CTkFrame", fg_color=both(PANEL_BG), top_fg_color=both(PANEL_BG),
             border_color=both(PANEL_BORDER))
    override("CTkButton", fg_color=both(ACCENT), hover_color=both(ACCENT_HOVER),
             border_color=both(ACCENT_LIGHT))
    override("CTkCheckBox", fg_color=both(ACCENT), hover_color=both(ACCENT_HOVER),
             checkmark_color=both(CHECK_MARK), border_color=both(ACCENT_LIGHT))
    override("CTkProgressBar", progress_color=both(ACCENT))
    override("CTkSlider", button_color=both(ACCENT),
             button_hover_color=both(ACCENT_HOVER), progress_color=both(ACCENT))
    override("CTkSwitch", progress_color=both(ACCENT),
             button_color=both(CHECK_MARK), button_hover_color=both("#e7ddf7"))
    override("CTkEntry", border_color=both(PANEL_BORDER))
    override("CTkOptionMenu", fg_color=both(ACCENT), button_color=both(ACCENT_HOVER),
             button_hover_color=both(ACCENT_HOVER))
    override("CTkComboBox", border_color=both(PANEL_BORDER), button_color=both(ACCENT),
             button_hover_color=both(ACCENT_HOVER))
    override("CTkSegmentedButton", selected_color=both(ACCENT),
             selected_hover_color=both(ACCENT_HOVER), unselected_color=both(PANEL_BG),
             unselected_hover_color=both(PANEL_BORDER))
    override("CTkScrollbar", button_color=both(PANEL_BORDER),
             button_hover_color=both(ACCENT))
    override("DropdownMenu", fg_color=both(PANEL_BG), hover_color=both(ACCENT))
