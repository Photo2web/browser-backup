"""
blacklist.py — zentrale Cache-/Ausschluss-Definition fuer die Sicherung.

Herkunft dieser Werte: Phase 0 (siehe PHASE0_NOTIZEN.md, Abschnitt
"Finale Blacklist"). Zwei reale Messlaeufe von inspect_profiles.py auf
einem produktiven System (Firefox mit 316 MB-Profil, Chrome mit zwei
Profilen bis 871 MB, Edge mit 753 MB) — die Blacklist wurde daraus
abgeleitet, nicht geraten.

Es gibt zwei Arten von Eintraegen:
  - "names": Ordner-/Dateiname, der NUR auf oberster Profil-Ebene greift
             (z.B. "Cache" direkt im Profilordner).
  - "patterns": Pfadmuster (glob, ueber fnmatch) relativ zum Profilordner,
             fuer Faelle wie "Service Worker/CacheStorage", die eine
             Ebene tiefer liegen.

Entscheidung (2026-07-26, Mike): konservative Blacklist — es werden nur
Ordner ausgeschlossen, die eindeutig als Cache identifizierbar sind.
Grosse, aber nicht eindeutig cache-benannte Ordner (WebStorage,
gmp-widevinecdm, load_statistics.db, EntityExtraction) bleiben bewusst
im Backup (siehe FORTSCHRITT.md, Abschnitt "Auf v1.1 verschoben").
"""

import fnmatch

# ANNAHME: cache2/, startupCache/, thumbnails/, OfflineCache/, .parentlock,
# "lock" existierten auf Mikes System NICHT (Firefox lagert den Haupt-Cache
# in aktuellen Versionen nach %LOCALAPPDATA% aus, ausserhalb des hier
# gesicherten Roaming-Profils). Sie bleiben trotzdem in der Blacklist, als
# wirkungsloser Kompatibilitaets-Eintrag fuer aeltere Firefox-Versionen, die
# noch alles im Roaming-Profil halten.
FIREFOX_NAMES = frozenset(
    {
        "cache2",
        "startupCache",
        "shader-cache",       # bestaetigt vorhanden, 693 KB
        "thumbnails",
        "OfflineCache",
        "crashes",            # bestaetigt vorhanden, 66 B
        "minidumps",           # bestaetigt vorhanden, 0 B
        "datareporting",       # bestaetigt vorhanden, 6,3 MB
        "lock",
        ".parentlock",
        "parent.lock",         # bestaetigt vorhanden, 0 B
    }
)

# Bestaetigt per Drilldown: storage/<default|permanent|temporary>/<origin>/cache
# macht 183,1 MB von 230,2 MB im storage-Ordner aus. Die Geschwister-Ordner
# "idb", "ls", "fs", ".metadata-v2" sind KEINE Caches und bleiben erhalten.
FIREFOX_PATTERNS = ("storage/*/*/cache",)


# ANNAHME: GrShaderCache/, ShaderCache/, Media Cache/, Application Cache/,
# component_crx_cache/, Crashpad/ existierten auf Mikes aktueller Chrome-/
# Edge-Version NICHT (vermutlich in neueren Versionen umbenannt/entfernt).
# Bleiben als wirkungsloser Kompatibilitaets-Eintrag fuer aeltere Versionen.
CHROMIUM_NAMES = frozenset(
    {
        "Cache",               # bestaetigt vorhanden, bis 330,7 MB
        "Code Cache",          # bestaetigt vorhanden, bis 221,3 MB
        "GPUCache",            # bestaetigt vorhanden, bis 5,6 MB
        "GrShaderCache",
        "ShaderCache",
        "Media Cache",
        "Application Cache",
        "component_crx_cache",
        "Crashpad",
        "DawnGraphiteCache",   # neu entdeckt in Phase 0, eindeutig Cache
        "DawnWebGPUCache",     # neu entdeckt in Phase 0, eindeutig Cache
    }
)

# Bestaetigt per Drilldown: "Service Worker/CacheStorage" ist der dominante
# Anteil des Service-Worker-Ordners (265,3 von 274,6 MB bzw. 75,7 von 80,8 MB).
# "Service Worker/ScriptCache" ist ebenfalls klar Cache (9,3 MB bzw. 5,0 MB).
# "Service Worker/Database" (Service-Worker-Registrierungen, nur ~100 KB)
# bleibt bewusst erhalten — ist fuer die Funktion der Service Worker noetig.
CHROMIUM_PATTERNS = (
    "Service Worker/CacheStorage",
    "Service Worker/ScriptCache",
)


def _normalize_browser_key(browser_key: str) -> str:
    if browser_key == "firefox":
        return "firefox"
    if browser_key in ("chrome", "edge"):
        return "chromium"
    raise ValueError(f"Unbekannter Browser-Key: {browser_key!r}")


def get_blacklist(browser_key: str) -> tuple[frozenset, tuple]:
    """Gibt (names, patterns) fuer den angegebenen Browser-Key zurueck."""
    normalized = _normalize_browser_key(browser_key)
    if normalized == "firefox":
        return FIREFOX_NAMES, FIREFOX_PATTERNS
    return CHROMIUM_NAMES, CHROMIUM_PATTERNS


def is_excluded(relative_posix_path: str, browser_key: str) -> bool:
    """Prueft, ob ein Pfad (relativ zum Profilordner, posix-Schreibweise
    mit '/' als Trenner) von der Sicherung ausgeschlossen werden soll.

    - Top-Level-Namen (erstes Pfadsegment) werden gegen 'names' geprueft.
    - Der komplette relative Pfad wird zusaetzlich gegen 'patterns' (glob)
      geprueft, fuer tiefer liegende Cache-Ordner wie 'Service Worker/CacheStorage'.
    """
    names, patterns = get_blacklist(browser_key)

    top_level = relative_posix_path.split("/", 1)[0]
    if top_level in names:
        return True

    for pattern in patterns:
        if fnmatch.fnmatch(relative_posix_path, pattern):
            return True

    return False


def excluded_patterns_for_manifest(browser_key: str) -> list[str]:
    """Liste aller Blacklist-Eintraege (Namen + Muster) fuer das Manifest
    (backup_manifest.json -> excluded_patterns)."""
    names, patterns = get_blacklist(browser_key)
    return sorted(names) + list(patterns)
