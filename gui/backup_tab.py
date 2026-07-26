"""
backup_tab.py — "Sichern"-Tab der BrowserBackup-GUI.

Alle gefundenen Browser/Profil-Kombinationen erscheinen als Checkliste —
der Nutzer kann einzelne, mehrere oder per "Alle auswaehlen" alle auf
einmal sichern (jede Kombination landet in einer eigenen ZIP-Datei).
"""

import queue
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.backup import backup_profile
from core.browsers import Browser, Profile, detect_browsers
from core.processes import is_browser_running, terminate_browser

from .dialogs import ask_process_warning, show_error, show_info
from .worker import Worker

# Deutlicher Hinweis aus PROJEKT.md §6.2 — wird gezeigt, sobald mindestens
# ein Chromium-basierter Browser (Chrome, Edge, Brave, Opera, Ecosia, ...) dabei war.
CHROMIUM_PASSWORD_HINWEIS = (
    "Hinweis: Chromium-Passwoerter/Cookies funktionieren nur auf demselben "
    "Windows-Konto/PC. Fuer PC-uebergreifende Passwoerter: Chrome-Sync oder "
    "ein Passwortmanager (z. B. Vaultwarden)."
)


class BackupTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self.browsers: list[Browser] = detect_browsers()
        self.worker = Worker()
        # (Browser, Profile, BooleanVar) je Zeile in der Checkliste.
        self.items: list[tuple[Browser, Profile, ctk.BooleanVar]] = []

        self._build_ui()

    # -- UI-Aufbau -----------------------------------------------------

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x")
        ctk.CTkLabel(header, text="Zu sichernde Profile:").pack(side="left", padx=(0, 8))
        ctk.CTkButton(header, text="Alle auswaehlen", width=120, command=self._select_all).pack(
            side="left", padx=4
        )
        ctk.CTkButton(header, text="Alle abwaehlen", width=120, command=self._select_none).pack(
            side="left", padx=4
        )

        self.list_frame = ctk.CTkScrollableFrame(self, height=160)
        self.list_frame.pack(fill="x", pady=(4, 12))
        self._populate_checklist()

        form = ctk.CTkFrame(self)
        form.pack(fill="x", pady=(0, 12))
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="Zielordner:").grid(row=0, column=0, sticky="w", padx=12, pady=8)
        target_frame = ctk.CTkFrame(form, fg_color="transparent")
        target_frame.grid(row=0, column=1, sticky="ew", padx=12, pady=8)
        target_frame.grid_columnconfigure(0, weight=1)

        self.target_entry = ctk.CTkEntry(target_frame, placeholder_text="Zielordner fuer die ZIP-Dateien")
        self.target_entry.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(target_frame, text="Durchsuchen ...", width=110, command=self._choose_target_dir).grid(
            row=0, column=1, padx=(8, 0)
        )

        self.exclude_cache_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            form, text="Cache/temporaere Daten ausschliessen", variable=self.exclude_cache_var
        ).grid(row=1, column=1, sticky="w", padx=12, pady=(0, 8))

        self.start_button = ctk.CTkButton(self, text="Sichern", command=self._on_start_clicked)
        self.start_button.pack(pady=(0, 12))

        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=(0, 8))

        self.log_box = ctk.CTkTextbox(self, height=200)
        self.log_box.configure(state="disabled")
        self.log_box.pack(fill="both", expand=True)

        if not self.browsers:
            self._log("Kein unterstuetzter Browser (Firefox/Chrome/Edge/...) gefunden.")

    def _populate_checklist(self):
        for browser in self.browsers:
            for profile in browser.profiles:
                var = ctk.BooleanVar(value=profile.is_default)
                label = f"{browser.display_name} – {profile.name}"
                if profile.is_default:
                    label += "  [Standard]"
                ctk.CTkCheckBox(self.list_frame, text=label, variable=var).pack(
                    anchor="w", padx=8, pady=2
                )
                self.items.append((browser, profile, var))

    # -- Hilfsfunktionen -------------------------------------------------

    def _select_all(self):
        for _, _, var in self.items:
            var.set(True)

    def _select_none(self):
        for _, _, var in self.items:
            var.set(False)

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

    # -- Ablauf -----------------------------------------------------

    def _on_start_clicked(self):
        if self.worker.is_running():
            return

        selected = [(b, p) for (b, p, var) in self.items if var.get()]
        if not selected:
            show_error(self, "Keine Auswahl", "Bitte mindestens ein Profil auswaehlen.")
            return

        dest_text = self.target_entry.get().strip()
        if not dest_text:
            show_error(self, "Kein Zielordner", "Bitte einen Zielordner fuer die Sicherung auswaehlen.")
            return
        dest_dir = Path(dest_text)

        # Jeden betroffenen Browser nur einmal auf "laeuft gerade" pruefen,
        # auch wenn mehrere seiner Profile ausgewaehlt sind.
        distinct_browsers = list({b.key: b for b, _ in selected}.values())
        for browser in distinct_browsers:
            if is_browser_running(browser.key):
                choice = ask_process_warning(self, browser.display_name)
                if choice == "abbrechen":
                    return
                if choice == "beenden":
                    errors = terminate_browser(browser.key, confirm=True)
                    for err in errors:
                        self._log(f"! Beenden fehlgeschlagen ({browser.display_name}): {err}")

        exclude_cache = self.exclude_cache_var.get()

        self.start_button.configure(state="disabled", text="Sicherung laeuft ...")
        self.progress_bar.set(0)
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self._log(f"Sichere {len(selected)} Profil(e) ...")

        total_items = len(selected)

        def run(progress_callback):
            results = []
            for index, (browser, profile) in enumerate(selected, start=1):
                def wrapped_cb(current, total, message, _b=browser, _p=profile, _i=index):
                    progress_callback(current, total, f"[{_i}/{total_items}] {_b.display_name} / {_p.name}: {message}")

                result = backup_profile(
                    browser, profile, dest_dir, exclude_cache=exclude_cache, progress_callback=wrapped_cb
                )
                results.append((browser, profile, result))
            return results

        self.worker.start(run)
        self.after(100, self._poll_worker)

    def _poll_worker(self):
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
                    _, results = item
                    self._on_backup_done(results)
                    return

                elif kind == "error":
                    _, exc = item
                    self._on_backup_error(exc)
                    return

        except queue.Empty:
            pass

        self.after(100, self._poll_worker)

    def _on_backup_done(self, results):
        self.progress_bar.set(1)
        self.start_button.configure(state="normal", text="Sichern")

        total_files = sum(result.file_count for _, _, result in results)
        total_locked = sum(len(result.locked_files) for _, _, result in results)
        any_chromium = any(browser.local_state_path is not None for browser, _, _ in results)

        self._log(f"\nFertig. {len(results)} Profil(e) gesichert.")
        for browser, profile, result in results:
            self._log(
                f"  {browser.display_name} / {profile.name}: {result.zip_path.name} "
                f"({result.file_count} Dateien, {len(result.locked_files)} gesperrt)"
            )

        summary_lines = [
            f"{len(results)} Profil(e) gesichert.",
            f"Dateien insgesamt: {total_files}",
        ]
        if total_locked:
            summary_lines.append(f"Gesperrte/uebersprungene Dateien insgesamt: {total_locked}")
        if results:
            summary_lines.append(f"Zielordner: {results[0][2].zip_path.parent}")
        if any_chromium:
            summary_lines.append("")
            summary_lines.append(CHROMIUM_PASSWORD_HINWEIS)

        show_info(self, "Sicherung abgeschlossen", "\n".join(summary_lines))

    def _on_backup_error(self, exc: Exception):
        self.start_button.configure(state="normal", text="Sichern")
        self._log(f"\nFEHLER: {exc}")
        show_error(self, "Fehler bei der Sicherung", str(exc))
