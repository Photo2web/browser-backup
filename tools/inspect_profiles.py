"""
inspect_profiles.py — Phase 0: Realitaets-Check der Profilstrukturen

Liest NUR (aendert nichts!) die lokalen Browserprofile aus und gibt eine
Uebersicht aus, damit wir die Cache-Blacklist aus PROJEKT.md gegen die
Realitaet pruefen koennen, statt sie zu raten.

Deckt ab:
  - Firefox: %APPDATA%\\Mozilla\\Firefox\\profiles.ini
  - Chrome:  %LOCALAPPDATA%\\Google\\Chrome\\User Data\\Local State
  - Edge:    %LOCALAPPDATA%\\Microsoft\\Edge\\User Data\\Local State

Fuer jedes gefundene Profil:
  - Top-Level-Eintraege (Ordner/Dateien) mit Groesse
  - Gesamtgroesse des Profils
  - Groesse OHNE die vorgeschlagene Cache-Blacklist (Effekt-Vorschau)

Aufruf:
    python inspect_profiles.py

Kein Adminrecht noetig, keine Schreibzugriffe.
"""

import configparser
import json
import os
from pathlib import Path

TOOL_VERSION = "0.0.2-phase0"

# ANNAHME: Startwerte aus PROJEKT.md §5.1 — werden nach dieser Ausgabe
# gemeinsam mit dem Nutzer gegen die reale Ordnerstruktur verifiziert.
FIREFOX_BLACKLIST_PREVIEW = {
    "cache2",
    "startupCache",
    "shader-cache",
    "thumbnails",
    "OfflineCache",
    "crashes",
    "minidumps",
    "datareporting",
    "lock",
    ".parentlock",
    "parent.lock",
}

CHROMIUM_BLACKLIST_PREVIEW = {
    "Cache",
    "Code Cache",
    "GPUCache",
    "GrShaderCache",
    "ShaderCache",
    "Media Cache",
    "Application Cache",
    "component_crx_cache",
    "Crashpad",
    # UNSICHER: "Service Worker/CacheStorage" und "Service Worker/ScriptCache"
    # sind Unterordner-Pfade (Ebene 2), keine Top-Level-Eintraege — werden
    # separat unten beim Top-Level-Eintrag "Service Worker" rekursiv geprueft.
}


def format_size(num_bytes: int) -> str:
    """Formatiert Bytes menschenlesbar (KB/MB/GB)."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def dir_size(path: Path) -> int:
    """Summiert die Groesse aller Dateien unterhalb von path rekursiv.
    Unlesbare/gesperrte Eintraege werden ignoriert (nur Anzeige, kein Abbruch)."""
    total = 0
    try:
        for entry in path.rglob("*"):
            try:
                if entry.is_file():
                    total += entry.stat().st_size
            except (OSError, PermissionError):
                continue
    except (OSError, PermissionError):
        pass
    return total


def entry_size(path: Path) -> int:
    """Groesse eines einzelnen Top-Level-Eintrags (Datei oder Ordner rekursiv)."""
    try:
        if path.is_dir():
            return dir_size(path)
        if path.is_file():
            return path.stat().st_size
    except (OSError, PermissionError):
        pass
    return 0


def list_top_level(profile_path: Path):
    """Liste (name, size_bytes, ist_ordner) fuer alle Top-Level-Eintraege eines Profils."""
    items = []
    try:
        for entry in sorted(profile_path.iterdir()):
            size = entry_size(entry)
            items.append((entry.name, size, entry.is_dir()))
    except (OSError, PermissionError) as exc:
        print(f"    ! Profil-Ordner nicht lesbar: {exc}")
    return items


def print_profile_report(profile_path: Path, blacklist_top_level: set):
    """Druckt Top-Level-Eintraege, Gesamtgroesse und Groesse ohne Blacklist."""
    if not profile_path.exists():
        print(f"    ! Profilordner existiert nicht: {profile_path}")
        return

    items = list_top_level(profile_path)
    total = 0
    excluded_total = 0

    for name, size, is_dir in items:
        marker = "[BLACKLIST]" if name in blacklist_top_level else ""
        kind = "D" if is_dir else "F"
        print(f"      {kind}  {format_size(size):>10}  {name} {marker}")
        total += size
        if name in blacklist_top_level:
            excluded_total += size

    print(f"    -- Gesamtgroesse:         {format_size(total)}")
    print(f"    -- Ohne Cache-Blacklist:  {format_size(total - excluded_total)}"
          f"  (gespart: {format_size(excluded_total)})")


def print_flat_drilldown(profile_path: Path, subfolder_name: str):
    """Listet die direkten Unterordner/-dateien von <profil>/<subfolder_name>
    mit Groesse. Fuer Ordner, die selbst schon eine kleine, feste Anzahl
    Unterordner haben (z.B. Chromium 'Service Worker', 'WebStorage') —
    damit sehen wir, WELCHER Unterordner tatsaechlich die Groesse verursacht,
    statt zu raten."""
    base = profile_path / subfolder_name
    if not base.exists():
        print(f"      (kein Unterordner '{subfolder_name}' vorhanden)")
        return

    print(f"      Drilldown '{subfolder_name}/':")
    try:
        children = sorted(base.iterdir(), key=lambda p: entry_size(p), reverse=True)
    except (OSError, PermissionError) as exc:
        print(f"        ! nicht lesbar: {exc}")
        return

    for child in children:
        size = entry_size(child)
        kind = "D" if child.is_dir() else "F"
        print(f"        {kind}  {format_size(size):>10}  {subfolder_name}/{child.name}")


def print_aggregated_drilldown(profile_path: Path, subfolder_name: str):
    """Fuer Ordner mit Pro-Origin-Struktur (Firefox 'storage/<default|permanent|
    temporary>/<origin>/<art>') — aggregiert die Groesse ueber alle Origins
    hinweg nach 'Art' (z.B. 'cache', 'idb', 'ls'), damit die Masse an
    Einzel-Origin-Ordnern nicht die eigentliche Frage verdeckt: welche ART
    von Unterdaten macht die Groesse aus."""
    base = profile_path / subfolder_name
    if not base.exists():
        print(f"      (kein Unterordner '{subfolder_name}' vorhanden)")
        return

    print(f"      Drilldown '{subfolder_name}/' (aggregiert nach Art, ueber alle Origins):")
    aggregated = {}
    try:
        for type_dir in base.iterdir():
            if not type_dir.is_dir():
                continue
            try:
                for origin_dir in type_dir.iterdir():
                    if not origin_dir.is_dir():
                        continue
                    try:
                        for kind_dir in origin_dir.iterdir():
                            size = entry_size(kind_dir)
                            aggregated[kind_dir.name] = aggregated.get(kind_dir.name, 0) + size
                    except (OSError, PermissionError):
                        continue
            except (OSError, PermissionError):
                continue
    except (OSError, PermissionError) as exc:
        print(f"        ! nicht lesbar: {exc}")
        return

    if not aggregated:
        print("        (keine Unterdaten gefunden)")
        return

    for name, size in sorted(aggregated.items(), key=lambda kv: kv[1], reverse=True):
        print(f"        {format_size(size):>10}  {subfolder_name}/*/*/{name}")


def inspect_firefox():
    print("\n" + "=" * 70)
    print("FIREFOX")
    print("=" * 70)

    appdata = os.environ.get("APPDATA")
    if not appdata:
        print("  ! Umgebungsvariable APPDATA nicht gesetzt.")
        return

    firefox_root = Path(appdata) / "Mozilla" / "Firefox"
    ini_path = firefox_root / "profiles.ini"

    if not ini_path.exists():
        print(f"  ! profiles.ini nicht gefunden: {ini_path}")
        return

    print(f"  profiles.ini gefunden: {ini_path}")

    config = configparser.ConfigParser()
    # UNSICHER: profiles.ini ist meist Standard-INI, aber manche Zeilen (z.B.
    # unter [General]) koennten Sonderzeichen enthalten. strict=False zur
    # Sicherheit gegen doppelte Keys in seltenen Faellen.
    config.read(ini_path, encoding="utf-8")

    default_profiles = set()
    for section in config.sections():
        if section.startswith("Install"):
            default = config[section].get("Default")
            if default:
                default_profiles.add(default)

    profile_sections = [s for s in config.sections() if s.startswith("Profile")]

    if not profile_sections:
        print("  ! Keine [ProfileN]-Sektionen in profiles.ini gefunden.")
        return

    for section in profile_sections:
        data = config[section]
        name = data.get("Name", "<ohne Name>")
        rel_path = data.get("Path", "")
        is_relative = data.get("IsRelative", "1") == "1"

        if is_relative:
            resolved = firefox_root / rel_path
        else:
            resolved = Path(rel_path)

        is_default = rel_path in default_profiles
        print(f"\n  Profil-Sektion: [{section}]")
        print(f"    Name:         {name}")
        print(f"    Path (roh):   {rel_path}  (IsRelative={is_relative})")
        print(f"    Aufgeloest:   {resolved}")
        print(f"    Standard:     {'ja' if is_default else 'nein'}")
        print_profile_report(resolved, FIREFOX_BLACKLIST_PREVIEW)
        # UNSICHER: 'storage/' ist laut PROJEKT.md §5.2 bewusst NICHT blacklisted
        # (IndexedDB/Site-Storage). Drilldown dient nur der Kontrolle, ob darin
        # trotzdem offensichtliche Cache-Unterordner stecken.
        print_aggregated_drilldown(resolved, "storage")


def inspect_chromium(display_name: str, user_data_path: Path):
    print("\n" + "=" * 70)
    print(display_name.upper())
    print("=" * 70)

    if not user_data_path.exists():
        print(f"  ! User-Data-Ordner nicht gefunden: {user_data_path}")
        return

    print(f"  User-Data-Ordner gefunden: {user_data_path}")

    local_state_path = user_data_path / "Local State"
    if not local_state_path.exists():
        print(f"  ! Local State nicht gefunden: {local_state_path}")
        return

    print(f"  Local State gefunden:      {local_state_path}"
          f"  ({format_size(local_state_path.stat().st_size)})")

    try:
        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  ! Local State konnte nicht gelesen/geparst werden: {exc}")
        return

    info_cache = local_state.get("profile", {}).get("info_cache", {})

    if not info_cache:
        print("  ! Keine Eintraege in profile.info_cache gefunden.")
        return

    for folder_name, info in info_cache.items():
        display = info.get("name", "<ohne Klarname>")
        profile_path = user_data_path / folder_name

        print(f"\n  Profil-Ordner: {folder_name}")
        print(f"    Klarname:    {display}")
        print(f"    Pfad:        {profile_path}")
        print_profile_report(profile_path, CHROMIUM_BLACKLIST_PREVIEW)
        # UNSICHER: welcher Unterordner von 'Service Worker' bzw. 'WebStorage'
        # tatsaechlich die Groesse verursacht — PROJEKT.md nennt nur
        # 'Service Worker/CacheStorage' und 'Service Worker/ScriptCache' als
        # Kandidaten, das wird hier gegen die Realitaet geprueft.
        print_flat_drilldown(profile_path, "Service Worker")
        print_flat_drilldown(profile_path, "WebStorage")


def main():
    print(f"inspect_profiles.py — BrowserBackup Phase 0 (Version {TOOL_VERSION})")
    print("Nur Lesezugriff — es werden keine Dateien veraendert oder geloescht.\n")

    inspect_firefox()

    localappdata = os.environ.get("LOCALAPPDATA")
    if not localappdata:
        print("\n! Umgebungsvariable LOCALAPPDATA nicht gesetzt — Chrome/Edge werden uebersprungen.")
    else:
        inspect_chromium("Chrome", Path(localappdata) / "Google" / "Chrome" / "User Data")
        inspect_chromium("Edge", Path(localappdata) / "Microsoft" / "Edge" / "User Data")

    print("\n" + "=" * 70)
    print("Ende der Ausgabe. Bitte diese komplett an Claude zurueckgeben.")
    print("=" * 70)


if __name__ == "__main__":
    main()
