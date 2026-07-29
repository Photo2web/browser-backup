"""
personal_tab.py — Tab "Persoenliche Daten".

Sichert/stellt die persoenlichen Windows-Ordner (Dokumente, Bilder, Musik,
Videos, Desktop, Downloads) wieder her — wahlweise als ZIP oder 1:1-Kopie,
mit Speicherplatz-Pruefung und Fortschrittsbalken. Intern per SegmentedButton
zwischen "Sichern" und "Wiederherstellen" umschaltbar. Lange Laeufe laufen im
Worker-Thread (Poll per after()), damit die GUI nicht einfriert.
"""

import queue
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.personal_data import (
    PersonalFolder,
    _format_bytes,
    backup_personal_folder,
    detect_personal_folders,
    folder_size,
    free_space,
    read_backup_manifest,
    restore_personal_folder,
)

from .dialogs import ask_conflict_mode, show_error, show_info
from .worker import Worker

_MODE_HINT = ("Hinweis: Fotos/Musik/Videos sind schon komprimiert - eine "
             "1:1-Kopie ist dort meist schneller als ZIP.")


class PersonalDataTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.worker = Worker()
        self.folders: list[PersonalFolder] = detect_personal_folders()
        # (PersonalFolder, BooleanVar, size_label) je Ordner
        self.backup_items: list[tuple[PersonalFolder, ctk.BooleanVar, ctk.CTkLabel]] = []
        self.mode_var = ctk.StringVar(value="zip")
        self._sizes: dict[str, int] = {}
        self._sizes_loaded = False
        # Restore: Liste (manifest, source_path, target_var-Entry)
        self.restore_rows: list[tuple[dict, Path, ctk.CTkEntry]] = []
        self._build_ui()

    # -- UI -------------------------------------------------------------

    def _build_ui(self):
        # Unten fest: Fortschrittsbalken + Log (immer sichtbar).
        self.log_box = ctk.CTkTextbox(self, height=90)
        self.log_box.configure(state="disabled")
        self.log_box.pack(side="bottom", fill="x", pady=(4, 0))
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.set(0)
        self.progress_bar.pack(side="bottom", fill="x", pady=(4, 4))

        # Umschaltung Sichern | Wiederherstellen.
        self.inner_switch = ctk.CTkSegmentedButton(
            self, values=["Sichern", "Wiederherstellen"], command=self._switch_view
        )
        self.inner_switch.set("Sichern")
        self.inner_switch.pack(side="top", fill="x", pady=(0, 8))

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(side="top", fill="both", expand=True)

        self._build_backup_view()
        self._build_restore_view()
        self.backup_view.pack(fill="both", expand=True)

    def _build_backup_view(self):
        self.backup_view = ctk.CTkFrame(self.body, fg_color="transparent")

        header = ctk.CTkFrame(self.backup_view, fg_color="transparent")
        header.pack(fill="x")
        ctk.CTkLabel(header, text="Zu sichernde Ordner:").pack(side="left", padx=(0, 8))
        ctk.CTkButton(header, text="Alle auswaehlen", width=120,
                      command=self._select_all_backup).pack(side="left", padx=4)

        self.backup_list = ctk.CTkScrollableFrame(self.backup_view, height=170)
        self.backup_list.pack(fill="x", pady=(4, 8))
        for folder in self.folders:
            row = ctk.CTkFrame(self.backup_list, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=1)
            var = ctk.BooleanVar(value=False)
            state = "normal" if folder.exists else "disabled"
            text = folder.display_name if folder.exists else f"{folder.display_name} (nicht vorhanden)"
            ctk.CTkCheckBox(row, text=text, variable=var, state=state).pack(side="left")
            size_label = ctk.CTkLabel(row, text="", text_color="gray70")
            size_label.pack(side="right")
            self.backup_items.append((folder, var, size_label))

        mode_frame = ctk.CTkFrame(self.backup_view, fg_color="transparent")
        mode_frame.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(mode_frame, text="Format:").pack(side="left", padx=(0, 8))
        ctk.CTkRadioButton(mode_frame, text="ZIP", variable=self.mode_var,
                           value="zip").pack(side="left", padx=6)
        ctk.CTkRadioButton(mode_frame, text="Kopie", variable=self.mode_var,
                           value="copy").pack(side="left", padx=6)
        ctk.CTkLabel(self.backup_view, text=_MODE_HINT, text_color="gray70",
                     wraplength=820, justify="left").pack(fill="x", pady=(0, 4))

        target_frame = ctk.CTkFrame(self.backup_view, fg_color="transparent")
        target_frame.pack(fill="x", pady=(0, 4))
        target_frame.grid_columnconfigure(0, weight=1)
        self.backup_target = ctk.CTkEntry(target_frame, placeholder_text="Zielordner fuer die Sicherung")
        self.backup_target.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(target_frame, text="Durchsuchen ...", width=110,
                      command=lambda: self._choose_dir(self.backup_target)).grid(row=0, column=1, padx=(8, 0))

        self.totals_label = ctk.CTkLabel(self.backup_view, text="Groessen werden geladen ...",
                                         text_color="gray70")
        self.totals_label.pack(fill="x", pady=(2, 4))
        self.backup_button = ctk.CTkButton(self.backup_view, text="Sichern",
                                           command=self._on_backup_clicked)
        self.backup_button.pack(pady=(0, 4))

    def _build_restore_view(self):
        self.restore_view = ctk.CTkFrame(self.body, fg_color="transparent")

        btns = ctk.CTkFrame(self.restore_view, fg_color="transparent")
        btns.pack(fill="x")
        ctk.CTkButton(btns, text="Backup-ZIP(s) waehlen ...", command=self._choose_restore_zips).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Kopie-Ordner waehlen ...", command=self._choose_restore_copy).pack(side="left", padx=4)

        self.restore_list = ctk.CTkScrollableFrame(self.restore_view, height=200)
        self.restore_list.pack(fill="both", expand=True, pady=(6, 6))
        self.restore_hint = ctk.CTkLabel(self.restore_list,
                                         text="Noch kein Backup gewaehlt.", text_color="gray70")
        self.restore_hint.pack(anchor="w", padx=8, pady=8)

        self.restore_button = ctk.CTkButton(self.restore_view, text="Wiederherstellen",
                                            command=self._on_restore_clicked)
        self.restore_button.pack(pady=(0, 4))

    # -- Umschaltung / on_show -----------------------------------------

    def _switch_view(self, value: str):
        self.backup_view.pack_forget()
        self.restore_view.pack_forget()
        if value == "Sichern":
            self.backup_view.pack(fill="both", expand=True)
        else:
            self.restore_view.pack(fill="both", expand=True)

    def on_show(self):
        """Beim Anzeigen des Tabs die Ordnergroessen einmal im Hintergrund laden."""
        if not self._sizes_loaded and not self.worker.is_running():
            self._load_sizes()

    # -- Groessen laden -------------------------------------------------

    def _load_sizes(self):
        self.backup_button.configure(state="disabled", text="Groessen werden ermittelt ...")
        existing = [f for f, _v, _l in self.backup_items if f.exists]

        def run(_progress):
            return {f.key: folder_size(f.path).total_bytes for f in existing}

        self.worker.start(run)
        self.after(120, self._poll_sizes)

    def _poll_sizes(self):
        try:
            while True:
                item = self.worker.queue.get_nowait()
                if item[0] == "done":
                    self._on_sizes_loaded(item[1])
                    return
                if item[0] == "error":
                    self.backup_button.configure(state="normal", text="Sichern")
                    self._log(f"Groessen konnten nicht geladen werden: {item[1]}")
                    show_error(self, "Groessen nicht ermittelbar",
                              f"Die Ordnergroessen konnten nicht bestimmt werden:\n{item[1]}\n\n"
                              "Tab schliessen und erneut oeffnen, um es noch einmal zu versuchen.")
                    return
        except queue.Empty:
            pass
        self.after(120, self._poll_sizes)

    def _on_sizes_loaded(self, sizes: dict):
        self._sizes = sizes
        self._sizes_loaded = True
        for folder, _var, label in self.backup_items:
            if folder.key in sizes:
                label.configure(text=_format_bytes(sizes[folder.key]))
        self._update_totals()
        self.backup_button.configure(state="normal", text="Sichern")

    def _update_totals(self):
        total = sum(self._sizes.get(f.key, 0) for f, v, _l in self.backup_items if v.get())
        self.totals_label.configure(text=f"Auswahl gesamt: {_format_bytes(total)}")

    # -- Sichern --------------------------------------------------------

    def _gather_backup_selection(self) -> list[PersonalFolder]:
        return [f for f, v, _l in self.backup_items if v.get() and f.exists]

    def _select_all_backup(self):
        for f, v, _l in self.backup_items:
            if f.exists:
                v.set(True)
        self._update_totals()

    def _on_backup_clicked(self):
        if self.worker.is_running():
            return
        selected = self._gather_backup_selection()
        if not selected:
            show_error(self, "Keine Auswahl", "Bitte mindestens einen vorhandenen Ordner auswaehlen.")
            return
        dest_text = self.backup_target.get().strip()
        if not dest_text:
            show_error(self, "Kein Zielordner", "Bitte einen Zielordner auswaehlen.")
            return
        dest = Path(dest_text)

        if not self._sizes_loaded:
            show_error(self, "Bitte kurz warten",
                       "Die Ordnergroessen werden noch ermittelt. Bitte einen Moment warten "
                       "und erneut auf 'Sichern' klicken.")
            return

        needed = sum(self._sizes.get(f.key, 0) for f in selected)
        try:
            free = free_space(dest)
        except OSError as exc:
            show_error(self, "Zielordner", f"Zielordner nicht nutzbar:\n{exc}")
            return
        if needed > free:
            show_error(self, "Zu wenig Speicherplatz",
                       f"Benoetigt (max.): {_format_bytes(needed)}\n"
                       f"Frei am Ziel: {_format_bytes(free)}\n\n"
                       "Bitte Ziel mit mehr Platz waehlen oder weniger Ordner auswaehlen.")
            return

        mode = self.mode_var.get()
        self.backup_button.configure(state="disabled", text="Sicherung laeuft ...")
        self.progress_bar.set(0)
        self._log(f"Sichere {len(selected)} Ordner ({mode}) ...")
        total_items = len(selected)

        def run(progress_callback):
            results = []
            for index, folder in enumerate(selected, start=1):
                def cb(c, t, m, _f=folder, _i=index):
                    progress_callback(c, t, f"[{_i}/{total_items}] {_f.display_name}: {m}")
                results.append(backup_personal_folder(folder, dest, mode=mode, progress_callback=cb))
            return results

        self.worker.start(run)
        self.after(100, lambda: self._poll_run(self._on_backup_done))

    def _on_backup_done(self, results):
        self.progress_bar.set(1)
        self.backup_button.configure(state="normal", text="Sichern")
        total_files = sum(r.file_count for r in results)
        total_skipped = sum(len(r.skipped) for r in results)
        self._log(f"Fertig. {len(results)} Ordner gesichert, {total_files} Dateien.")
        lines = [f"{len(results)} Ordner gesichert.", f"Dateien insgesamt: {total_files}"]
        if total_skipped:
            lines.append(f"Uebersprungene (gesperrte) Dateien: {total_skipped}")
        lines.append(f"Zielordner: {results[0].target.parent}")
        show_info(self, "Sicherung abgeschlossen", "\n".join(lines))

    # -- Wiederherstellen ----------------------------------------------

    def _choose_restore_zips(self):
        paths = filedialog.askopenfilenames(parent=self, title="Backup-ZIP(s) waehlen",
                                            filetypes=[("ZIP", "*.zip")])
        self._load_restore_sources([Path(p) for p in paths])

    def _choose_restore_copy(self):
        chosen = filedialog.askdirectory(parent=self, title="Kopie-Ordner waehlen")
        if chosen:
            self._load_restore_sources([Path(chosen)])

    def _load_restore_sources(self, sources: list[Path]):
        if not sources:
            return
        for child in self.restore_list.winfo_children():
            child.destroy()
        self.restore_rows = []
        by_key = {f.key: f for f in self.folders}
        for source in sources:
            try:
                manifest = read_backup_manifest(source)
            except (OSError, KeyError, ValueError) as exc:
                self._log(f"Kein gueltiges Backup: {source.name} ({exc})")
                continue
            row = ctk.CTkFrame(self.restore_list, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=2)
            name = manifest.get("folder_display_name", manifest.get("folder_key", "?"))
            ctk.CTkLabel(row, text=f"{name}  <-  {source.name}").pack(side="left", padx=(4, 8))
            target_entry = ctk.CTkEntry(row, width=280)
            default = by_key.get(manifest.get("folder_key", ""))
            target_entry.insert(0, str(default.path) if default else "")
            target_entry.pack(side="left", padx=4)
            ctk.CTkButton(row, text="Anderen Ordner ...", width=130,
                          command=lambda e=target_entry: self._choose_dir(e)).pack(side="left", padx=4)
            self.restore_rows.append((manifest, source, target_entry))
        if not self.restore_rows:
            ctk.CTkLabel(self.restore_list, text="Keine gueltigen Backups gefunden.",
                         text_color="gray70").pack(anchor="w", padx=8, pady=8)

    def _on_restore_clicked(self):
        if self.worker.is_running():
            show_info(self, "Bitte warten", "Es laeuft gerade ein anderer Vorgang.")
            return
        if not self.restore_rows:
            show_error(self, "Kein Backup", "Bitte zuerst ein Backup waehlen.")
            return

        jobs = []
        needed_per_drive: dict[str, int] = {}
        for manifest, source, entry in self.restore_rows:
            target = entry.get().strip()
            if not target:
                show_error(self, "Kein Ziel", f"Bitte Zielordner fuer {source.name} angeben.")
                return
            target_path = Path(target)
            jobs.append((source, target_path))
            drive = target_path.anchor or str(target_path)
            needed_per_drive[drive] = needed_per_drive.get(drive, 0) + int(manifest.get("total_bytes", 0))

        # Speicherplatz am Ziel pruefen (Spec §5/§6). total_bytes im Manifest ist
        # die tatsaechlich gesicherte Rohgroesse -> konservative Obergrenze fuer den Restore.
        for drive, needed in needed_per_drive.items():
            try:
                free = free_space(drive)
            except OSError:
                continue
            if needed > free:
                show_error(self, "Zu wenig Speicherplatz",
                           f"Ziel-Laufwerk {drive}\n"
                           f"Benoetigt (max.): {_format_bytes(needed)}\n"
                           f"Frei: {_format_bytes(free)}\n\n"
                           "Bitte Platz schaffen oder weniger Backups auswaehlen.")
                return

        conflict = ask_conflict_mode(self)
        if conflict == "abbrechen":
            return

        self.restore_button.configure(state="disabled", text="Laeuft ...")
        self.progress_bar.set(0)
        self._log(f"Stelle {len(jobs)} Ordner wieder her (Konflikt: {conflict}) ...")
        total_items = len(jobs)

        def run(progress_callback):
            results = []
            for index, (source, target) in enumerate(jobs, start=1):
                def cb(c, t, m, _s=source, _i=index):
                    progress_callback(c, t, f"[{_i}/{total_items}] {_s.name}: {m}")
                results.append(restore_personal_folder(source, target, conflict=conflict, progress_callback=cb))
            return results

        self.worker.start(run)
        self.after(100, lambda: self._poll_run(self._on_restore_done))

    def _on_restore_done(self, results):
        self.progress_bar.set(1)
        self.restore_button.configure(state="normal", text="Wiederherstellen")
        restored = sum(r.restored for r in results)
        overwritten = sum(r.overwritten for r in results)
        skipped = sum(r.skipped_existing for r in results)
        errors = sum(len(r.errors) for r in results)
        self._log(f"Fertig. {restored} neu, {overwritten} ueberschrieben, {skipped} uebersprungen.")
        lines = [f"Ordner: {len(results)}", f"Neu geschrieben: {restored}",
                 f"Ueberschrieben: {overwritten}", f"Uebersprungen: {skipped}"]
        if errors:
            lines.append(f"Fehler: {errors}")
        show_info(self, "Wiederherstellung abgeschlossen", "\n".join(lines))

    # -- gemeinsame Helfer ---------------------------------------------

    def _poll_run(self, on_done):
        try:
            while True:
                item = self.worker.queue.get_nowait()
                kind = item[0]
                if kind == "progress":
                    _, current, total, message = item
                    if total:
                        self.progress_bar.set(current / total)
                    self._log(message)
                elif kind == "done":
                    on_done(item[1])
                    return
                elif kind == "error":
                    self._on_run_error(item[1])
                    return
        except queue.Empty:
            pass
        self.after(100, lambda: self._poll_run(on_done))

    def _on_run_error(self, exc: Exception):
        self.progress_bar.set(0)
        self.backup_button.configure(state="normal", text="Sichern")
        self.restore_button.configure(state="normal", text="Wiederherstellen")
        self._log(f"FEHLER: {exc}")
        show_error(self, "Fehler", str(exc))

    def _choose_dir(self, entry: ctk.CTkEntry):
        chosen = filedialog.askdirectory(parent=self)
        if chosen:
            entry.delete(0, "end")
            entry.insert(0, chosen)

    def _log(self, message: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
