"""
restore_tab.py — "Wiederherstellen"-Tab der Umzugstool-GUI.

Es koennen mehrere Backup-ZIPs auf einmal ausgewaehlt werden (z.B. wenn
jedes Profil einzeln gesichert wurde, siehe gui/backup_tab.py). Jede ZIP
wird automatisch anhand ihres Manifests (Browser + Quell-Profilname) einem
installierten Ziel-Browser/-Profil zugeordnet; ueber eine Checkliste kann
der Nutzer gezielt einzelne oder alle davon wiederherstellen.

v1-Scope (bestaetigt in Phase 0): nur "vorhandenes Profil ueberschreiben".
Es gibt deshalb bewusst KEINE Radio-Auswahl "neu anlegen" — nur ein
Hinweistext, dass das in einer spaeteren Version folgt.
"""

import json
import queue
import zipfile
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.browsers import Browser, Profile, detect_browsers
from core.processes import is_browser_running, terminate_browser
from core.restore import read_manifest, restore_profile

from .dialogs import ask_process_warning, ask_yes_no, show_error, show_info
from .progress import ColorProgressBar
from .worker import Worker

CHROMIUM_PASSWORD_HINWEIS = (
    "Hinweis: Chromium-Passwoerter/Cookies funktionieren nur auf demselben "
    "Windows-Konto/PC. Fuer PC-uebergreifende Passwoerter: Chrome-Sync oder "
    "ein Passwortmanager (z. B. Vaultwarden)."
)


@dataclass
class _Candidate:
    """Eine ausgewaehlte ZIP-Datei + der dazu automatisch ermittelte
    Ziel-Browser (falls installiert). Das Ziel-Profil kann der Nutzer per
    Dropdown noch aendern (profile_menu ist None, wenn browser nicht
    installiert ist — dann gibt es nichts zum Wiederherstellen)."""

    zip_path: Path
    manifest: dict
    browser: Browser | None
    var: object = None            # ctk.BooleanVar
    profile_menu: object = None   # ctk.CTkOptionMenu, nur falls browser gefunden


class RestoreTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self.browsers: list[Browser] = detect_browsers()
        self.worker = Worker()
        self.candidates: list[_Candidate] = []

        self._build_ui()

    # -- UI-Aufbau -----------------------------------------------------

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x")
        ctk.CTkButton(header, text="Backup-ZIPs auswaehlen ...", command=self._choose_zips).pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkButton(header, text="Alle auswaehlen", width=120, command=self._select_all).pack(
            side="left", padx=4
        )
        ctk.CTkButton(header, text="Alle abwaehlen", width=120, command=self._select_none).pack(
            side="left", padx=4
        )

        self.list_frame = ctk.CTkScrollableFrame(self, height=200, label_text="Ausgewaehlte Backups")
        self.list_frame.pack(fill="x", pady=(8, 12))
        self._refresh_placeholder()

        options = ctk.CTkFrame(self)
        options.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            options,
            text=(
                "v1 unterstuetzt nur das Ueberschreiben eines vorhandenen Profils.\n"
                '"Neues Profil anlegen" folgt in einer spaeteren Version.'
            ),
            justify="left",
            text_color="gray60",
        ).pack(anchor="w", padx=12, pady=(8, 4))

        self.safety_backup_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            options, text="Sicherheits-Backup der Ziel-Profile erstellen", variable=self.safety_backup_var
        ).pack(anchor="w", padx=12, pady=4)

        self.local_state_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            options,
            text=(
                "Local State bei betroffenen Chromium-Profilen mit uebernehmen "
                "(Passwoerter bleiben trotzdem nicht portabel)"
            ),
            variable=self.local_state_var,
        ).pack(anchor="w", padx=12, pady=(0, 8))

        self.start_button = ctk.CTkButton(self, text="Wiederherstellen", command=self._on_start_clicked)
        self.start_button.pack(pady=(0, 12))
        # Ohne ausgewaehlte ZIPs gibt es kein installiertes Ziel -> Button gesperrt.
        self._update_start_button_state()

        self.progress_bar = ColorProgressBar(self)
        self.progress_bar.pack(fill="x", pady=(0, 8))

        self.log_box = ctk.CTkTextbox(self, height=180)
        self.log_box.configure(state="disabled")
        self.log_box.pack(fill="both", expand=True)

        if not self.browsers:
            self._log("Kein unterstuetzter Browser (Firefox/Chrome/Edge/...) gefunden.")

    def _refresh_placeholder(self):
        if not self.candidates:
            ctk.CTkLabel(
                self.list_frame, text="Noch keine ZIP-Dateien ausgewaehlt.", text_color="gray60"
            ).pack(anchor="w", padx=8, pady=8)

    def _update_start_button_state(self):
        """Aktiviert den Wiederherstellen-Button nur, wenn mindestens ein
        ausgewaehltes Backup einem installierten Ziel-Browser zugeordnet ist.
        Ohne installiertes Ziel waere ein Klick wirkungslos (nichts wird
        zurueckgespielt) -> Button bleibt gesperrt statt erst beim Klick zu
        meckern."""
        has_target = any(c.browser is not None for c in self.candidates)
        self.start_button.configure(state="normal" if has_target else "disabled")

    def _log(self, message: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # -- ZIP-Auswahl + automatischer Abgleich -----------------------------

    def _choose_zips(self):
        chosen = filedialog.askopenfilenames(
            parent=self, filetypes=[("Umzugstool ZIP", "*.zip")], title="Backup-ZIPs auswaehlen"
        )
        if not chosen:
            return

        self.candidates = []
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        for path_str in chosen:
            zip_path = Path(path_str)
            try:
                manifest = read_manifest(zip_path)
            except (KeyError, OSError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
                # z.B. beschaedigte/keine echte ZIP-Datei oder fehlendes/
                # kaputtes Manifest — einzelne Datei ueberspringen statt
                # die ganze Auswahl abzubrechen.
                self._log(f"! Manifest von {zip_path.name} konnte nicht gelesen werden: {exc}")
                continue

            browser = next((b for b in self.browsers if b.key == manifest.get("browser")), None)
            candidate = _Candidate(zip_path=zip_path, manifest=manifest, browser=browser)
            self.candidates.append(candidate)
            self._add_row(candidate)

        self._refresh_placeholder()
        self._update_start_button_state()

    def _add_row(self, candidate: _Candidate):
        row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        row.pack(fill="x", pady=2)

        source_profile = candidate.manifest.get("source_profile_name", "?")
        created_at = candidate.manifest.get("created_at", "?")

        if candidate.browser is None:
            candidate.var = ctk.BooleanVar(value=False)
            browser_key = candidate.manifest.get("browser", "?")
            text = (
                f"{browser_key} – {source_profile}  "
                f"(Browser nicht installiert - bitte zuerst installieren, siehe Tab Neuinstallation)"
            )
            checkbox = ctk.CTkCheckBox(row, text=text, variable=candidate.var, state="disabled")
            checkbox.pack(side="left", anchor="w")
            return

        candidate.var = ctk.BooleanVar(value=True)
        label = f"{candidate.browser.display_name} – Quelle: {source_profile}  (erstellt {created_at})"
        ctk.CTkCheckBox(row, text=label, variable=candidate.var).pack(side="left", anchor="w")

        ctk.CTkLabel(row, text="Ziel-Profil:").pack(side="left", padx=(12, 4))
        profile_names = [p.name for p in candidate.browser.profiles]
        best_match = source_profile if source_profile in profile_names else None
        default_name = next((p.name for p in candidate.browser.profiles if p.is_default), None)
        preselect = best_match or default_name or (profile_names[0] if profile_names else "-")

        candidate.profile_menu = ctk.CTkOptionMenu(row, values=profile_names or ["-"], width=160)
        candidate.profile_menu.set(preselect)
        candidate.profile_menu.pack(side="left")

    def _select_all(self):
        for candidate in self.candidates:
            if candidate.browser is not None:
                candidate.var.set(True)

    def _select_none(self):
        for candidate in self.candidates:
            if candidate.browser is not None:
                candidate.var.set(False)

    # -- Ablauf -----------------------------------------------------

    def _resolve_selected(self) -> list[tuple[Browser, Profile, Path, dict]]:
        """Liefert (Browser, Profile, zip_path, manifest) fuer alle
        angehakten Kandidaten, mit dem aktuell im Dropdown gewaehlten
        Ziel-Profil."""
        resolved = []
        for candidate in self.candidates:
            if not candidate.browser or not candidate.var.get():
                continue
            profile_name = candidate.profile_menu.get()
            profile = next((p for p in candidate.browser.profiles if p.name == profile_name), None)
            if profile:
                resolved.append((candidate.browser, profile, candidate.zip_path, candidate.manifest))
        return resolved

    def _on_start_clicked(self):
        if self.worker.is_running():
            return

        selected = self._resolve_selected()
        if not selected:
            show_error(self, "Keine Auswahl", "Bitte mindestens ein Backup mit installiertem Ziel-Browser auswaehlen.")
            return

        distinct_browsers = list({b.key: b for b, _, _, _ in selected}.values())
        for browser in distinct_browsers:
            if is_browser_running(browser.key):
                choice = ask_process_warning(self, browser.display_name)
                if choice == "abbrechen":
                    return
                if choice == "beenden":
                    errors = terminate_browser(browser.key, confirm=True)
                    for err in errors:
                        self._log(f"! Beenden fehlgeschlagen ({browser.display_name}): {err}")

        make_safety_backup = self.safety_backup_var.get()
        restore_local_state = self.local_state_var.get()

        overview = "\n".join(f'  - {b.display_name}: "{p.name}"' for b, p, _, _ in selected)
        confirmed = ask_yes_no(
            self,
            "Wiederherstellung bestaetigen",
            f"Folgende {len(selected)} Profil(e) werden ueberschrieben:\n\n{overview}\n\n"
            f"Sicherheits-Backup: {'ja' if make_safety_backup else 'nein'}\n"
            f"Local State uebernehmen (wo zutreffend): {'ja' if restore_local_state else 'nein'}\n\n"
            "Fortfahren?",
        )
        if not confirmed:
            return

        self.start_button.configure(state="disabled", text="Wiederherstellung laeuft ...")
        self.progress_bar.reset()
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self._log(f"Stelle {len(selected)} Profil(e) wieder her ...")

        total_items = len(selected)

        def run(progress_callback):
            results = []
            for index, (browser, profile, zip_path, _manifest) in enumerate(selected, start=1):
                def wrapped_cb(current, total, message, _b=browser, _p=profile, _i=index):
                    progress_callback(current, total, f"[{_i}/{total_items}] {_b.display_name} / {_p.name}: {message}")

                result = restore_profile(
                    zip_path,
                    browser,
                    profile,
                    make_safety_backup=make_safety_backup,
                    restore_local_state=restore_local_state,
                    progress_callback=wrapped_cb,
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
                        self.progress_bar.set_fraction(current / total)
                    self._log(message)

                elif kind == "done":
                    _, results = item
                    self._on_restore_done(results)
                    return

                elif kind == "error":
                    _, exc = item
                    self._on_restore_error(exc)
                    return

        except queue.Empty:
            pass

        self.after(100, self._poll_worker)

    def _on_restore_done(self, results):
        self.progress_bar.set_fraction(1.0)
        self.start_button.configure(text="Wiederherstellen")
        self._update_start_button_state()

        total_restored = sum(result.restored_files for _, _, result in results)
        total_locked = sum(len(result.locked_files) for _, _, result in results)
        any_chromium = any(browser.local_state_path is not None for browser, _, _ in results)

        self._log(f"\nFertig. {len(results)} Profil(e) wiederhergestellt.")
        for browser, profile, result in results:
            self._log(
                f"  {browser.display_name} / {profile.name}: {result.restored_files} Dateien, "
                f"{len(result.locked_files)} gesperrt"
            )
            if result.safety_backup_path:
                self._log(f"    Sicherheits-Backup: {result.safety_backup_path}")
            if result.local_state_restored:
                self._log("    Local State wurde uebernommen.")

        summary_lines = [
            f"{len(results)} Profil(e) wiederhergestellt.",
            f"Dateien insgesamt: {total_restored}",
        ]
        if total_locked:
            summary_lines.append(f"Gesperrte/uebersprungene Dateien insgesamt: {total_locked}")
        if any_chromium:
            summary_lines.append("")
            summary_lines.append(CHROMIUM_PASSWORD_HINWEIS)

        show_info(self, "Wiederherstellung abgeschlossen", "\n".join(summary_lines))

    def _on_restore_error(self, exc: Exception):
        self.start_button.configure(text="Wiederherstellen")
        self._update_start_button_state()
        self._log(f"\nFEHLER: {exc}")
        show_error(self, "Fehler bei der Wiederherstellung", str(exc))
