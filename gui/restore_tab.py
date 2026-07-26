"""
restore_tab.py — "Wiederherstellen"-Tab der BrowserBackup-GUI.

v1-Scope (bestaetigt in Phase 0): nur "vorhandenes Profil ueberschreiben".
Es gibt deshalb bewusst KEINE Radio-Auswahl "neu anlegen" — nur ein
Hinweistext, dass das in einer spaeteren Version folgt (statt einer
Option, die je nach Browser inkonsistent funktionieren wuerde).
"""

import queue
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.browsers import Browser, detect_browsers
from core.processes import is_browser_running, terminate_browser
from core.restore import read_manifest, restore_profile

from .dialogs import ask_process_warning, ask_yes_no, show_error, show_info
from .worker import Worker

CHROMIUM_PASSWORD_HINWEIS = (
    "Hinweis: Chromium-Passwoerter/Cookies funktionieren nur auf demselben "
    "Windows-Konto/PC. Fuer PC-uebergreifende Passwoerter: Chrome-Sync oder "
    "ein Passwortmanager (z. B. Vaultwarden)."
)


class RestoreTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self.browsers: list[Browser] = detect_browsers()
        self.worker = Worker()
        self.zip_path: Path | None = None
        self.manifest: dict | None = None

        self._build_ui()

    # -- UI-Aufbau -----------------------------------------------------

    def _build_ui(self):
        top = ctk.CTkFrame(self)
        top.pack(fill="x", pady=(0, 12))
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top, text="Backup-ZIP:").grid(row=0, column=0, sticky="w", padx=12, pady=8)
        zip_frame = ctk.CTkFrame(top, fg_color="transparent")
        zip_frame.grid(row=0, column=1, sticky="ew", padx=12, pady=8)
        zip_frame.grid_columnconfigure(0, weight=1)

        self.zip_entry = ctk.CTkEntry(zip_frame, placeholder_text="Noch keine ZIP ausgewaehlt")
        self.zip_entry.configure(state="disabled")
        self.zip_entry.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(zip_frame, text="Auswaehlen ...", width=110, command=self._choose_zip).grid(
            row=0, column=1, padx=(8, 0)
        )

        ctk.CTkLabel(top, text="Manifest:").grid(row=1, column=0, sticky="nw", padx=12, pady=8)
        self.manifest_box = ctk.CTkTextbox(top, height=120)
        self.manifest_box.configure(state="disabled")
        self.manifest_box.grid(row=1, column=1, sticky="ew", padx=12, pady=8)

        ctk.CTkLabel(top, text="Ziel-Browser:").grid(row=2, column=0, sticky="w", padx=12, pady=8)
        self.browser_menu = ctk.CTkOptionMenu(top, values=["-"], command=self._on_browser_change)
        self.browser_menu.grid(row=2, column=1, sticky="ew", padx=12, pady=8)

        ctk.CTkLabel(top, text="Ziel-Profil:").grid(row=3, column=0, sticky="w", padx=12, pady=8)
        self.profile_menu = ctk.CTkOptionMenu(top, values=["-"])
        self.profile_menu.grid(row=3, column=1, sticky="ew", padx=12, pady=8)

        ctk.CTkLabel(
            top,
            text=(
                "v1 unterstuetzt nur das Ueberschreiben eines vorhandenen Profils.\n"
                '"Neues Profil anlegen" folgt in einer spaeteren Version.'
            ),
            justify="left",
            text_color="gray60",
        ).grid(row=4, column=1, sticky="w", padx=12, pady=(0, 4))

        self.safety_backup_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            top, text="Sicherheits-Backup des Ziel-Profils erstellen", variable=self.safety_backup_var
        ).grid(row=5, column=1, sticky="w", padx=12, pady=4)

        self.local_state_var = ctk.BooleanVar(value=False)
        self.local_state_check = ctk.CTkCheckBox(
            top,
            text="Local State mit uebernehmen (nur Chromium — Passwoerter bleiben trotzdem nicht portabel)",
            variable=self.local_state_var,
        )
        self.local_state_check.grid(row=6, column=1, sticky="w", padx=12, pady=(0, 8))

        self.start_button = ctk.CTkButton(self, text="Wiederherstellen", command=self._on_start_clicked)
        self.start_button.pack(pady=(0, 12))

        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=(0, 8))

        self.log_box = ctk.CTkTextbox(self, height=180)
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

        if browser.local_state_path is not None:
            self.local_state_check.configure(state="normal")
        else:
            self.local_state_var.set(False)
            self.local_state_check.configure(state="disabled")

    def _log(self, message: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _choose_zip(self):
        chosen = filedialog.askopenfilename(
            parent=self, filetypes=[("BrowserBackup ZIP", "*.zip")], title="Backup-ZIP auswaehlen"
        )
        if not chosen:
            return

        zip_path = Path(chosen)
        try:
            manifest = read_manifest(zip_path)
        except (KeyError, OSError) as exc:
            show_error(self, "Ungueltige ZIP", f"Manifest konnte nicht gelesen werden:\n{exc}")
            return

        self.zip_path = zip_path
        self.manifest = manifest

        self.zip_entry.configure(state="normal")
        self.zip_entry.delete(0, "end")
        self.zip_entry.insert(0, str(zip_path))
        self.zip_entry.configure(state="disabled")

        self._show_manifest(manifest)
        self._preselect_target(manifest)

    def _show_manifest(self, manifest: dict):
        lines = [
            f"Browser:        {manifest.get('browser', '-')}",
            f"Quell-Profil:   {manifest.get('source_profile_name', '-')}",
            f"Erstellt am:    {manifest.get('created_at', '-')}",
            f"Quell-Rechner:  {manifest.get('source_host', '-')}",
            f"Quell-OS:       {manifest.get('source_os', '-')}",
            f"Local State enthalten: {'ja' if manifest.get('has_local_state') else 'nein'}",
        ]
        locked = manifest.get("locked_files") or []
        if locked:
            lines.append(f"Beim Sichern gesperrte Dateien: {len(locked)}")

        self.manifest_box.configure(state="normal")
        self.manifest_box.delete("1.0", "end")
        self.manifest_box.insert("1.0", "\n".join(lines))
        self.manifest_box.configure(state="disabled")

    def _preselect_target(self, manifest: dict):
        """Bequemlichkeit: waehlt Ziel-Browser/-Profil passend zum Manifest
        vor, falls auf diesem Rechner vorhanden. Der Nutzer kann trotzdem
        jederzeit ein anderes Ziel waehlen."""
        browser_key = manifest.get("browser")
        browser = next((b for b in self.browsers if b.key == browser_key), None)
        if not browser:
            return
        self.browser_menu.set(browser.display_name)
        self._on_browser_change(browser.display_name)

        profile_name = manifest.get("source_profile_name")
        if profile_name and profile_name in [p.name for p in browser.profiles]:
            self.profile_menu.set(profile_name)

    # -- Ablauf -----------------------------------------------------

    def _on_start_clicked(self):
        if self.worker.is_running():
            return

        if not self.zip_path:
            show_error(self, "Keine ZIP", "Bitte zuerst eine Backup-ZIP auswaehlen.")
            return

        browser = self._current_browser()
        if not browser:
            show_error(self, "Kein Browser", "Es wurde kein Ziel-Browser gefunden.")
            return

        profile_name = self.profile_menu.get()
        profile = next((p for p in browser.profiles if p.name == profile_name), None)
        if not profile:
            show_error(self, "Kein Profil", "Bitte ein Ziel-Profil auswaehlen.")
            return

        if is_browser_running(browser.key):
            choice = ask_process_warning(self, browser.display_name)
            if choice == "abbrechen":
                return
            if choice == "beenden":
                errors = terminate_browser(browser.key, confirm=True)
                for err in errors:
                    self._log(f"! Beenden fehlgeschlagen: {err}")

        confirmed = ask_yes_no(
            self,
            "Wiederherstellung bestaetigen",
            f'Das Profil "{profile.name}" ({browser.display_name}) wird ueberschrieben.\n\n'
            f"Sicherheits-Backup: {'ja' if self.safety_backup_var.get() else 'nein'}\n"
            f"Local State uebernehmen: {'ja' if self.local_state_var.get() else 'nein'}\n\n"
            "Fortfahren?",
        )
        if not confirmed:
            return

        self.start_button.configure(state="disabled", text="Wiederherstellung laeuft ...")
        self.progress_bar.set(0)
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self._log(f"Stelle wieder her: {browser.display_name} / {profile.name} ...")

        zip_path = self.zip_path
        make_safety_backup = self.safety_backup_var.get()
        restore_local_state = self.local_state_var.get()

        def run(progress_callback):
            return restore_profile(
                zip_path,
                browser,
                profile,
                make_safety_backup=make_safety_backup,
                restore_local_state=restore_local_state,
                progress_callback=progress_callback,
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
                    self._on_restore_done(browser, result)
                    return

                elif kind == "error":
                    _, exc = item
                    self._on_restore_error(exc)
                    return

        except queue.Empty:
            pass

        self.after(100, self._poll_worker, browser)

    def _on_restore_done(self, browser: Browser, result):
        self.progress_bar.set(1)
        self.start_button.configure(state="normal", text="Wiederherstellen")

        self._log(f"\nFertig. Dateien wiederhergestellt: {result.restored_files}")
        if result.locked_files:
            self._log(f"Gesperrte/uebersprungene Dateien: {len(result.locked_files)}")
            for locked in result.locked_files[:10]:
                self._log(f"  ! {locked}")
        if result.safety_backup_path:
            self._log(f"Sicherheits-Backup: {result.safety_backup_path}")
        if result.local_state_restored:
            self._log("Local State wurde uebernommen.")
            if result.local_state_backup_path:
                self._log(f"Vorherige Local State gesichert als: {result.local_state_backup_path}")

        summary_lines = [f"Dateien wiederhergestellt: {result.restored_files}"]
        if result.locked_files:
            summary_lines.append(f"Gesperrte/uebersprungene Dateien: {len(result.locked_files)}")
        if result.safety_backup_path:
            summary_lines.append(f"Sicherheits-Backup: {result.safety_backup_path}")
        if browser.local_state_path is not None:  # jeder Chromium-Fork, nicht nur Chrome/Edge
            summary_lines.append("")
            summary_lines.append(CHROMIUM_PASSWORD_HINWEIS)

        show_info(self, "Wiederherstellung abgeschlossen", "\n".join(summary_lines))

    def _on_restore_error(self, exc: Exception):
        self.start_button.configure(state="normal", text="Wiederherstellen")
        self._log(f"\nFEHLER: {exc}")
        show_error(self, "Fehler bei der Wiederherstellung", str(exc))
