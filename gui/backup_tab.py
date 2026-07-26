"""
backup_tab.py — "Sichern"-Tab der BrowserBackup-GUI.
"""

import queue
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.backup import backup_profile
from core.browsers import Browser, detect_browsers
from core.processes import is_browser_running, terminate_browser

from .dialogs import ask_process_warning, show_error, show_info
from .worker import Worker

# Deutlicher Hinweis aus PROJEKT.md §6.2 — wird nach jeder Chromium-Sicherung gezeigt.
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

        self._build_ui()

    # -- UI-Aufbau -----------------------------------------------------

    def _build_ui(self):
        form = ctk.CTkFrame(self)
        form.pack(fill="x", pady=(0, 12))
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="Browser:").grid(row=0, column=0, sticky="w", padx=12, pady=8)
        self.browser_menu = ctk.CTkOptionMenu(form, values=["-"], command=self._on_browser_change)
        self.browser_menu.grid(row=0, column=1, sticky="ew", padx=12, pady=8)

        ctk.CTkLabel(form, text="Profil:").grid(row=1, column=0, sticky="w", padx=12, pady=8)
        self.profile_menu = ctk.CTkOptionMenu(form, values=["-"])
        self.profile_menu.grid(row=1, column=1, sticky="ew", padx=12, pady=8)

        ctk.CTkLabel(form, text="Zielordner:").grid(row=2, column=0, sticky="w", padx=12, pady=8)
        target_frame = ctk.CTkFrame(form, fg_color="transparent")
        target_frame.grid(row=2, column=1, sticky="ew", padx=12, pady=8)
        target_frame.grid_columnconfigure(0, weight=1)

        self.target_entry = ctk.CTkEntry(target_frame, placeholder_text="Zielordner fuer die ZIP-Datei")
        self.target_entry.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(target_frame, text="Durchsuchen ...", width=110, command=self._choose_target_dir).grid(
            row=0, column=1, padx=(8, 0)
        )

        self.exclude_cache_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            form, text="Cache/temporaere Daten ausschliessen", variable=self.exclude_cache_var
        ).grid(row=3, column=1, sticky="w", padx=12, pady=(0, 8))

        self.start_button = ctk.CTkButton(self, text="Sichern", command=self._on_start_clicked)
        self.start_button.pack(pady=(0, 12))

        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=(0, 8))

        self.log_box = ctk.CTkTextbox(self, height=220)
        self.log_box.configure(state="disabled")
        self.log_box.pack(fill="both", expand=True)

        if not self.browsers:
            self._log("Kein unterstuetzter Browser (Firefox/Chrome/Edge) gefunden.")
        else:
            names = [b.display_name for b in self.browsers]
            self.browser_menu.configure(values=names)
            self.browser_menu.set(names[0])
            self._on_browser_change(names[0])

    # -- Hilfsfunktionen -------------------------------------------------

    def _current_browser(self) -> Browser | None:
        name = self.browser_menu.get()
        return next((b for b in self.browsers if b.display_name == name), None)

    def _on_browser_change(self, _value):
        browser = self._current_browser()
        if not browser:
            return
        names = [p.name for p in browser.profiles]
        self.profile_menu.configure(values=names or ["-"])
        if names:
            default = next((p.name for p in browser.profiles if p.is_default), names[0])
            self.profile_menu.set(default)

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

        browser = self._current_browser()
        if not browser:
            show_error(self, "Kein Browser", "Es wurde kein unterstuetzter Browser gefunden.")
            return

        profile_name = self.profile_menu.get()
        profile = next((p for p in browser.profiles if p.name == profile_name), None)
        if not profile:
            show_error(self, "Kein Profil", "Bitte ein Profil auswaehlen.")
            return

        dest_text = self.target_entry.get().strip()
        if not dest_text:
            show_error(self, "Kein Zielordner", "Bitte einen Zielordner fuer die Sicherung auswaehlen.")
            return
        dest_dir = Path(dest_text)

        if is_browser_running(browser.key):
            choice = ask_process_warning(self, browser.display_name)
            if choice == "abbrechen":
                return
            if choice == "beenden":
                errors = terminate_browser(browser.key, confirm=True)
                for err in errors:
                    self._log(f"! Beenden fehlgeschlagen: {err}")

        exclude_cache = self.exclude_cache_var.get()

        self.start_button.configure(state="disabled", text="Sicherung laeuft ...")
        self.progress_bar.set(0)
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self._log(f"Sichere {browser.display_name} / {profile.name} ...")

        def run(progress_callback):
            return backup_profile(
                browser, profile, dest_dir, exclude_cache=exclude_cache, progress_callback=progress_callback
            )

        self.worker.start(run)
        self.after(100, self._poll_worker, browser)

    def _poll_worker(self, browser: Browser):
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
                    _, result = item
                    self._on_backup_done(browser, result)
                    return

                elif kind == "error":
                    _, exc = item
                    self._on_backup_error(exc)
                    return

        except queue.Empty:
            pass

        self.after(100, self._poll_worker, browser)

    def _on_backup_done(self, browser: Browser, result):
        self.progress_bar.set(1)
        self.start_button.configure(state="normal", text="Sichern")

        self._log(f"\nFertig: {result.zip_path}")
        self._log(f"Dateien gesichert: {result.file_count}")
        if result.locked_files:
            self._log(f"Gesperrte/uebersprungene Dateien: {len(result.locked_files)}")
            for locked in result.locked_files[:10]:
                self._log(f"  ! {locked}")

        summary_lines = [
            f"ZIP-Datei: {result.zip_path}",
            f"Dateien gesichert: {result.file_count}",
        ]
        if result.locked_files:
            summary_lines.append(f"Gesperrte/uebersprungene Dateien: {len(result.locked_files)}")
        if browser.key in ("chrome", "edge"):
            summary_lines.append("")
            summary_lines.append(CHROMIUM_PASSWORD_HINWEIS)

        show_info(self, "Sicherung abgeschlossen", "\n".join(summary_lines))

    def _on_backup_error(self, exc: Exception):
        self.start_button.configure(state="normal", text="Sichern")
        self._log(f"\nFEHLER: {exc}")
        show_error(self, "Fehler bei der Sicherung", str(exc))
