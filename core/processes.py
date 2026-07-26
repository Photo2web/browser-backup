"""
processes.py — Pruefen und Beenden von Browserprozessen ueber psutil.

Wird von backup.py/restore.py NICHT automatisch aufgerufen — die GUI
(Phase 2) entscheidet, wann geprueft/gewarnt/beendet wird, damit der
Nutzer immer die Kontrolle behaelt.
"""

import psutil

# ANNAHME: Prozessnamen unter Windows fuer die drei unterstuetzten Browser.
# Beta-/Nightly-Kanaele (z.B. "firefox-nightly.exe") werden damit NICHT
# erkannt — fuer v1 ausreichend, da wir auch nur Standard-Installationspfade
# fuer die Profil-Erkennung unterstuetzen.
_PROCESS_NAMES = {
    "firefox": {"firefox.exe"},
    "chrome": {"chrome.exe"},
    "edge": {"msedge.exe"},
}


def find_running_processes(browser_key: str) -> list[psutil.Process]:
    """Gibt alle laufenden Prozesse zurueck, die zum angegebenen Browser
    gehoeren (leere Liste, wenn keiner laeuft oder browser_key unbekannt ist)."""
    names = _PROCESS_NAMES.get(browser_key, set())
    if not names:
        return []

    found: list[psutil.Process] = []
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info["name"] in names:
                found.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Prozess kann zwischen process_iter() und dem Zugriff auf
            # proc.info beendet worden sein oder gehoert einem anderen
            # Benutzerkonto — in beiden Faellen einfach ueberspringen.
            continue
    return found


def is_browser_running(browser_key: str) -> bool:
    """Kurze Ja/Nein-Pruefung, ob der Browser gerade laeuft."""
    return len(find_running_processes(browser_key)) > 0


def terminate_browser(browser_key: str, confirm: bool, timeout_seconds: float = 5.0) -> list[str]:
    """Beendet alle laufenden Prozesse des angegebenen Browsers.

    Erfordert confirm=True als Sicherheitsschranke, damit ein Beenden nicht
    versehentlich ausgeloest werden kann — die GUI muss den Nutzer vorher
    ausdruecklich fragen (PROJEKT.md §8.3/§9.5).

    Gibt eine Liste von Fehlermeldungen zurueck (leer = alles beendet).
    """
    if not confirm:
        raise ValueError("terminate_browser() erfordert confirm=True (Nutzerbestaetigung).")

    processes = find_running_processes(browser_key)
    errors: list[str] = []

    for proc in processes:
        try:
            proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            errors.append(f"PID {proc.pid}: {exc}")

    _, still_alive = psutil.wait_procs(processes, timeout=timeout_seconds)

    for proc in still_alive:
        try:
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            errors.append(f"PID {proc.pid} (kill): {exc}")

    return errors


if __name__ == "__main__":
    # Manueller Testlauf: zeigt fuer alle drei Browser, ob sie gerade laufen.
    # Aufruf vom Projekt-Root aus: python -m core.processes
    for key in ("firefox", "chrome", "edge"):
        running = find_running_processes(key)
        if running:
            pids = ", ".join(str(p.pid) for p in running)
            print(f"{key}: laeuft ({len(running)} Prozess(e), PIDs: {pids})")
        else:
            print(f"{key}: laeuft nicht")
