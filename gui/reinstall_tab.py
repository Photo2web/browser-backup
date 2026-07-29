"""
reinstall_tab.py — "Neuinstallation"-Tab der Umzugstool-GUI.

Zwei Quellen fuer die Auswahl:
1. **Grundausstattung** - eine kuratierte, feste Liste haeufig gebrauchter
   winget-Programme (core/essential_apps.py); auch ohne winget-Laden sichtbar.
2. **Installierte Programme** - via `winget list` geladen (Internet noetig),
   winget-faehig ankreuzbar, Rest als "manuell" gekennzeichnet.

Aus der (zusammengefuehrten) Auswahl erzeugt das Tool drei Dateien
(Installationsanweisung.md, Install-Apps.ps1, Apps.ubundle) und kann das
erzeugte Skript optional direkt starten ("Jetzt installieren").
"""

import queue
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.essential_apps import EssentialApp, essential_apps
from core.installed_apps import (
    InstalledApp,
    WinGetTimeout,
    WinGetUnavailable,
    list_installed_apps,
)
from core.installplan import launch_install_script, write_install_plan

from .dialogs import ask_yes_no, show_error, show_info
from .worker import Worker

_INTERNET_HINWEIS = (
    "Hinweis: Auflisten und Installieren der Programme benoetigt eine "
    "Internetverbindung (winget laedt aus dem Netz)."
)

_MANUAL_TEXT_COLOR = "gray60"
_CATEGORY_TEXT_COLOR = "gray55"


class ReinstallTab(ctk.CTkFrame):
    def __init__(self, master, on_back=None):
        super().__init__(master, fg_color="transparent")

        # Callback zurueck zum Startbildschirm (wie die anderen Modi einen
        # '‹ Zurueck'-Button haben). None -> kein Button (z.B. in Alt-Tests).
        self._on_back = on_back
        self.worker = Worker()
        # (InstalledApp, BooleanVar) je installiertem Programm.
        self.items: list[tuple[InstalledApp, ctk.BooleanVar]] = []
        # (EssentialApp, BooleanVar) je Grundausstattungs-Programm.
        self.essential_items: list[tuple[EssentialApp, ctk.BooleanVar]] = []
        self._loaded = False
        self._last_script_path: Path | None = None
        self._last_installable = 0

        self._build_ui()

    # -- UI-Aufbau -----------------------------------------------------

    def _build_ui(self):
        # === Unten fest angepinnt (immer sichtbar), damit die Buttons auch
        #     auf kleinen/hoch-skalierten Bildschirmen nicht abgeschnitten
        #     werden. Zuerst gepackt = am weitesten unten. ===
        self.log_box = ctk.CTkTextbox(self, height=70)
        self.log_box.configure(state="disabled")
        self.log_box.pack(side="bottom", fill="x", pady=(4, 0))

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.pack(side="bottom", pady=(6, 4))
        self.create_button = ctk.CTkButton(
            button_row, text="Dateien erzeugen", command=self._on_create_clicked
        )
        self.create_button.pack(side="left", padx=6)
        self.install_button = ctk.CTkButton(
            button_row, text="Jetzt installieren", command=self._on_install_clicked, state="disabled"
        )
        self.install_button.pack(side="left", padx=6)

        form = ctk.CTkFrame(self)
        form.pack(side="bottom", fill="x", pady=(4, 4))
        form.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(form, text="Zielordner:").grid(row=0, column=0, sticky="w", padx=12, pady=6)
        target_frame = ctk.CTkFrame(form, fg_color="transparent")
        target_frame.grid(row=0, column=1, sticky="ew", padx=12, pady=6)
        target_frame.grid_columnconfigure(0, weight=1)
        self.target_entry = ctk.CTkEntry(
            target_frame, placeholder_text="Zielordner fuer Anweisung, Skript und Bundle"
        )
        self.target_entry.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(target_frame, text="Durchsuchen ...", width=110,
                      command=self._choose_target_dir).grid(row=0, column=1, padx=(8, 0))

        # === Oben (fuellt den Rest): Grundausstattung + installierte Programme ===
        if self._on_back is not None:
            back_row = ctk.CTkFrame(self, fg_color="transparent")
            back_row.pack(side="top", fill="x", pady=(0, 4))
            ctk.CTkButton(back_row, text="‹ Zurueck", width=90, command=self._on_back).pack(side="left")
            ctk.CTkLabel(back_row, text="Neuinstallation",
                         font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=8)

        ess_header = ctk.CTkFrame(self, fg_color="transparent")
        ess_header.pack(side="top", fill="x")
        ctk.CTkLabel(
            ess_header, text="Grundausstattung (Standard-Programme fuer einen neuen PC):"
        ).pack(side="left", padx=(0, 8))
        self.essentials_select_btn = ctk.CTkButton(
            ess_header, text="Alle auswaehlen", width=120, command=self._select_all_essentials
        )
        self.essentials_select_btn.pack(side="left", padx=4)

        self.essentials_frame = ctk.CTkScrollableFrame(self, height=110)
        self.essentials_frame.pack(side="top", fill="x", pady=(4, 8))
        self._populate_essentials()

        inst_header = ctk.CTkFrame(self, fg_color="transparent")
        inst_header.pack(side="top", fill="x")
        ctk.CTkLabel(inst_header, text="Auf diesem PC installierte Programme:").pack(
            side="left", padx=(0, 8)
        )
        self.select_winget_btn = ctk.CTkButton(
            inst_header, text="Alle winget-faehigen", width=150, command=self._select_installable
        )
        self.select_winget_btn.pack(side="left", padx=4)
        self.select_none_btn = ctk.CTkButton(
            inst_header, text="Alle abwaehlen", width=120, command=self._select_none
        )
        self.select_none_btn.pack(side="left", padx=4)
        self.reload_btn = ctk.CTkButton(
            inst_header, text="Aktualisieren", width=120, command=self._load_apps
        )
        self.reload_btn.pack(side="right", padx=4)

        ctk.CTkLabel(self, text=_INTERNET_HINWEIS, text_color="gray70", wraplength=820,
                     justify="left").pack(side="top", fill="x", pady=(2, 2))

        self.list_frame = ctk.CTkScrollableFrame(self, height=120)
        self.list_frame.pack(side="top", fill="both", expand=True, pady=(4, 6))
        self.status_label = ctk.CTkLabel(
            self.list_frame, text="Noch nicht geladen — bitte 'Aktualisieren' klicken.",
            text_color="gray70",
        )
        self.status_label.pack(anchor="w", padx=8, pady=8)

    def _populate_essentials(self):
        last_category = None
        for essential in essential_apps():
            if essential.category != last_category:
                ctk.CTkLabel(
                    self.essentials_frame, text=essential.category, text_color=_CATEGORY_TEXT_COLOR
                ).pack(anchor="w", padx=8, pady=(6, 0))
                last_category = essential.category
            var = ctk.BooleanVar(value=False)
            ctk.CTkCheckBox(
                self.essentials_frame,
                text=f"{essential.name}   [{essential.package_id}]",
                variable=var,
            ).pack(anchor="w", padx=20, pady=1)
            self.essential_items.append((essential, var))

    # -- oeffentlich: vom Hauptfenster beim Umschalten aufgerufen --------

    def on_show(self):
        """Beim ersten Anzeigen des Tabs die installierten Programme laden."""
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
            f"{len(apps)} installierte Programme gefunden "
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
                   "sein (Windows 10/11). Die Grundausstattung kann trotzdem gewaehlt werden.")
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

    def _select_all_essentials(self):
        for _, var in self.essential_items:
            var.set(True)

    def _set_controls_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for btn in (self.select_winget_btn, self.select_none_btn, self.reload_btn,
                    self.create_button, self.essentials_select_btn):
            btn.configure(state=state)
        # "Jetzt installieren" nur, wenn ein Plan mit winget-faehigen Apps existiert.
        install_state = "normal" if (enabled and self._last_installable > 0) else "disabled"
        self.install_button.configure(state=install_state)

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

    def _gather_selected(self) -> list[InstalledApp]:
        """Auswahl aus installierten Programmen + Grundausstattung, nach
        package_id dedupliziert (installierte haben Vorrang)."""
        apps = [app for app, var in self.items if var.get()]
        seen = {a.package_id for a in apps if a.package_id}
        for essential, var in self.essential_items:
            if var.get():
                candidate = essential.to_installed_app()
                if candidate.package_id not in seen:
                    apps.append(candidate)
                    seen.add(candidate.package_id)
        return apps

    # -- Dateien erzeugen -----------------------------------------------

    def _on_create_clicked(self):
        if self.worker.is_running():
            return

        selected = self._gather_selected()
        if not selected:
            show_error(self, "Keine Auswahl",
                       "Bitte mindestens ein Programm (Grundausstattung oder installiert) auswaehlen.")
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

        # Plan merken -> "Jetzt installieren" freischalten (falls etwas installierbar).
        self._last_script_path = result.script_path
        self._last_installable = result.installable_count
        self.install_button.configure(
            state="normal" if result.installable_count > 0 else "disabled"
        )

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
            "Auf dem neuen Rechner: 'Jetzt installieren' klicken (installiert auf DIESEM "
            "Rechner) oder Install-Apps.ps1 dorthin kopieren und ausfuehren. "
            "Internetverbindung noetig."
        )
        show_info(self, "Neuinstallation vorbereitet", summary)

    # -- Direkt installieren --------------------------------------------

    def _on_install_clicked(self):
        if self._last_script_path is None or not Path(self._last_script_path).is_file():
            show_error(self, "Kein Skript", "Bitte zuerst 'Dateien erzeugen'.")
            return

        confirm = ask_yes_no(
            self,
            "Installation starten?",
            f"Es werden {self._last_installable} Programm(e) auf DIESEM Rechner installiert.\n\n"
            "Erfordert Administrator-Rechte (UAC-Abfrage) und eine Internetverbindung.\n"
            "Der Fortschritt erscheint in einem separaten PowerShell-Fenster.\n\n"
            "Fortfahren?",
        )
        if not confirm:
            return

        try:
            launch_install_script(self._last_script_path)
        except OSError as exc:
            self._log(f"FEHLER beim Start: {exc}")
            show_error(self, "Fehler", f"Installation konnte nicht gestartet werden:\n{exc}")
            return

        self._log("Installation gestartet (siehe PowerShell-Fenster).")
        show_info(
            self,
            "Installation gestartet",
            "Das PowerShell-Fenster fragt nach Administrator-Rechten (UAC) und zeigt "
            "den Fortschritt. Dieses Fenster kannst du offen lassen.",
        )
