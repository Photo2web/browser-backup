"""
Umzugstool — Kernlogik-Paket.

Enthält reine, GUI-unabhängige Funktionen zur Browser-/Profil-Erkennung,
Sicherung und Wiederherstellung sowie (ab v1.1) zur Programm-Neuinstallation
(installed_apps + installplan). Wird von der customtkinter-GUI importiert und
aus einem Worker-Thread heraus aufgerufen. Siehe docs/PROJEKT.md.
"""

TOOL_VERSION = "1.4.5"  # v1.4.5: Echte Umlaute, adaptive Skalierung (4K), Neuinstallation als Tabelle, Kachelecken-Fix, AnyDesk
