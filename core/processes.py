"""
processes.py — Prüfen und Beenden von Browserprozessen über psutil.

Wird von backup.py/restore.py NICHT automatisch aufgerufen — die GUI
(Phase 2) entscheidet, wann geprüft/gewarnt/beendet wird, damit der
Nutzer immer die Kontrolle behält.
"""

import psutil

# ANNAHME: Prozessnamen unter Windows. Chrome/Edge/Firefox sind bekannt und
# üblich. Brave/Vivaldi sind gut dokumentierte Standardnamen. Opera/Opera GX
# und Ecosia sind NICHT auf einer echten Installation verifiziert (siehe
# core/browsers.py) — falls der Name nicht stimmt, wird der Browser hier
# schlicht als "läuft nicht" erkannt (harmlos, kein Absturz), nur der
# Prozess-Warnhinweis vor dem Sichern greift dann nicht.
# Beta-/Nightly-Kanäle (z.B. "firefox-nightly.exe") werden NICHT erkannt —
# für v1 ausreichend, da wir auch nur Standard-Installationspfade für die
# Profil-Erkennung unterstützen.
_PROCESS_NAMES = {
    "firefox": {"firefox.exe"},
    "chrome": {"chrome.exe"},
    "edge": {"msedge.exe"},
    "brave": {"brave.exe"},
    "vivaldi": {"vivaldi.exe"},
    "opera": {"opera.exe"},
    "opera_gx": {"opera.exe"},
    "ecosia": {"ecosia.exe"},
}


def find_running_processes(browser_key: str) -> list[psutil.Process]:
    """Gibt alle laufenden Prozesse zurück, die zum angegebenen Browser
    gehören (leere Liste, wenn keiner läuft oder browser_key unbekannt ist)."""
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
            # proc.info beendet worden sein oder gehört einem anderen
            # Benutzerkonto — in beiden Fällen einfach überspringen.
            continue
    return found


def is_browser_running(browser_key: str) -> bool:
    """Kurze Ja/Nein-Prüfung, ob der Browser gerade läuft."""
    return len(find_running_processes(browser_key)) > 0


def terminate_browser(browser_key: str, confirm: bool, timeout_seconds: float = 5.0) -> list[str]:
    """Beendet alle laufenden Prozesse des angegebenen Browsers.

    Erfordert confirm=True als Sicherheitsschranke, damit ein Beenden nicht
    versehentlich ausgelöst werden kann — die GUI muss den Nutzer vorher
    ausdrücklich fragen (PROJEKT.md §8.3/§9.5).

    Gibt eine Liste von Fehlermeldungen zurück (leer = alles beendet).
    """
    if not confirm:
        raise ValueError("terminate_browser() erfordert confirm=True (Nutzerbestätigung).")

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
    # Manueller Testlauf: zeigt für alle drei Browser, ob sie gerade laufen.
    # Aufruf vom Projekt-Root aus: python -m core.processes
    for key in ("firefox", "chrome", "edge"):
        running = find_running_processes(key)
        if running:
            pids = ", ".join(str(p.pid) for p in running)
            print(f"{key}: läuft ({len(running)} Prozess(e), PIDs: {pids})")
        else:
            print(f"{key}: läuft nicht")
