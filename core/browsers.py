"""
browsers.py — Erkennung installierter Browser und ihrer Profile.

Firefox: %APPDATA%\\Mozilla\\Firefox\\profiles.ini
Chromium-Familie (Chrome, Edge, Brave, Vivaldi, Opera, Ecosia, ...):
    <User-Data-Ordner>\\Local State (JSON) -> profile.info_cache
    Chrome/Edge/Brave/Vivaldi/Ecosia liegen unter %LOCALAPPDATA%\\<Hersteller>\\<Produkt>\\User Data
    Opera liegt (anders als die meisten!) direkt unter %APPDATA%\\Opera Software\\<Produkt>,
    ohne "User Data"-Zwischenordner — der Ordner selbst uebernimmt diese Rolle.

Chrome/Edge/Firefox/Opera/Ecosia wurden gegen reale Installationen auf
Mikes System geprueft (siehe PHASE0_NOTIZEN.md sowie Verifikation am
2026-07-26). Brave/Vivaldi nutzen denselben, generischen Chromium-
Mechanismus (detect_chromium()), sind aber NICHT auf einer echten
Installation verifiziert — die Ordnernamen sind gut dokumentierte
Chromium-Standardpfade, sollten aber bei Bedarf per
`python -m core.browsers` gegengeprueft werden.
"""

import configparser
import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Profile:
    """Ein einzelnes Browserprofil."""

    id: str            # Firefox: relativer Pfad aus profiles.ini; Chromium: Ordnername ("Default", "Profile 1", ...)
    name: str          # Klarname fuer die GUI (Firefox: Name=; Chromium: info_cache.<id>.name)
    path: Path         # aufgeloester, absoluter Pfad zum Profilordner
    is_default: bool = False


@dataclass
class Browser:
    """Ein erkannter Browser mit seinen Profilen."""

    key: str            # "firefox" | "chrome" | "edge" — interner Schluessel, u.a. fuer blacklist.py und processes.py
    display_name: str   # Anzeigename fuer die GUI ("Firefox", "Chrome", "Edge")
    profiles: list[Profile] = field(default_factory=list)
    local_state_path: Path | None = None  # nur Chromium: gemeinsame "Local State"-Datei im User-Data-Root


def detect_firefox() -> Browser | None:
    """Erkennt Firefox ueber profiles.ini. Gibt None zurueck, wenn Firefox
    nicht installiert ist oder keine Profile gefunden wurden."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None

    firefox_root = Path(appdata) / "Mozilla" / "Firefox"
    ini_path = firefox_root / "profiles.ini"
    if not ini_path.exists():
        return None

    config = configparser.ConfigParser()
    try:
        config.read(ini_path, encoding="utf-8")
    except configparser.Error:
        return None

    default_profiles = set()
    for section in config.sections():
        if section.startswith("Install"):
            default = config[section].get("Default")
            if default:
                default_profiles.add(default)

    profiles: list[Profile] = []
    for section in config.sections():
        if not section.startswith("Profile"):
            continue
        data = config[section]
        rel_path = data.get("Path", "")
        if not rel_path:
            continue
        name = data.get("Name", section)
        is_relative = data.get("IsRelative", "1") == "1"
        resolved = (firefox_root / rel_path) if is_relative else Path(rel_path)

        profiles.append(
            Profile(
                id=rel_path,
                name=name,
                path=resolved,
                is_default=(rel_path in default_profiles),
            )
        )

    if not profiles:
        return None

    return Browser(key="firefox", display_name="Firefox", profiles=profiles)


def detect_chromium(key: str, display_name: str, user_data_path: Path) -> Browser | None:
    """Erkennt einen Chromium-basierten Browser ueber
    <User Data>/Local State -> profile.info_cache. Gibt None zurueck,
    wenn der Browser nicht installiert ist oder Local State nicht
    lesbar/vorhanden ist. Funktioniert fuer jeden Chromium-Fork, der diese
    Konvention nutzt (Chrome, Edge, Brave, Vivaldi, Opera, Ecosia, ...) —
    user_data_path zeigt bei Opera direkt auf den Produktordner (kein
    "User Data"-Zwischenordner), bei den anderen auf "<Produkt>\\User Data"."""
    if not user_data_path.exists():
        return None

    local_state_path = user_data_path / "Local State"
    if not local_state_path.exists():
        return None

    try:
        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    info_cache = local_state.get("profile", {}).get("info_cache", {})
    if not info_cache:
        return None

    profiles = [
        Profile(
            id=folder_name,
            # "or folder_name" statt nur .get(..., folder_name): manche
            # Chromium-Forks (z.B. Opera) tragen einen LEEREN String als
            # "name" ein, .get() greift dann nicht auf den Default-Wert zurueck.
            name=info.get("name") or folder_name,
            path=user_data_path / folder_name,
            is_default=(folder_name == "Default"),
        )
        for folder_name, info in info_cache.items()
        # UNSICHER/beobachtet (Opera): info_cache kann verwaiste Eintraege
        # enthalten, deren Profilordner gar nicht (mehr) existiert. Diese
        # werden nicht angezeigt, um Phantom-Profile in der GUI zu vermeiden.
        if (user_data_path / folder_name).is_dir()
    ]

    return Browser(
        key=key,
        display_name=display_name,
        profiles=profiles,
        local_state_path=local_state_path,
    )


# Chromium-Familie unter %LOCALAPPDATA%\<Hersteller>\<Produkt>\User Data.
# Neue Chromium-basierte Browser aufnehmen = hier eine Zeile ergaenzen,
# detect_chromium() ist bereits generisch.
_LOCALAPPDATA_CHROMIUM_BROWSERS = (
    ("chrome", "Chrome", ("Google", "Chrome")),
    ("edge", "Edge", ("Microsoft", "Edge")),
    ("brave", "Brave", ("BraveSoftware", "Brave-Browser")),
    ("vivaldi", "Vivaldi", ("Vivaldi",)),
    ("ecosia", "Ecosia", ("EcosiaBrowser",)),  # verifiziert 2026-07-26 auf Mikes System
)

# Opera nutzt %APPDATA% statt %LOCALAPPDATA% und keinen "User Data"-
# Zwischenordner — der Produktordner selbst ist bereits die User-Data-Ebene.
_APPDATA_CHROMIUM_BROWSERS = (
    ("opera", "Opera", ("Opera Software", "Opera Stable")),
    ("opera_gx", "Opera GX", ("Opera Software", "Opera GX Stable")),
)


def detect_browsers() -> list[Browser]:
    """Erkennt alle unterstuetzten, installierten Browser. Nicht gefundene
    Browser werden ausgelassen (GUI zeigt schlicht nur die gefundenen an)."""
    found: list[Browser] = []

    firefox = detect_firefox()
    if firefox:
        found.append(firefox)

    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        localappdata_path = Path(localappdata)
        for key, display_name, path_parts in _LOCALAPPDATA_CHROMIUM_BROWSERS:
            user_data_path = localappdata_path.joinpath(*path_parts, "User Data")
            browser = detect_chromium(key, display_name, user_data_path)
            if browser:
                found.append(browser)

    appdata = os.environ.get("APPDATA")
    if appdata:
        appdata_path = Path(appdata)
        for key, display_name, path_parts in _APPDATA_CHROMIUM_BROWSERS:
            user_data_path = appdata_path.joinpath(*path_parts)
            browser = detect_chromium(key, display_name, user_data_path)
            if browser:
                found.append(browser)

    return found


if __name__ == "__main__":
    # Manueller Testlauf: zeigt alle erkannten Browser + Profile in der Konsole.
    # Aufruf vom Projekt-Root aus: python -m core.browsers
    browsers = detect_browsers()

    if not browsers:
        print("Keine unterstuetzten Browser gefunden.")
    else:
        for browser in browsers:
            print(f"\n{browser.display_name} ({browser.key})")
            if browser.local_state_path:
                print(f"  Local State: {browser.local_state_path}")
            for profile in browser.profiles:
                marker = " [Standard]" if profile.is_default else ""
                print(f"  - {profile.name!r} (id={profile.id!r}){marker}")
                print(f"      Pfad: {profile.path}")
                print(f"      Existiert: {profile.path.exists()}")
