"""
worker.py — führt eine Backup-/Restore-Funktion in einem eigenen Thread aus.

Tkinter/customtkinter-Widgets dürfen nur aus dem Haupt-Thread heraus
angefasst werden. Deshalb landet jeder Fortschritt/jedes Ergebnis in einer
Queue, die die GUI periodisch per widget.after() abfragt (Poll-Muster) —
siehe backup_tab.py/restore_tab.py, Methode _poll_worker().
"""

import queue
import threading
from typing import Callable


class Worker:
    """Kapselt genau einen laufenden Hintergrund-Thread + seine Queue."""

    def __init__(self):
        self.queue: queue.Queue = queue.Queue()
        self.thread: threading.Thread | None = None

    def is_running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def start(self, func: Callable[[Callable[[int, int, str], None]], object]) -> None:
        """Startet func(progress_callback) in einem Thread. func muss das
        Ergebnis zurückgeben (z.B. BackupResult/RestoreResult) — es wird
        automatisch als ("done", ergebnis) in die Queue gelegt. Exceptions
        werden als ("error", exception) gemeldet statt den Thread stumm
        sterben zu lassen."""

        def runner():
            try:
                result = func(self._progress)
            except Exception as exc:  # bewusst breit: jeder Fehler soll in der GUI landen, nicht nur auf der Konsole
                self.queue.put(("error", exc))
            else:
                self.queue.put(("done", result))

        self.thread = threading.Thread(target=runner, daemon=True)
        self.thread.start()

    def _progress(self, current: int, total: int, message: str) -> None:
        self.queue.put(("progress", current, total, message))
