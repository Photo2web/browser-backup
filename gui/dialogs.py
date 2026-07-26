"""
dialogs.py — wiederverwendete Dialoge fuer beide Tabs (Sichern/Wiederherstellen).
"""

from tkinter import messagebox

import customtkinter as ctk


def _root(widget):
    """Loest zu einer beliebigen Widget-Referenz das eigentliche Toplevel-
    Fenster auf — noetig fuer wm-Operationen wie transient()/grab_set(),
    die nur auf echten Toplevel-Fenstern funktionieren, nicht auf Frames."""
    return widget.winfo_toplevel()


def ask_process_warning(parent, browser_display_name: str) -> str:
    """Zeigt einen Dialog mit drei Optionen, wenn der Ziel-/Quellbrowser
    noch laeuft (PROJEKT.md §8.3/§9.5). Gibt 'beenden', 'weiter' oder
    'abbrechen' zurueck."""
    root = _root(parent)
    result = {"choice": "abbrechen"}

    dialog = ctk.CTkToplevel(root)
    dialog.title("Browser laeuft")
    dialog.transient(root)

    ctk.CTkLabel(
        dialog,
        text=(
            f"{browser_display_name} laeuft gerade.\n\n"
            "Manche Dateien koennten dadurch gesperrt sein und in der "
            "Sicherung/Wiederherstellung fehlen (die Sicherung bricht "
            "deswegen aber nicht ab). Wie moechtest du fortfahren?"
        ),
        wraplength=390,
        justify="left",
    ).pack(padx=16, pady=(16, 12), fill="x")

    button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    button_frame.pack(padx=16, pady=(0, 16), fill="x")

    def choose(value):
        result["choice"] = value
        dialog.destroy()

    ctk.CTkButton(
        button_frame, text=f"{browser_display_name} beenden", command=lambda: choose("beenden")
    ).pack(fill="x", pady=2)
    ctk.CTkButton(
        button_frame, text="Trotzdem fortfahren", fg_color="gray40", command=lambda: choose("weiter")
    ).pack(fill="x", pady=2)
    ctk.CTkButton(
        button_frame, text="Abbrechen", fg_color="gray30", command=lambda: choose("abbrechen")
    ).pack(fill="x", pady=2)

    # UNSICHER (behoben): eine fest geratene Groesse ("440x200") war zu
    # niedrig fuer Label + 3 Buttons, die Buttons ragten unter die
    # sichtbare Dialogkante. Stattdessen wird die Groesse aus dem
    # tatsaechlich benoetigten Platz berechnet — funktioniert unabhaengig
    # von Schriftgroesse/DPI-Skalierung.
    dialog.update_idletasks()
    width = max(440, dialog.winfo_reqwidth())
    height = dialog.winfo_reqheight()

    root.update_idletasks()
    x = root.winfo_x() + (root.winfo_width() - width) // 2
    y = root.winfo_y() + (root.winfo_height() - height) // 2
    dialog.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")
    dialog.resizable(False, False)

    dialog.grab_set()
    dialog.protocol("WM_DELETE_WINDOW", lambda: choose("abbrechen"))
    root.wait_window(dialog)
    return result["choice"]


def show_info(parent, title: str, message: str) -> None:
    messagebox.showinfo(title, message, parent=_root(parent))


def show_error(parent, title: str, message: str) -> None:
    messagebox.showerror(title, message, parent=_root(parent))


def ask_yes_no(parent, title: str, message: str) -> bool:
    return messagebox.askyesno(title, message, parent=_root(parent))
