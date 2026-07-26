# FORTSCHRITT — BrowserBackup

## Phase 0 — Realitaets-Check der Profilstrukturen

**Status:** Skript geschrieben, wartet auf Ausfuehrung durch Mike.

### Erledigt
- `inspect_profiles.py` erstellt: liest Firefox (`profiles.ini`) sowie
  Chrome/Edge (`Local State` → `profile.info_cache`), listet Top-Level-Eintraege
  je Profil mit Groesse, Gesamtgroesse und Groesse ohne Cache-Blacklist-Vorschau.
  Nur Lesezugriff, keine Aenderungen am System.
- `PHASE0_NOTIZEN.md` erstellt: Ablauf zur Blacklist-Verifikation +
  Empfehlung zur offenen Frage "Restore: neues Profil anlegen in v1?".
- Git-Repository initialisiert.

### Offen
- Mike fuehrt `python inspect_profiles.py` aus und gibt die Ausgabe zurueck.
- Danach: Blacklist in `core/blacklist.py` (Phase 1) final ableiten (nicht raten).
- Entscheidung bestaetigen: v1 unterstuetzt beim Restore nur "vorhandenes
  Profil ueberschreiben" (Empfehlung in `PHASE0_NOTIZEN.md`), "neues Profil
  anlegen" auf v1.1 verschieben — wartet auf Bestaetigung.
- Danach Start Phase 1 (Kernlogik `core/`).

### Getroffene Annahmen (Phase 0)
- `configparser` mit UTF-8 fuer `profiles.ini` (siehe `PHASE0_NOTIZEN.md`).
- Chromium-Blacklist-Vorschau im Skript ist nur Top-Level; Pfadmuster wie
  `Service Worker/CacheStorage` werden erst in Phase 0-Interpretation bzw.
  Phase 1 (`core/blacklist.py`) beruecksichtigt.
- Es wird von Standard-Installationspfaden ausgegangen (kein Microsoft-Store-
  Chrome o.ae. gesondert behandelt) — zeigt sich in der realen Ausgabe.
