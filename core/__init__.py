"""
Umzugstool — Kernlogik-Paket.

Enthaelt reine, GUI-unabhaengige Funktionen zur Browser-/Profil-Erkennung,
Sicherung und Wiederherstellung sowie (ab v1.1) zur Programm-Neuinstallation
(installed_apps + installplan). Wird von der customtkinter-GUI importiert und
aus einem Worker-Thread heraus aufgerufen. Siehe docs/PROJEKT.md.
"""

TOOL_VERSION = "1.4.0"  # v1.4.0: Software entfernen (Registry-Liste, deinstallieren, Wiederherstell-Liste)
