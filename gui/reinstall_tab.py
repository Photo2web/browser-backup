"""
reinstall_tab.py — "Neuinstallation"-Tab der BrowserBackup-GUI.

Listet alle installierten Programme als Checkliste (via `winget list`).
winget-faehige Programme sind automatisch installierbar, alle uebrigen als
"manuell" gekennzeichnet. Aus der Auswahl werden drei Dateien erzeugt:
Installationsanweisung.md, Install-Apps.ps1 und Apps.ubundle (siehe
core/installplan.py).

Das Laden erfolgt bewusst erst beim Oeffnen des Tabs (on_show), da
`winget list` eine Internetverbindung benoetigt.
"""

import queue
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.installed_apps import (
    InstalledApp,
    WinGetTimeout,
    WinGetUnavailable,
    list_installed_apps,
)
from core.installplan import write_install_plan

from .dialogs import show_error, show_info
from .worker import Worker

_INTERNET_HINWEIS = (
    "Hinweis: Das Auflisten und spaetere Installieren der Programme benoetigt "
    "eine Internetverbindung (winget laedt aus dem Netz)."
)

# Dezente Farbe fuer "manuell"-Zeilen (nicht automatisch installierbar).
_MANUAL_TEXT_COLOR = "gray60"


class ReinstallTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self.worker = Worker()
        self.items: list[tuple[InstalledApp, ctk.BooleanVar]] = []
        self._loaded = False

        self._build_ui()

    # -- UI-Aufbau -----------------------------------------------------

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x")
        ctk.CTkLabel(header, text="Zu uebernehmende Programme:").pack(side="left", padx=(0, 8))
        self.select_winget_btn = ctk.CTkButton(
            header, text="Alle winget-faehigen", width=150, command=self._select_installable
        )
        self.select_winget_btn.pack(side="left", padx=4)
        self.select_none_btn = ctk.CTkButton(
            header, text="Alle abwaehlen", width=120, command=self._select_none
        )
        self.select_none_btn.pack(side="left", padx=4)
        self.reload_btn = ctk.CTkButton(
            header, text="Aktualisieren", width=120, command=self._load_apps
        )
        self.reload_btn.pack(side="right", padx=4)

        ctk.CTkLabel(self, text=_INTERNET_HINWEIS, text_color="gray70", wraplength=800,
                     justify="left").pack(fill="x", pady=(2, 2))

        self.list_frame = ctk.CTkScrollableFrame(self, height=220)
        self.list_frame.pack(fill="both", expand=True, pady=(4, 12))
        self.status_label = ctk.CTkLabel(
            self.list_frame, text="Noch nicht geladen — bitte 'Aktualisieren' klicken.",
            text_color="gray70",
        )
        self.status_label.pack(anchor="w", padx=8, pady=8)

        form = ctk.CTkFrame(self)
        form.pack(fill="x", pady=(0, 12))
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="Zielordner:").grid(row=0, column=0, sticky="w", padx=12, pady=8)
        target_frame = ctk.CTkFrame(form, fg_color="transparent")
        target_frame.grid(row=0, column=1, sticky="ew", padx=12, pady=8)
        target_frame.grid_columnconfigure(0, weight=1)
        self.target_entry = ctk.CTkEntry(
            target_frame, placeholder_text="Zielordner fuer Anweisung, Skript und Bundle"
        )
        self.target_entry.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(target_frame, text="Durchsuchen ...", width=110,
                      command=self._choose_target_dir).grid(row=0, column=1, padx=(8, 0))

        self.create_button = ctk.CTkButton(self, text="Dateien erzeugen", command=self._on_create_clicked)
        self.create_button.pack(pady=(0, 12))

        self.log_box = ctk.CTkTextbox(self, height=140)
        self.log_box.configure(state="disabled")
        self.log_box.pack(fill="both", expand=False)

    # -- oeffentlich: vom Hauptfenster beim Umschalten aufgerufen --------

    def on_show(self):
        """Beim ersten Anzeigen des Tabs die Programme laden."""
        if not self._loaded and not self.worker.is_running():
            self._load_apps()

    # -- Laden ----------------------------------------------------------

    def _load_apps(self):
        if self.worker.is_running():
            return

        self._clear_checklist()
        self.status_label = ctk.CTkLabel(
            self.list_frame, text="Programme werden geladen (winget) ...", text_color="gray70"
        )
        self.status_label.pack(anchor="w", padx=8, pady=8)
        self._set_controls_enabled(False)
        self._log("Lade installierte Programme via winget ...")

        def run(_progress_callback):
            return list_installed_apps()

        self.worker.start(run)
        self.after(100, self._poll_load)

    def _poll_load(self):
        try:
            while True:
                item = self.worker.queue.get_nowait()
                kind = item[0]
                if kind == "done":
                    self._on_apps_loaded(item[1])
                    return
                if kind == "error":
                    self._on_load_error(item[1])
                    return
                # "progress" wird hier nicht genutzt.
        except queue.Empty:
            pass
        self.after(100, self._poll_load)

    def _on_apps_loaded(self, apps: list[InstalledApp]):
        self._loaded = True
        self._set_controls_enabled(True)
        self._clear_checklist()

        installable = [a for a in apps if a.winget_installable]
        manual = [a for a in apps if not a.winget_installable]

        for app in installable:
            self._add_row(app)
        for app in manual:
            self._add_row(app)

        self._log(
            f"{len(apps)} Programme gefunden "
            f"({len(installable)} winget-faehig, {len(manual)} manuell)."
        )
        if not apps:
            ctk.CTkLabel(self.list_frame, text="Keine Programme gefunden.",
                         text_color="gray70").pack(anchor="w", padx=8, pady=8)

    def _on_load_error(self, exc: Exception):
        self._set_controls_enabled(True)
        self._clear_checklist()
        if isinstance(exc, WinGetUnavailable):
            msg = ("winget wurde nicht gefunden. Der 'App-Installer' muss installiert "
                   "sein (Windows 10/11).")
        elif isinstance(exc, WinGetTimeout):
            msg = "winget hat zu lange gebraucht. Bitte 'Aktualisieren' erneut versuchen."
        else:
            msg = f"Programme konnten nicht geladen werden: {exc}"
        ctk.CTkLabel(self.list_frame, text=msg, text_color="gray70", wraplength=780,
                     justify="left").pack(anchor="w", padx=8, pady=8)
        self._log(f"FEHLER beim Laden: {exc}")

    def _add_row(self, app: InstalledApp):
        var = ctk.BooleanVar(value=False)
        if app.winget_installable:
            label = f"{app.name}   [{app.package_id}]   ({app.source})"
            checkbox = ctk.CTkCheckBox(self.list_frame, text=label, variable=var)
        else:
            label = f"{app.name}   (manuell — kein winget-Paket)"
            checkbox = ctk.CTkCheckBox(
                self.list_frame, text=label, variable=var, text_color=_MANUAL_TEXT_COLOR
            )
        checkbox.pack(anchor="w", padx=8, pady=1)
        self.items.append((app, var))

    # -- Hilfsfunktionen -------------------------------------------------

    def _clear_checklist(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        self.items = []

    def _select_installable(self):
        for app, var in self.items:
            var.set(app.winget_installable)

    def _select_none(self):
        for _, var in self.items:
            var.set(False)

    def _set_controls_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.select_winget_btn.configure(state=state)
        self.select_none_btn.configure(state=state)
        self.reload_btn.configure(state=state)
        self.create_button.configure(state=state)

    def _choose_target_dir(self):
        chosen = filedialog.askdirectory(parent=self)
        if chosen:
            self.target_entry.delete(0, "end")
            self.target_entry.insert(0, chosen)

    def _log(self, message: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # -- Dateien erzeugen -----------------------------------------------

    def _on_create_clicked(self):
        if self.worker.is_running():
            return

        selected = [app for app, var in self.items if var.get()]
        if not selected:
            show_error(self, "Keine Auswahl", "Bitte mindestens ein Programm auswaehlen.")
            return

        dest_text = self.target_entry.get().strip()
        if not dest_text:
            show_error(self, "Kein Zielordner", "Bitte einen Zielordner auswaehlen.")
            return
        dest_dir = Path(dest_text)

        try:
            result = write_install_plan(selected, dest_dir)
        except OSError as exc:
            self._log(f"FEHLER beim Schreiben: {exc}")
            show_error(self, "Fehler", f"Dateien konnten nicht geschrieben werden:\n{exc}")
            return

        self._log(
            f"Erzeugt: {result.installable_count} winget-faehig, "
            f"{result.manual_count} manuell -> {dest_dir}"
        )
        summary = (
            f"Dateien erzeugt in:\n{dest_dir}\n\n"
            f"- {result.instructions_path.name}  (lesbare Anleitung)\n"
            f"- {result.script_path.name}  (winget-Installationsskript, startet als Admin)\n"
            f"- {result.bundle_path.name}  (UniGetUI-Bundle)\n\n"
            f"Automatisch installierbar: {result.installable_count}\n"
            f"Manuell: {result.manual_count}\n\n"
            "Auf dem neuen Rechner: Install-Apps.ps1 rechtsklicken und "
            "'Mit PowerShell ausfuehren' — es fragt selbst nach Admin-Rechten. "
            "Internetverbindung noetig."
        )
        show_info(self, "Neuinstallation vorbereitet", summary)
