# Phase 0 — Notizen & offene Entscheidungen

## Zweck dieser Datei

`inspect_profiles.py` liest **nur lokal bei Mike** die realen Profilstrukturen
von Firefox/Chrome/Edge aus (Top-Level-Eintraege + Groessen, mit/ohne
Cache-Blacklist-Vorschau). Die hier vorgeschlagene Blacklist ist ein
**Startwert aus PROJEKT.md §5.1** und wird **nicht** vor Erhalt der echten
Ausgabe finalisiert.

## Ablauf

1. Mike fuehrt aus: `python inspect_profiles.py`
2. Ausgabe wird komplett zurueckgegeben (Copy/Paste).
3. Gemeinsam wird geprueft:
   - Existieren die vorgeschlagenen Blacklist-Ordner tatsaechlich?
   - Gibt es zusaetzliche grosse Cache-artige Ordner, die noch fehlen?
   - Gibt es Ordner in der Blacklist, die auf diesem System gar nicht existieren
     (harmlos, aber gut zu wissen)?
4. Blacklist in `core/blacklist.py` (Phase 1) wird danach final festgelegt.

## Offene Design-Frage: Restore — "Neues Profil anlegen" in v1?

**Kontext (PROJEKT.md §9):**
- Firefox: neues Profil = neue `[ProfileN]`-Sektion in `profiles.ini` + neuer
  Profilordner. Vergleichsweise einfach, da `profiles.ini` ein simples INI-Format
  ist und wir die Struktur bereits beim Lesen verstehen.
- Chromium: neues Profil = neuer `Profile N`-Ordner **und** ein korrekter
  Eintrag in `Local State` → `profile.info_cache.<ordner>` mit u.a. `name`,
  `user_name`, `is_using_default_name` etc. Der genaue Pflichtfeld-Umfang ist
  intern (nicht offiziell dokumentiert) und versionsabhaengig — ein falsch
  befuellter `info_cache`-Eintrag kann dazu fuehren, dass Chrome/Edge das
  Profil beim naechsten Start ignoriert, umbenennt oder das Profilmenue
  inkonsistent anzeigt.

**Empfehlung:** Fuer v1 **nur "vorhandenes Profil ueberschreiben"** unterstuetzen.
"Neues Profil anlegen" auf v1.1 verschieben.

**Begruendung:**
- Firefox-seitig waere "neu anlegen" zwar machbar, aber wenn wir es nur fuer
  Firefox bauen und bei Chromium verweigern, entsteht eine inkonsistente GUI
  (Radio-Option, die je nach Browser mal geht, mal nicht) — mehr Verwirrung als
  Nutzen fuer v1.
- Das Risiko eines beschaedigten `info_cache`-Eintrags bei Chromium (PROJEKT.md
  §9, offene Design-Frage) ist genau die Art von "raten statt pruefen", die wir
  vermeiden wollen. Ohne Testreihe gegen mehrere Chrome/Edge-Versionen ist das
  Risiko fuer ein Kunden-/Produktivtool zu hoch.
- "Vorhandenes Profil ueberschreiben" deckt den mit Abstand haeufigsten
  Anwendungsfall ab (Wechsel auf neuen PC, Wiederherstellung nach Neuinstallation
  ins frische Standardprofil).

**Status:** ✅ Bestaetigt von Mike (2026-07-26). v1 unterstuetzt beim Restore
nur "vorhandenes Profil ueberschreiben". "Neues Profil anlegen" wird als
Punkt fuer v1.1 in `FORTSCHRITT.md` gefuehrt.

## Finale Blacklist (aus echten Messungen auf Mikes System abgeleitet)

Quelle: zwei Laeufe von `inspect_profiles.py` (Top-Level + Drilldown fuer
`storage`, `Service Worker`, `WebStorage`) am 2026-07-26.

### Firefox (relativ zum Profilordner)

Top-Level, bestaetigt vorhanden:
- `crashes/` (66 B), `datareporting/` (6,3 MB), `minidumps/` (0 B),
  `parent.lock` (0 B), `shader-cache/` (693,3 KB)

Top-Level, auf diesem System NICHT vorhanden, aber als Kompatibilitaets-
Eintrag fuer aeltere Firefox-Versionen beibehalten (Firefox verlagert den
Haupt-Cache seit einigen Versionen nach `%LOCALAPPDATA%`, ausserhalb des
hier gesicherten Roaming-Profils):
- `cache2/`, `startupCache/`, `thumbnails/`, `OfflineCache/`, `.parentlock`, `lock`

**Neu, per Pfadmuster (nicht Top-Level!) — durch Drilldown bestaetigt:**
- `storage/*/*/cache` (Muster: `storage/<default|permanent|temporary>/<origin>/cache`)
  → 183,1 MB von 230,2 MB im `storage`-Ordner sind dieser Cache-Typ.
  Die Geschwister `idb`, `ls`, `fs`, `.metadata-v2` bleiben **erhalten**
  (echte Website-/Login-Daten, keine Cache-Muster).

**Bewusst NICHT ausgeschlossen (konservative Entscheidung, siehe unten):**
- `gmp-widevinecdm/` (21,6 MB), `gmp-gmpopenh264/` (1,1 MB) — DRM-/Codec-
  Plugins, redownloadbar, aber nicht cache-benannt.

### Chromium — Chrome/Edge (relativ zum Profilordner)

Top-Level, bestaetigt vorhanden:
- `Cache/`, `Code Cache/`, `GPUCache/`

Top-Level, neu entdeckt (in PROJEKT.md-Startliste gefehlt, eindeutig
cache-benannt):
- `DawnGraphiteCache/`, `DawnWebGPUCache/`

Top-Level, auf aktuellen Chrome/Edge-Versionen NICHT mehr vorhanden, aber
als Kompatibilitaets-Eintrag fuer aeltere Versionen beibehalten:
- `GrShaderCache/`, `ShaderCache/`, `Media Cache/`, `Application Cache/`,
  `component_crx_cache/`, `Crashpad/`

**Neu, per Pfadmuster — durch Drilldown bestaetigt:**
- `Service Worker/CacheStorage/` (265,3 MB von 274,6 MB bei aktivem Profil,
  75,7 MB von 80,8 MB bei Edge — der dominante Anteil)
- `Service Worker/ScriptCache/` (9,3 MB / 5,0 MB)
- `Service Worker/Database/` bleibt **erhalten** (Service-Worker-
  Registrierungen, nur ~100 KB, essenziell fuer Funktion)

**Bewusst NICHT ausgeschlossen (konservative Entscheidung):**
- `WebStorage/` — bei Mikes aktivem Chrome-Profil 326,7 MB in einem
  einzigen Origin-Unterordner. Nicht cache-benannt, Semantik nicht
  abschliessend verifiziert (quota-verwaltete Site-Storage, koennte auch
  echte IndexedDB-aehnliche Nutzung einer PWA sein). Groesster Posten,
  der Backups aufblaeht — als v1.1-Kandidat vermerkt.
- `load_statistics.db` (+ `-wal`/`-shm`, ~36,5 MB bei Edge) — Chromiums
  Prefetch-Vorhersage-Datenbank, regenerierbar, aber nicht cache-benannt.
- `EntityExtraction/` (8,4 MB, Edge-spezifisch) — Einordnung unklar.

**Entscheidung (2026-07-26, Mike):** Konservative Blacklist fuer v1 — nur
eindeutig als Cache identifizierbare Ordner/Muster ausschliessen. Die vier
oben genannten unklaren, teils grossen Ordner bleiben vorerst im Backup;
Grund und Groessenangabe stehen in `FORTSCHRITT.md` als v1.1-Kandidaten.

## Sonstige Annahmen aus dieser Phase (siehe auch `# ANNAHME:` im Code)

- `profiles.ini`-Parsing nutzt `configparser` mit UTF-8; Sonderzeichen in
  Profilnamen werden nicht separat behandelt (Standardverhalten von
  `configparser`).
- Chromium-Blacklist-Vorschau enthaelt nur Top-Level-Ordnernamen. Die in
  PROJEKT.md genannten Pfade `Service Worker/CacheStorage` und
  `Service Worker/ScriptCache` liegen eine Ebene tiefer — dafuer muss die
  finale Blacklist in `core/blacklist.py` Pfadmuster (nicht nur Namen)
  unterstuetzen. Wird in Phase 1 beruecksichtigt.
- Es wird nur `Local State` im `User Data`-Root erwartet; abweichende
  Installationsarten (z. B. Chrome aus dem Microsoft Store) werden nicht
  gesondert behandelt, falls sie einen anderen Pfad nutzen sollten — das
  zeigt sich in der realen Ausgabe.
