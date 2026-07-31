"""
uninstall_screen.py — "Software entfernen"-Karte der Umzugstool-GUI.

Listet alle installierten Programme (aus der Uninstall-Registry), gruppiert nach
Scope (nur dieser Benutzer / alle Benutzer), laesst sie ankreuzen und startet
nach einer Sammelbestaetigung ein separates Skript, das sie der Reihe nach
entfernt. Die Auswahl wird zugleich als Wiederherstell-Liste gespeichert, die im
Neuinstallation-Bereich zum Wiederholen bereitsteht.

Der Registry-Scan laeuft im Worker-Thread (Poll per after()), damit die GUI
nicht einfriert. Die eigentliche Deinstallation und die Registry-/Skript-Logik
liegen GUI-unabhaengig in core/.
"""

import queue

import customtkinter as ctk

from core.installed_programs import InstalledProgram, list_installed_programs
from core.removed_list import save_removed, store_dir
from core.uninstallplan import write_and_launch_uninstall

from .dialogs import ask_yes_no, show_error, show_info
from .worker import Worker

_HINT = ("Hinweis: Manche Programme werden still entfernt, andere oeffnen ihren "
         "eigenen Uninstaller zum Durchklicken. 'Alle Benutzer' erfordert "
         "Administrator-Rechte (Windows fragt per UAC nach).")
_GROUP_COLOR = "gray55"


class UninstallScreen(ctk.CTkFrame):
    def __init__(self, master, on_back=None):
        super().__init__(master, fg_color="transparent")
        self._on_back = on_back
        self.worker = Worker()
        self._loaded = False
        # (InstalledProgram, BooleanVar) je Programm.
        self.items: list[tuple[InstalledProgram, ctk.BooleanVar]] = []
        self._build_ui()

    # -- UI-Aufbau -----------------------------------------------------

    def _build_ui(self):
        # Unten fest angepinnt (immer sichtbar).
        self.log_box = ctk.CTkTextbox(self, height=70)
        self.log_box.configure(state="disabled")
        self.log_box.pack(side="bottom", fill="x", pady=(4, 0))

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.pack(side="bottom", pady=(6, 4))
        self.remove_button = ctk.CTkButton(
            button_row, text="Ausgewaehlte entfernen",
            command=self._on_remove_clicked, state="disabled")
        self.remove_button.pack(side="left", padx=6)

        # Oben: Zurueck + Titel.
        if self._on_back is not None:
            back_row = ctk.CTkFrame(self, fg_color="transparent")
            back_row.pack(side="top", fill="x", pady=(0, 4))
            ctk.CTkButton(back_row, text="‹ Zurueck", width=90,
                          command=self._on_back).pack(side="left")
            ctk.CTkLabel(back_row, text="Software entfernen",
                         font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=8)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(side="top", fill="x")
        ctk.CTkLabel(header, text="Installierte Programme:").pack(side="left", padx=(0, 8))
        self.select_all_btn = ctk.CTkButton(header, text="Alle auswaehlen", width=120,
                                             command=self._select_all, state="disabled")
        self.select_all_btn.pack(side="left", padx=4)
        self.select_none_btn = ctk.CTkButton(header, text="Alle abwaehlen", width=120,
                                              command=self._select_none, state="disabled")
        self.select_none_btn.pack(side="left", padx=4)
        self.reload_btn = ctk.CTkButton(header, text="Aktualisieren", width=120,
                                        command=self._load, state="disabled")
        self.reload_btn.pack(side="right", padx=4)

        ctk.CTkLabel(self, text=_HINT, text_color="gray70", wraplength=820,
                     justify="left").pack(side="top", fill="x", pady=(2, 2))

        self.list_frame = ctk.CTkScrollableFrame(self, height=320)
        self.list_frame.pack(side="top", fill="both", expand=True, pady=(4, 6))
        self.status_label = ctk.CTkLabel(
            self.list_frame, text="Programme werden beim Oeffnen geladen ...",
            text_color="gray70")
        self.status_label.pack(anchor="w", padx=8, pady=8)

    # -- vom Hauptfenster beim Umschalten aufgerufen --------------------

    def on_show(self):
        if not self._loaded and not self.worker.is_running():
            self._load()

    # -- Laden ----------------------------------------------------------

    def _load(self):
        if self.worker.is_running():
            return
        self._clear_list()
        self.status_label = ctk.CTkLabel(
            self.list_frame, text="Programme werden geladen (Registry) ...",
            text_color="gray70")
        self.status_label.pack(anchor="w", padx=8, pady=8)
        self._set_controls(False)
        self._log("Lade installierte Programme aus der Registry ...")

        def run(_progress_callback):
            return list_installed_programs()

        self.worker.start(run)
        self.after(100, self._poll_load)

    def _poll_load(self):
        try:
            while True:
                item = self.worker.queue.get_nowait()
                if item[0] == "done":
                    self._on_loaded(item[1])
                    return
                if item[0] == "error":
                    self._on_load_error(item[1])
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll_load)

    def _on_loaded(self, programs: list[InstalledProgram]):
        self._loaded = True
        self._set_controls(True)
        self._clear_list()
        if not programs:
            ctk.CTkLabel(self.list_frame, text="Keine Programme gefunden.",
                         text_color="gray70").pack(anchor="w", padx=8, pady=8)
            self.remove_button.configure(state="disabled")
            self._log("Keine Programme gefunden.")
            return
        user = [p for p in programs if p.scope == "user"]
        machine = [p for p in programs if p.scope == "machine"]
        self._add_group("Nur dieser Benutzer", user)
        self._add_group("Alle Benutzer (Administrator-Rechte noetig)", machine)
        self.remove_button.configure(state="normal")
        self._log(f"{len(programs)} Programme gefunden "
                  f"({len(user)} nur dieser Benutzer, {len(machine)} alle Benutzer).")

    def _add_group(self, title: str, programs: list[InstalledProgram]):
        if not programs:
            return
        ctk.CTkLabel(self.list_frame, text=title, text_color=_GROUP_COLOR,
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=8, pady=(8, 2))
        for program in programs:
            var = ctk.BooleanVar(value=False)
            parts = [program.name]
            if program.version:
                parts.append(program.version)
            if program.publisher:
                parts.append(f"({program.publisher})")
            ctk.CTkCheckBox(self.list_frame, text="   ".join(parts),
                            variable=var).pack(anchor="w", padx=20, pady=1)
            self.items.append((program, var))

    def _on_load_error(self, exc: Exception):
        self._set_controls(True)
        self._clear_list()
        ctk.CTkLabel(self.list_frame,
                     text=f"Programme konnten nicht geladen werden: {exc}",
                     text_color="gray70", wraplength=780,
                     justify="left").pack(anchor="w", padx=8, pady=8)
        self._log(f"FEHLER beim Laden: {exc}")

    # -- Hilfsfunktionen -------------------------------------------------

    def _clear_list(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        self.items = []

    def _select_all(self):
        for _p, var in self.items:
            var.set(True)

    def _select_none(self):
        for _p, var in self.items:
            var.set(False)

    def _set_controls(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for btn in (self.select_all_btn, self.select_none_btn, self.reload_btn):
            btn.configure(state=state)
        if not enabled:
            self.remove_button.configure(state="disabled")

    def _log(self, message: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # -- Entfernen ------------------------------------------------------

    def _on_remove_clicked(self):
        if self.worker.is_running():
            return
        selected = [p for p, var in self.items if var.get()]
        if not selected:
            show_error(self, "Keine Auswahl", "Bitte mindestens ein Programm ankreuzen.")
            return

        machine = [p for p in selected if p.scope == "machine"]
        preview = [f"- {p.name}" for p in selected[:25]]
        if len(selected) > 25:
            preview.append(f"... und {len(selected) - 25} weitere")
        admin_hint = ("\n\nDarunter Programme fuer ALLE Benutzer - dafuer fragt Windows "
                      "nach Administrator-Rechten (UAC).") if machine else ""
        confirm = ask_yes_no(
            self, "Wirklich entfernen?",
            f"Diese {len(selected)} Programme werden deinstalliert:\n\n"
            + "\n".join(preview) + admin_hint
            + "\n\nDer Fortschritt laeuft in einem separaten Fenster. Fortfahren?")
        if not confirm:
            return

        # Wiederherstell-Liste VOR dem Start sichern (Auswahl, nicht Erfolg).
        try:
            saved = save_removed(selected)
            self._log(f"Wiederherstell-Liste gespeichert: {saved}")
        except OSError as exc:
            self._log(f"Konnte Wiederherstell-Liste nicht speichern: {exc}")

        try:
            script = write_and_launch_uninstall(selected, store_dir())
        except OSError as exc:
            self._log(f"FEHLER beim Start: {exc}")
            show_error(self, "Fehler",
                       f"Deinstallation konnte nicht gestartet werden:\n{exc}")
            return

        self._log(f"Deinstallation gestartet: {script}")
        show_info(
            self, "Deinstallation gestartet",
            "Der Fortschritt erscheint in einem separaten Fenster. Bei Programmen "
            "fuer alle Benutzer bitte die Windows-Abfrage (UAC) bestaetigen.\n\n"
            "Die entfernten Programme stehen im Bereich 'Neuinstallation' unter "
            "'Zuletzt entfernte Programme' zum Wiederherstellen bereit.")
