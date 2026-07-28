"""
dialogs.py — wiederverwendete Dialoge im App-Design (Dark-Theme).

Statt der nativen tkinter.messagebox-Dialoge (die hell aussehen und nicht zum
customtkinter-Theme passen) werden hier einheitliche CTkToplevel-Dialoge
verwendet: Info, Fehler, Ja/Nein und die Browser-laeuft-Abfrage.
"""

import customtkinter as ctk

# Akzentfarbe fuer Fehlertitel.
_ERROR_COLOR = "#e05a4d"


def _root(widget):
    """Loest zu einer beliebigen Widget-Referenz das eigentliche Toplevel-
    Fenster auf — noetig fuer wm-Operationen wie transient()/grab_set(),
    die nur auf echten Toplevel-Fenstern funktionieren, nicht auf Frames."""
    return widget.winfo_toplevel()


def _themed_dialog(parent, title, message, buttons, *, escape_value,
                   accent_color=None, stacked=False):
    """Generischer, themed Dialog.

    buttons: Liste von (label, value, fg_color|None). Der Dialog gibt den
    value des geklickten Buttons zurueck; Escape/Schliessen liefert
    escape_value.
    """
    root = _root(parent)
    result = {"value": escape_value}

    dialog = ctk.CTkToplevel(root)
    dialog.title(title)
    dialog.transient(root)

    ctk.CTkLabel(
        dialog, text=title, font=ctk.CTkFont(size=15, weight="bold"),
        text_color=accent_color,
    ).pack(padx=18, pady=(16, 2), anchor="w")

    ctk.CTkLabel(
        dialog, text=message, wraplength=420, justify="left",
    ).pack(padx=18, pady=(2, 12), fill="x", anchor="w")

    button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    button_frame.pack(padx=18, pady=(0, 12), fill="x")

    def choose(value):
        result["value"] = value
        dialog.destroy()

    for label, value, fg_color in buttons:
        kwargs = {"text": label, "command": lambda v=value: choose(v)}
        if fg_color is not None:
            kwargs["fg_color"] = fg_color
        btn = ctk.CTkButton(button_frame, **kwargs)
        if stacked:
            btn.pack(fill="x", pady=2)
        else:
            # nebeneinander, primaerer (erster) Button rechts
            btn.pack(side="right", padx=(6, 0))

    # Groesse aus dem tatsaechlich benoetigten Platz berechnen (robust gegen
    # Schriftgroesse/DPI) und ueber dem Hauptfenster zentrieren.
    dialog.update_idletasks()
    width = max(340, dialog.winfo_reqwidth())
    height = dialog.winfo_reqheight()
    root.update_idletasks()
    x = root.winfo_x() + (root.winfo_width() - width) // 2
    y = root.winfo_y() + (root.winfo_height() - height) // 2
    dialog.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")
    dialog.resizable(False, False)

    dialog.grab_set()
    dialog.protocol("WM_DELETE_WINDOW", lambda: choose(escape_value))
    dialog.bind("<Escape>", lambda _e: choose(escape_value))
    dialog.focus_set()
    root.wait_window(dialog)
    return result["value"]


def show_info(parent, title: str, message: str) -> None:
    _themed_dialog(parent, title, message,
                   buttons=[("OK", "ok", None)], escape_value="ok")


def show_error(parent, title: str, message: str) -> None:
    _themed_dialog(parent, title, message,
                   buttons=[("OK", "ok", None)], escape_value="ok",
                   accent_color=_ERROR_COLOR)


def ask_yes_no(parent, title: str, message: str) -> bool:
    return _themed_dialog(
        parent, title, message,
        buttons=[("Ja", True, None), ("Nein", False, "gray40")],
        escape_value=False,
    )


def ask_conflict_mode(parent) -> str:
    """Konfliktverhalten fuer die Wiederherstellung.
    Rueckgabe: 'skip' | 'newer' | 'overwrite' | 'abbrechen'.
    Escape/Schliessen -> 'abbrechen' (zerstoerungsfrei, echter Abbruch)."""
    return _themed_dialog(
        parent, "Wiederherstellen - vorhandene Dateien",
        "Wie sollen bereits vorhandene Dateien am Ziel behandelt werden?",
        buttons=[
            ("Vorhandene ueberspringen (sicher)", "skip", None),
            ("Nur neuere ueberschreiben", "newer", "gray40"),
            ("Immer ueberschreiben", "overwrite", "gray30"),
            ("Abbrechen", "abbrechen", "gray30"),
        ],
        escape_value="abbrechen",
        stacked=True,
    )


def ask_process_warning(parent, browser_display_name: str) -> str:
    """Dialog mit drei Optionen, wenn der Ziel-/Quellbrowser noch laeuft
    (PROJEKT.md §8.3/§9.5). Gibt 'beenden', 'weiter' oder 'abbrechen' zurueck."""
    message = (
        f"{browser_display_name} laeuft gerade.\n\n"
        "Manche Dateien koennten dadurch gesperrt sein und in der "
        "Sicherung/Wiederherstellung fehlen (die Sicherung bricht deswegen "
        "aber nicht ab). Wie moechtest du fortfahren?"
    )
    return _themed_dialog(
        parent, "Browser laeuft", message,
        buttons=[
            (f"{browser_display_name} beenden", "beenden", None),
            ("Trotzdem fortfahren", "weiter", "gray40"),
            ("Abbrechen", "abbrechen", "gray30"),
        ],
        escape_value="abbrechen",
        stacked=True,
    )
