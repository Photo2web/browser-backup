"""Erkennung installierter Programme über die Windows-Uninstall-Registry.

GUI-unabhängig und einzeln testbar. Liefert eine Liste von ``InstalledProgram``
aus den Uninstall-Keys von HKLM (alle Benutzer, 64- und 32-Bit-View) sowie HKCU
(nur dieser Benutzer). Der Scope steht durch die Hive fest: HKLM = ``machine``
(Deinstallation braucht Admin), HKCU = ``user``.

Gelesen wird mit Pythons eingebautem ``winreg`` (keine Fremd-Abhängigkeit). Auf
Nicht-Windows oder ohne winreg ist die Liste leer. Das eigentliche Filtern/
Umwandeln passiert in reinen Funktionen, sodass Tests eine Mock-Registry
(Liste aus (values, scope, key_path)-Tupeln) einspeisen können.
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    import winreg  # nur auf Windows vorhanden
except ImportError:  # pragma: no cover - Nicht-Windows
    winreg = None

# Registry-Einträge dieser ReleaseType-Werte sind Updates/Hotfixes -> ausblenden.
_UPDATE_RELEASE_TYPES = frozenset({"update", "hotfix", "security update"})


@dataclass(frozen=True)
class InstalledProgram:
    """Ein installiertes Programm laut Uninstall-Registry."""

    name: str
    publisher: str | None
    version: str | None
    scope: str                      # "user" | "machine"
    uninstall_string: str | None
    quiet_uninstall_string: str | None
    install_location: str | None
    registry_key: str

    @property
    def needs_admin(self) -> bool:
        """systemweite Programme (HKLM) erfordern Admin-Rechte zum Entfernen."""
        return self.scope == "machine"


# ---------------------------------------------------------------------------
# Reine Umwandlung/Filterung (testbar mit Mock-Einträgen)
# ---------------------------------------------------------------------------

def _as_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean(value) -> str | None:
    """Registry-Wert zu getrimmtem String oder None (leer/kein String)."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _raw_to_program(values: dict, scope: str, key_path: str) -> InstalledProgram | None:
    """Wandelt die Registry-Werte eines Uninstall-Eintrags in ein
    ``InstalledProgram`` um - oder ``None``, wenn der Eintrag herausgefiltert
    wird (kein Name, nicht deinstallierbar, System-/Update-Eintrag)."""
    name = _clean(values.get("DisplayName"))
    if not name:
        return None

    uninstall = _clean(values.get("UninstallString"))
    quiet = _clean(values.get("QuietUninstallString"))
    if not uninstall and not quiet:
        return None

    # System-Komponenten und Windows-Updates/Hotfixes ausblenden.
    if _as_int(values.get("SystemComponent")) == 1:
        return None
    release_type = (_clean(values.get("ReleaseType")) or "").lower()
    if release_type in _UPDATE_RELEASE_TYPES:
        return None
    if _clean(values.get("ParentKeyName")):
        return None

    return InstalledProgram(
        name=name,
        publisher=_clean(values.get("Publisher")),
        version=_clean(values.get("DisplayVersion")),
        scope=scope,
        uninstall_string=uninstall,
        quiet_uninstall_string=quiet,
        install_location=_clean(values.get("InstallLocation")),
        registry_key=key_path,
    )


def build_programs(raw_entries) -> list[InstalledProgram]:
    """Reine Funktion: (values, scope, key_path)-Tupel -> gefilterte, sortierte,
    deduplizierte Programmliste. Dedupe nach (Name, Version, Scope), damit die
    32-/64-Bit-View dasselbe Programm nicht doppelt zeigt."""
    programs: list[InstalledProgram] = []
    for values, scope, key_path in raw_entries:
        prog = _raw_to_program(values, scope, key_path)
        if prog is not None:
            programs.append(prog)

    seen: set[tuple[str, str, str]] = set()
    unique: list[InstalledProgram] = []
    for prog in sorted(programs, key=lambda p: p.name.lower()):
        sig = (prog.name.lower(), prog.version or "", prog.scope)
        if sig in seen:
            continue
        seen.add(sig)
        unique.append(prog)
    return unique


# ---------------------------------------------------------------------------
# Registry lesen (nur Windows)
# ---------------------------------------------------------------------------

_UNINSTALL_SUBKEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"


def _read_values(key) -> dict:
    """Alle Werte eines geöffneten Registry-Keys als Dict."""
    values: dict = {}
    try:
        value_count = winreg.QueryInfoKey(key)[1]
    except OSError:
        return values
    for i in range(value_count):
        try:
            name, data, _vtype = winreg.EnumValue(key, i)
        except OSError:
            continue
        values[name] = data
    return values


def _read_root(hive, view_flag: int, scope: str):
    """Liefert (values, scope, key_path) für jeden Unterschlüssel eines
    Uninstall-Roots. Fehler (fehlender Schlüssel, Zugriff) -> übersprungen."""
    access = winreg.KEY_READ | view_flag
    try:
        root = winreg.OpenKey(hive, _UNINSTALL_SUBKEY, 0, access)
    except OSError:
        return
    try:
        subkey_count = winreg.QueryInfoKey(root)[0]
        for i in range(subkey_count):
            try:
                child_name = winreg.EnumKey(root, i)
                child = winreg.OpenKey(root, child_name, 0, access)
            except OSError:
                continue
            try:
                yield _read_values(child), scope, f"{_UNINSTALL_SUBKEY}\\{child_name}"
            finally:
                winreg.CloseKey(child)
    finally:
        winreg.CloseKey(root)


def _iter_raw_entries():
    """Alle Roh-Einträge aus HKLM (64/32-Bit) + HKCU. Leer ohne winreg."""
    if winreg is None:
        return
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY, "machine"),
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY, "machine"),
        (winreg.HKEY_CURRENT_USER, 0, "user"),
    ]
    for hive, view_flag, scope in roots:
        yield from _read_root(hive, view_flag, scope)


def list_installed_programs() -> list[InstalledProgram]:
    """Liest die installierten Programme aus der Uninstall-Registry.

    Reihenfolge alphabetisch nach Name. Auf Nicht-Windows leere Liste.
    """
    return build_programs(_iter_raw_entries())


if __name__ == "__main__":  # pragma: no cover - manueller Sichttest (nur Lesezugriff)
    result = list_installed_programs()
    machine = [p for p in result if p.scope == "machine"]
    user = [p for p in result if p.scope == "user"]
    print(f"Programme gesamt : {len(result)}")
    print(f"  alle Benutzer  : {len(machine)}")
    print(f"  nur dieser User: {len(user)}")
    for p in result[:15]:
        print(f"  - [{p.scope}] {p.name}  {p.version or ''}")
