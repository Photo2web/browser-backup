# FORTSCHRITT — BrowserBackup

## Phase 0 — Realitaets-Check der Profilstrukturen

**Status:** ✅ Abgeschlossen (2026-07-26).

### Erledigt
- `inspect_profiles.py` erstellt und zweimal auf Mikes System ausgefuehrt
  (Top-Level-Report + gezielter Drilldown fuer `storage` (Firefox),
  `Service Worker` und `WebStorage` (Chromium)). Nur Lesezugriff.
- Finale Blacklist aus echten Messungen abgeleitet, siehe
  `PHASE0_NOTIZEN.md` (Abschnitt "Finale Blacklist") fuer alle Details
  und Groessenangaben. Kurzfassung:
  - Firefox: `crashes/`, `datareporting/`, `minidumps/`, `parent.lock`,
    `shader-cache/` + Pfadmuster `storage/*/*/cache` (183 MB Fund).
    Kompat-Eintraege fuer aeltere Versionen: `cache2/`, `startupCache/`,
    `thumbnails/`, `OfflineCache/`, `.parentlock`, `lock`.
  - Chromium: `Cache/`, `Code Cache/`, `GPUCache/`, `DawnGraphiteCache/`,
    `DawnWebGPUCache/` + Pfadmuster `Service Worker/CacheStorage/` und
    `Service Worker/ScriptCache/` (zusammen der dominante Grossteil des
    Service-Worker-Ordners). Kompat-Eintraege fuer aeltere Versionen:
    `GrShaderCache/`, `ShaderCache/`, `Media Cache/`, `Application Cache/`,
    `component_crx_cache/`, `Crashpad/`.
- Restore-Entscheidung bestaetigt: v1 unterstuetzt nur "vorhandenes
  Profil ueberschreiben" (siehe `PHASE0_NOTIZEN.md`).
- Blacklist-Umfang bestaetigt: konservative Variante (nur eindeutig als
  Cache identifizierte Ordner/Muster).
- Git-Repository initialisiert, Phase 0 committet.

### Offen (fuer Phase 1)
- `core/blacklist.py` mit der oben genannten finalen Blacklist inkl.
  Pfadmuster-Unterstuetzung (nicht nur Top-Level-Namen) implementieren.
- `core/browsers.py`, `core/backup.py`, `core/restore.py`,
  `core/processes.py` gemaess PROJEKT.md §Phase 1 bauen.
- Manuelle Testlaeufe fuer `browsers.py` und `backup.py`.

### Auf v1.1 verschoben (bewusst, nicht vergessen)
- Restore: "Neues Profil anlegen" (Firefox `profiles.ini`-Eintrag +
  Chromium `info_cache`-Erzeugung) — Risiko eines beschaedigten Profils
  ohne Testreihe zu hoch fuer v1.
- Pruefen, ob folgende grosse, nicht eindeutig cache-benannte Ordner
  in einer spaeteren Version doch ausgeschlossen werden sollten:
  - Chromium `WebStorage/` (bei Mike bis zu 326,7 MB in einem Origin-Ordner)
  - Firefox `gmp-widevinecdm/` (21,6 MB), `gmp-gmpopenh264/` (1,1 MB)
  - Chromium `load_statistics.db` (+`-wal`/`-shm`, ~36,5 MB bei Edge)
  - Edge `EntityExtraction/` (8,4 MB)
- Selektives Mergen einzelner DPAPI-/`os_crypt`-Keys bei Chromium-Restore
  (bereits in PROJEKT.md §6.3 als Nice-to-have vermerkt).

### Getroffene Annahmen (Phase 0)
- `configparser` mit UTF-8 fuer `profiles.ini`.
- Es wird von Standard-Installationspfaden ausgegangen (kein Microsoft-
  Store-Chrome o.ae. gesondert behandelt) — auf Mikes System nicht
  aufgetreten, bleibt eine Annahme fuer andere Systeme.
- Firefox-Cache-Ordner (`cache2` etc.) koennen je nach Firefox-Version im
  Roaming-Profil ODER unter `%LOCALAPPDATA%` liegen. v1 sichert nur das
  Roaming-Profil (wie in PROJEKT.md §4.1 spezifiziert) — der ausgelagerte
  lokale Cache wird dadurch ohnehin nie mitgesichert, das ist gewuenscht.
