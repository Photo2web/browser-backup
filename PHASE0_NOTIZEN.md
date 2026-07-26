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

**Status:** Empfehlung — wartet auf Bestaetigung durch Mike, bevor GUI (Phase 2)
die Radio-Option "neu anlegen" ggf. ausblendet/deaktiviert.

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
