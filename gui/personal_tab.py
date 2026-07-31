"""
personal_tab.py — Persoenliche Daten: Sichern-/Restore-Frames.

Sichert/stellt die persoenlichen Windows-Ordner (Dokumente, Bilder, Musik,
Videos, Desktop, Downloads) wieder her — wahlweise als ZIP oder 1:1-Kopie,
mit Speicherplatz-Pruefung und Fortschrittsbalken. `PersonalBackupFrame`
(Sichern) und `PersonalRestoreFrame` (Wiederherstellen) sind eigenstaendige
Frames fuer je einen Modus-Container; sie teilen sich die Worker-Poll-/Log-/
Balken-Logik ueber die Basisklasse `_RunFrame`. Lange Laeufe laufen im
Worker-Thread (Poll per after()), damit die GUI nicht einfriert.
"""

import queue
import zipfile
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.personal_data import (
    PersonalFolder,
    _format_bytes,
    backup_personal_folder,
    cluster_size,
    detect_personal_folders,
    disk_reservation,
    find_personal_backups,
    folder_size,
    free_space,
    read_backup_manifest,
    restore_personal_folder,
)

# Kleine Restmarge auf die (bereits konservative) Cluster-Schaetzung, damit
# auch Dateisystem-Metadaten/Verzeichniseintraege noch Luft haben.
_SPACE_SAFETY = 1.02

from .dialogs import ask_conflict_mode, show_error, show_info
from .progress import ColorProgressBar
from .worker import Worker

_MODE_HINT = ("Hinweis: Fotos/Musik/Videos sind schon komprimiert - eine "
             "1:1-Kopie ist dort meist schneller als ZIP.")


class _RunFrame(ctk.CTkFrame):
    """Basis fuer die beiden Personal-Frames: Worker-Poll, Log, Balken."""

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.worker = Worker()
        self.log_box = ctk.CTkTextbox(self, height=90)
        self.log_box.configure(state="disabled")
        self.log_box.pack(side="bottom", fill="x", pady=(4, 0))
        self.progress_bar = ColorProgressBar(self)
        self.progress_bar.pack(side="bottom", fill="x", pady=(4, 4))

    def _log(self, message: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _poll_run(self, on_done):
        try:
            while True:
                item = self.worker.queue.get_nowait()
                kind = item[0]
                if kind == "progress":
                    _, current, total, message = item
                    if total:
                        self.progress_bar.set_fraction(current / total)
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
        self.progress_bar.reset()
        self._log(f"FEHLER: {exc}")
        show_error(self, "Fehler", str(exc))

    def _choose_dir(self, entry: ctk.CTkEntry):
        chosen = filedialog.askdirectory(parent=self)
        if chosen:
            entry.delete(0, "end")
            entry.insert(0, chosen)


class PersonalBackupFrame(_RunFrame):
    """Modus "Sichern": Persoenliche Ordner in den Umzugsordner sichern."""

    def __init__(self, master, dir_provider):
        super().__init__(master)
        # Liefert Zielordner/Modul-Unterordner (siehe BackupMode) statt eines
        # eigenen Ziel-Feldes.
        self.dir_provider = dir_provider
        self.folders: list[PersonalFolder] = detect_personal_folders()
        # (PersonalFolder, BooleanVar, size_label) je Ordner
        self.backup_items: list[tuple[PersonalFolder, ctk.BooleanVar, ctk.CTkLabel]] = []
        self.mode_var = ctk.StringVar(value="zip")
        self._sizes: dict[str, int] = {}
        # Dateianzahl je Ordner - fuer die Cluster-genaue Speicherplatz-Pruefung.
        self._counts: dict[str, int] = {}
        self._sizes_loaded = False
        self._build()

    # -- UI -------------------------------------------------------------

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x")
        ctk.CTkLabel(header, text="Zu sichernde Ordner:").pack(side="left", padx=(0, 8))
        ctk.CTkButton(header, text="Alle auswaehlen", width=120,
                      command=self._select_all_backup).pack(side="left", padx=4)

        self.backup_list = ctk.CTkScrollableFrame(self, height=170)
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

        mode_frame = ctk.CTkFrame(self, fg_color="transparent")
        mode_frame.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(mode_frame, text="Format:").pack(side="left", padx=(0, 8))
        ctk.CTkRadioButton(mode_frame, text="ZIP", variable=self.mode_var,
                           value="zip").pack(side="left", padx=6)
        ctk.CTkRadioButton(mode_frame, text="Kopie", variable=self.mode_var,
                           value="copy").pack(side="left", padx=6)
        ctk.CTkLabel(self, text=_MODE_HINT, text_color="gray70",
                     wraplength=820, justify="left").pack(fill="x", pady=(0, 4))

        self.totals_label = ctk.CTkLabel(self, text="Groessen werden geladen ...",
                                         text_color="gray70")
        self.totals_label.pack(fill="x", pady=(2, 4))
        self.backup_button = ctk.CTkButton(self, text="Sichern",
                                           command=self._on_backup_clicked)
        self.backup_button.pack(pady=(0, 4))

    # -- on_show ---------------------------------------------------------

    def on_show(self):
        """Beim Anzeigen des Frames die Ordnergroessen einmal im Hintergrund laden."""
        if not self._sizes_loaded and not self.worker.is_running():
            self._load_sizes()

    # -- Groessen laden -------------------------------------------------

    def _load_sizes(self):
        self.backup_button.configure(state="disabled", text="Groessen werden ermittelt ...")
        existing = [f for f, _v, _l in self.backup_items if f.exists]

        def run(_progress):
            # Groesse UND Dateianzahl je Ordner (Anzahl -> Cluster-Verschnitt).
            return {f.key: folder_size(f.path) for f in existing}

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

    def _on_sizes_loaded(self, results: dict):
        # results: {key: FolderSize}. Groesse + Dateianzahl getrennt merken.
        self._sizes = {key: fs.total_bytes for key, fs in results.items()}
        self._counts = {key: fs.file_count for key, fs in results.items()}
        self._sizes_loaded = True
        for folder, _var, label in self.backup_items:
            if folder.key in self._sizes:
                label.configure(text=_format_bytes(self._sizes[folder.key]))
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

        dest_base = self.dir_provider.resolve_target()
        if dest_base is None:
            return
        if not self._sizes_loaded:
            show_error(self, "Bitte kurz warten",
                       "Die Ordnergroessen werden noch ermittelt. Bitte einen Moment warten "
                       "und erneut auf 'Sichern' klicken.")
            return

        mode = self.mode_var.get()
        try:
            free = free_space(dest_base)
        except OSError as exc:
            show_error(self, "Zielordner", f"Zielordner nicht nutzbar:\n{exc}")
            return

        # Cluster-genaue Pruefung: im Kopie-Modus belegt jede Datei mind. einen
        # ganzen Cluster (Slack), im ZIP-Modus entsteht nur eine Datei pro
        # Ordner (vernachlaessigbarer Slack). Plus kleine Restmarge.
        cluster = cluster_size(dest_base)
        if mode == "copy":
            needed = sum(disk_reservation(self._sizes.get(f.key, 0),
                                          self._counts.get(f.key, 0), cluster)
                         for f in selected)
        else:
            needed = sum(disk_reservation(self._sizes.get(f.key, 0), 1, cluster)
                         for f in selected)
        needed = int(needed * _SPACE_SAFETY)

        if needed > free:
            show_error(self, "Zu wenig Speicherplatz",
                       f"Benoetigt (inkl. Cluster-Verschnitt): {_format_bytes(needed)}\n"
                       f"Frei am Ziel: {_format_bytes(free)}\n\n"
                       "Bitte Ziel mit mehr Platz waehlen oder weniger Ordner auswaehlen.\n"
                       "Tipp: Der ZIP-Modus braucht bei vielen kleinen Dateien deutlich "
                       "weniger Platz als eine 1:1-Kopie.")
            return
        dest = self.dir_provider.module_dir("PersoenlicheDaten")
        self.backup_button.configure(state="disabled", text="Sicherung laeuft ...")
        self.progress_bar.reset()
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
        self.progress_bar.set_fraction(1.0)
        self.backup_button.configure(state="normal", text="Sichern")
        total_files = sum(r.file_count for r in results)
        total_skipped = sum(len(r.skipped) for r in results)
        self._log(f"Fertig. {len(results)} Ordner gesichert, {total_files} Dateien.")
        lines = [f"{len(results)} Ordner gesichert.", f"Dateien insgesamt: {total_files}"]
        if total_skipped:
            lines.append(f"Uebersprungene (gesperrte) Dateien: {total_skipped}")
        lines.append(f"Zielordner: {results[0].target.parent}")
        show_info(self, "Sicherung abgeschlossen", "\n".join(lines))

    def _on_run_error(self, exc):
        super()._on_run_error(exc)
        self.backup_button.configure(state="normal", text="Sichern")


class PersonalRestoreFrame(_RunFrame):
    """Modus "Wiederherstellen": Persoenliche Ordner aus einem Backup zurueckspielen."""

    def __init__(self, master):
        super().__init__(master)
        self.folders: list[PersonalFolder] = detect_personal_folders()
        # Restore: Liste (manifest, source_path, target-Entry, ausgewaehlt-Var)
        self.restore_rows: list[tuple[dict, Path, ctk.CTkEntry, ctk.BooleanVar]] = []
        self._build()

    # -- UI -------------------------------------------------------------

    def _build(self):
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x")
        # Neuer Weg: kompletten Umzugsordner waehlen -> Backups automatisch finden.
        ctk.CTkButton(btns, text="Umzugsordner waehlen ...",
                      command=self._choose_run_folder).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Backup-ZIP(s) waehlen ...", command=self._choose_restore_zips).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Kopie-Ordner waehlen ...", command=self._choose_restore_copy).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Alle aus-/abwaehlen", width=140,
                      command=self._toggle_all_restore).pack(side="right", padx=4)

        self.restore_list = ctk.CTkScrollableFrame(self, height=200)
        self.restore_list.pack(fill="both", expand=True, pady=(6, 6))
        self.restore_hint = ctk.CTkLabel(self.restore_list,
                                         text="Noch kein Backup gewaehlt.", text_color="gray70")
        self.restore_hint.pack(anchor="w", padx=8, pady=8)

        self.restore_button = ctk.CTkButton(self, text="Wiederherstellen",
                                            command=self._on_restore_clicked)
        self.restore_button.pack(pady=(0, 4))

    # -- Backup-Quellen waehlen ----------------------------------------

    def _choose_restore_zips(self):
        paths = filedialog.askopenfilenames(parent=self, title="Backup-ZIP(s) waehlen",
                                            filetypes=[("ZIP", "*.zip")])
        self._load_restore_sources([Path(p) for p in paths])

    def _choose_restore_copy(self):
        chosen = filedialog.askdirectory(parent=self, title="Kopie-Ordner waehlen")
        if chosen:
            self._load_restore_sources([Path(chosen)])

    def _choose_run_folder(self):
        """Umzugsordner (oder PersoenlicheDaten/) waehlen und rekursiv nach
        Datensicherungen durchsuchen. Der Scan laeuft im Worker-Thread, damit
        die GUI bei vielen ZIPs nicht einfriert."""
        if self.worker.is_running():
            show_info(self, "Bitte warten", "Es laeuft gerade ein anderer Vorgang.")
            return
        chosen = filedialog.askdirectory(parent=self, title="Umzugsordner waehlen")
        if not chosen:
            return
        root = Path(chosen)
        self._log(f"Durchsuche {root} nach Datensicherungen ...")

        def run(_progress):
            return find_personal_backups(root)

        self.worker.start(run)
        self.after(100, self._poll_scan)

    def _poll_scan(self):
        try:
            while True:
                item = self.worker.queue.get_nowait()
                if item[0] == "done":
                    self._on_scan_done(item[1])
                    return
                if item[0] == "error":
                    self._on_run_error(item[1])
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll_scan)

    def _on_scan_done(self, results: list):
        self._clear_restore_list()
        if not results:
            self.restore_hint = ctk.CTkLabel(
                self.restore_list,
                text="Keine persoenlichen Datensicherungen in diesem Ordner gefunden.",
                text_color="gray70")
            self.restore_hint.pack(anchor="w", padx=8, pady=8)
            self._log("Keine Datensicherungen gefunden.")
            show_info(self, "Nichts gefunden",
                      "Keine persoenlichen Datensicherungen in diesem Ordner gefunden.")
            return
        for path, manifest in results:
            self._add_restore_row(manifest, path)
        self._log(f"{len(results)} Datensicherung(en) gefunden.")

    # -- Zeilen-Liste ---------------------------------------------------

    def _clear_restore_list(self):
        for child in self.restore_list.winfo_children():
            child.destroy()
        self.restore_rows = []

    def _add_restore_row(self, manifest: dict, source: Path):
        by_key = {f.key: f for f in self.folders}
        row = ctk.CTkFrame(self.restore_list, fg_color="transparent")
        row.pack(fill="x", padx=4, pady=2)
        var = ctk.BooleanVar(value=True)  # Funde sind per Default angehakt.
        name = manifest.get("folder_display_name", manifest.get("folder_key", "?"))
        ctk.CTkCheckBox(row, text=f"{name}  <-  {source.name}", variable=var,
                        width=0).pack(side="left", padx=(4, 8))
        target_entry = ctk.CTkEntry(row, width=260)
        default = by_key.get(manifest.get("folder_key", ""))
        target_entry.insert(0, str(default.path) if default else "")
        target_entry.pack(side="left", padx=4)
        ctk.CTkButton(row, text="Anderer Ordner ...", width=130,
                      command=lambda e=target_entry: self._choose_dir(e)).pack(side="left", padx=4)
        self.restore_rows.append((manifest, source, target_entry, var))

    def _load_restore_sources(self, sources: list[Path]):
        if not sources:
            return
        self._clear_restore_list()
        for source in sources:
            try:
                manifest = read_backup_manifest(source)
            except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
                self._log(f"Kein gueltiges Backup: {source.name} ({exc})")
                continue
            self._add_restore_row(manifest, source)
        if not self.restore_rows:
            ctk.CTkLabel(self.restore_list, text="Keine gueltigen Backups gefunden.",
                         text_color="gray70").pack(anchor="w", padx=8, pady=8)

    def _toggle_all_restore(self):
        if not self.restore_rows:
            return
        # Sind alle an -> alle aus, sonst alle an.
        all_on = all(var.get() for *_rest, var in self.restore_rows)
        new_value = not all_on
        for *_rest, var in self.restore_rows:
            var.set(new_value)

    # -- Wiederherstellen ----------------------------------------------

    def _on_restore_clicked(self):
        if self.worker.is_running():
            show_info(self, "Bitte warten", "Es laeuft gerade ein anderer Vorgang.")
            return
        if not self.restore_rows:
            show_error(self, "Kein Backup", "Bitte zuerst ein Backup waehlen.")
            return

        selected_rows = [(m, s, e) for m, s, e, v in self.restore_rows if v.get()]
        if not selected_rows:
            show_error(self, "Nichts ausgewaehlt",
                       "Bitte mindestens eine Datensicherung ankreuzen.")
            return

        jobs = []
        needed_per_drive: dict[str, int] = {}
        cluster_per_drive: dict[str, int] = {}
        for manifest, source, entry in selected_rows:
            target = entry.get().strip()
            if not target:
                show_error(self, "Kein Ziel", f"Bitte Zielordner fuer {source.name} angeben.")
                return
            target_path = Path(target)
            jobs.append((source, target_path))
            drive = target_path.anchor or str(target_path)
            # Beim Restore werden immer Einzeldateien geschrieben (auch aus ZIP)
            # -> Cluster-Verschnitt am Ziel-Laufwerk einrechnen.
            if drive not in cluster_per_drive:
                cluster_per_drive[drive] = cluster_size(target_path)
            reservation = disk_reservation(int(manifest.get("total_bytes", 0)),
                                           int(manifest.get("file_count", 0)),
                                           cluster_per_drive[drive])
            needed_per_drive[drive] = needed_per_drive.get(drive, 0) + reservation

        # Speicherplatz am Ziel pruefen (Spec §5/§6), inkl. Cluster-Verschnitt + Restmarge.
        for drive, needed in needed_per_drive.items():
            needed = int(needed * _SPACE_SAFETY)
            try:
                free = free_space(drive)
            except OSError:
                continue
            if needed > free:
                show_error(self, "Zu wenig Speicherplatz",
                           f"Ziel-Laufwerk {drive}\n"
                           f"Benoetigt (inkl. Cluster-Verschnitt): {_format_bytes(needed)}\n"
                           f"Frei: {_format_bytes(free)}\n\n"
                           "Bitte Platz schaffen oder weniger Backups auswaehlen.")
                return

        conflict = ask_conflict_mode(self)
        if conflict == "abbrechen":
            return

        self.restore_button.configure(state="disabled", text="Laeuft ...")
        self.progress_bar.reset()
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
        self.progress_bar.set_fraction(1.0)
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

    def _on_run_error(self, exc: Exception):
        super()._on_run_error(exc)
        self.restore_button.configure(state="normal", text="Wiederherstellen")
