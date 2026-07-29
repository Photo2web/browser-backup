# Umzugstool — fuer Windows 10+

Portables Windows-Tool fuer den Rechnerumzug: sichert und stellt
Browser-Profile (Firefox, Chrome, Edge, Brave, Vivaldi, Opera, Opera GX,
Ecosia) sowie persoenliche Daten (Dokumente, Bilder, Musik, Videos, Desktop,
Downloads) wieder her und erstellt eine Installationsanweisung samt Skript
fuer die auf dem alten Rechner installierten Programme (Neuinstallation).
Kein Installer, keine Adminrechte noetig.

---

## ⚠️ Wichtiger Hinweis: Chromium-Passwoerter

**Chromium-basierte Browser (Chrome, Edge, Brave, Vivaldi, Opera, Opera GX,
Ecosia) verschluesseln gespeicherte Passwoerter und teils Cookies mit einem
Schluessel, der ueber Windows-DPAPI an das Benutzerkonto UND den PC gebunden
ist.**

- Diese Daten werden zwar mitgesichert (schadet nicht), sind aber auf einem
  **anderen PC oder unter einem anderen Windows-Konto NICHT entschluesselbar**.
- Funktioniert eine Wiederherstellung **auf demselben PC, demselben
  Windows-Konto**, bleiben die Passwoerter erhalten.
- Fuer PC-uebergreifende Passwoerter: Chrome-Sync (bzw. das Pendant des
  jeweiligen Browsers) oder ein eigenstaendiger Passwortmanager
  (z. B. Vaultwarden) nutzen.

**Firefox ist davon nicht betroffen** — Firefox nutzt NSS statt DPAPI,
`logins.json` + `key4.db` funktionieren auf jedem PC, solange beide Dateien
zusammen wiederhergestellt werden (bei gesetztem Primaerpasswort wird dieses
auf dem Zielrechner einmal abgefragt).

---

## Funktionen

- **Sichern:** beliebige installierte Browser/Profile per Checkliste
  auswaehlen — einzeln oder alle auf einmal. Jedes Profil landet in einer
  eigenen ZIP-Datei (`umzug_<browser>_<profil>_<datum_zeit>.zip`).
- **Wiederherstellen:** mehrere Backup-ZIPs auf einmal auswaehlen, werden
  automatisch anhand des Manifests dem passenden installierten Browser/
  Profil zugeordnet. Ziel-Profil pro Zeile per Dropdown anpassbar.
- **Neuinstallation (v1.1):** listet alle installierten Programme (via winget)
  und erzeugt aus der Auswahl eine lesbare Installationsanweisung, ein
  selbst-elevierendes winget-PowerShell-Skript und ein UniGetUI-Bundle, um die
  Programme auf einem neuen Windows-Rechner wieder einzurichten.
- **Persönliche Daten (v1.2):** sichert die persönlichen Windows-Ordner
  (Dokumente, Bilder, Musik, Videos, Desktop, Downloads) wahlweise als ZIP oder
  1:1-Kopie und stellt sie wieder her. Mit Speicherplatz-Prüfung (Medium +
  Zielrechner) und Fortschrittsbalken. Bekannt-Ordner werden über die
  Windows-API aufgelöst (OneDrive/NextCloud-Umleitung wird berücksichtigt).
- Cache/temporaere Daten werden beim Sichern standardmaessig ausgeschlossen
  (abschaltbar) — siehe `core/blacklist.py` fuer die genaue Liste.
- Vor Sicherung/Wiederherstellung wird geprueft, ob der betroffene Browser
  laeuft, mit Angebot, ihn zu beenden.
- Optionales Sicherheits-Backup des Ziel-Profils vor dem Ueberschreiben.
- Gesperrte/unlesbare Dateien (z. B. weil der Browser doch noch laeuft)
  werden einzeln uebersprungen und im Ergebnis aufgelistet — die Sicherung
  bricht dafuer nicht ab.

---

## Ausfuehren

### Als fertige .exe

Falls `dist\Umzugstool.exe` bereits gebaut wurde (siehe unten):
Doppelklick genuegt, kein Installer, keine Adminrechte noetig.

### Aus dem Quellcode

```powershell
pip install -r requirements.txt
python main.py
```

Voraussetzung: Python 3.11+, Windows 10/11.

---

## Bedienung

### Sichern

1. Oben bei „Zu sichernde Profile" die gewuenschten Browser/Profile
   anhaken (oder „Alle auswaehlen").
2. Zielordner fuer die ZIP-Dateien waehlen.
3. „Cache/temporaere Daten ausschliessen" ist standardmaessig an
   (deutlich kleinere Backups) — bei Bedarf abschalten.
4. „Sichern" klicken. Laeuft einer der betroffenen Browser noch, fragt
   das Tool nach (Beenden / Trotzdem fortfahren / Abbrechen).
5. Am Ende erscheint eine Zusammenfassung; bei Chromium-Browsern zusaetzlich
   der Passwort-Hinweis von oben.

### Wiederherstellen

1. „Backup-ZIPs auswaehlen..." — es koennen mehrere ZIPs auf einmal
   gewaehlt werden.
2. Jede Zeile zeigt den erkannten Ziel-Browser, das vorbelegte Ziel-Profil
   (per Dropdown aenderbar) sowie Quell-Profilname und Erstellungsdatum.
   Ist der Quell-Browser hier nicht installiert, ist die Zeile deaktiviert.
3. Gewuenschte Zeilen anhaken (oder „Alle auswaehlen").
4. „Sicherheits-Backup der Ziel-Profile erstellen" ist standardmaessig an —
   sichert das jeweilige Ziel-Profil vor dem Ueberschreiben zusaetzlich ab.
5. „Local State mit uebernehmen" nur aktivieren, wenn wirklich gewuenscht
   (siehe Passwort-Hinweis oben) — betrifft nur Chromium-Profile, bei denen
   das Backup eine `Local State` enthaelt. Die bisherige `Local State` wird
   dabei automatisch als `Local State.bak_<Zeitstempel>` gesichert.
6. „Wiederherstellen" klicken, im folgenden Dialog die Uebersicht pruefen
   und bestaetigen.

**v1-Einschraenkung:** Es kann nur ein *vorhandenes* Profil ueberschrieben
werden, kein neues Profil angelegt werden (siehe „Bekannte Einschraenkungen"
unten).

### Neuinstallation (Programme auf einem neuen PC)

1. Tab „Neuinstallation" oeffnen. Es gibt zwei Auswahl-Bereiche:
   - **Grundausstattung** — eine feste, kuratierte Liste haeufiger Programme
     (Browser, Acrobat Reader, 7-Zip, VLC, …), sofort waehlbar. Pflege in
     `core/essential_apps.py`.
   - **Installierte Programme** — werden per `winget` geladen
     (**Internetverbindung noetig**). winget-faehige sind automatisch
     installierbar; als „(manuell)" markierte haben kein winget-Paket und
     landen nur in der lesbaren Anleitung.
2. Gewuenschte Programme aus beiden Bereichen anhaken (werden zusammengefuehrt
   und nach winget-Id dedupliziert).
3. Zielordner waehlen und „Dateien erzeugen" klicken. Es entstehen drei Dateien:
   - `Installationsanweisung.md` — lesbare Liste (winget + manuell),
   - `Install-Apps.ps1` — Installationsskript fuer den neuen Rechner,
   - `Apps.ubundle` — UniGetUI-Bundle (in UniGetUI unter *Package Bundles*
     zu importieren).
4. **Direkt installieren:** „Jetzt installieren" startet das erzeugte Skript auf
   *diesem* Rechner (nach Rueckfrage). Sinnvoll also auf dem **neuen** Laptop.
   Alternativ `Install-Apps.ps1` dorthin kopieren und per Rechtsklick „Mit
   PowerShell ausfuehren".
5. Das Skript startet sich selbst mit Administrator-Rechten neu (UAC), prueft
   PowerShell 7+, stellt winget sicher (faengt den „erst Microsoft Store"-Fall
   ab) und installiert die Programme nacheinander. **Internetverbindung noetig.**

**Passwort-Hinweis gilt auch hier nicht:** Es werden keine Anmeldedaten
uebertragen — nur die Programme selbst neu installiert.

---

## Bekannte Einschraenkungen (v1)

- **Kein „Neues Profil anlegen"** beim Wiederherstellen — nur Ueberschreiben
  eines vorhandenen Profils. Grund: Ein neues Chromium-Profil erfordert einen
  korrekten Eintrag in `Local State` → `profile.info_cache`, dessen
  Pflichtfeld-Umfang inoffiziell/versionsabhaengig ist. Ohne Testreihe gegen
  mehrere Chrome/Edge-Versionen war das Risiko eines beschaedigten Profils
  zu hoch fuer v1.
- Einige grosse, aber nicht eindeutig als „Cache" benannte Ordner werden
  bewusst NICHT ausgeschlossen (z. B. Chromium `WebStorage/`, Firefox
  `gmp-widevinecdm/`) — Details in `docs/FORTSCHRITT.md`.
- Brave/Vivaldi/Opera GX sind ueber denselben Mechanismus wie Chrome/Edge
  eingebunden, aber nicht auf einer echten Installation verifiziert
  (siehe Kommentare in `core/browsers.py`).
- `restore.py` konnte aus Vorsicht nicht gegen ein echtes Profil getestet
  werden (siehe `docs/FORTSCHRITT.md`, Abschnitt „Zurueckgestellt").

---

## Build als portable .exe (PyInstaller)

```powershell
pip install -r packaging/requirements-dev.txt
pyinstaller --onefile --windowed --name Umzugstool --icon assets/icon.ico --add-data "assets/icon.ico;assets" --collect-all customtkinter main.py
```

Oder einfach `.\packaging\build.ps1` ausfuehren (aus dem Projekt-Root).

Ergebnis: `dist\Umzugstool.exe` — eine einzelne, portable Datei.

**Warum `--collect-all customtkinter`?** customtkinter liefert eigene
Theme-/Asset-Dateien (JSON, Fonts) aus, die PyInstaller ohne dieses Flag
nicht automatisch mitnimmt — die .exe wuerde sonst mit einem Theme-Fehler
abstuerzen. `psutil` braucht kein zusaetzliches Flag (PyInstaller-Hook ist
eingebaut).

Der Build wurde getestet: die erzeugte `.exe` startet fehlerfrei.

---

## Projektstruktur

```
main.py               Einstiegspunkt
requirements.txt      Laufzeit-Abhaengigkeiten
README.md             Diese Datei
core/                 Kernlogik, GUI-unabhaengig, einzeln testbar
  browsers.py           Browser-/Profil-Erkennung
  blacklist.py          Cache-Ausschlussliste
  backup.py             ZIP-Sicherung
  restore.py            ZIP-Wiederherstellung
  processes.py          Browser-Prozess-Check/-Beenden
  installed_apps.py     Installierte Programme via winget (Neuinstallation)
  installplan.py        Erzeugt Anleitung + PS-Skript + UniGetUI-Bundle; startet Skript
  essential_apps.py     Kuratierte Grundausstattung (feste winget-Liste)
  personal_data.py      Persoenliche Ordner sichern/wiederherstellen (v1.2)
gui/                  customtkinter-Oberflaeche
  app.py                Hauptfenster
  backup_tab.py         Sichern-Tab
  restore_tab.py        Wiederherstellen-Tab
  reinstall_tab.py      Neuinstallation-Tab
  personal_tab.py       Tab "Persoenliche Daten"
  worker.py             Thread + Queue fuer Fortschritt
  dialogs.py            Wiederverwendete Dialoge
tests/                Unit-Tests (python -m unittest discover -s tests)
docs/                 Projektdoku & Spezifikation (nicht Teil der Laufzeit)
  PROJEKT.md            Vollstaendige Spezifikation
  FORTSCHRITT.md        Verlauf: erledigt / offen / Annahmen je Phase
  PHASE0_NOTIZEN.md     Herleitung der Cache-Blacklist (Phase 0)
tools/                Hilfsskripte (nicht Teil der App)
  inspect_profiles.py   Phase-0-Diagnose (nur Lesezugriff, zur Blacklist-Herleitung)
packaging/            Build-Werkzeug fuer die portable .exe
  build.ps1             PyInstaller-Wrapper
  requirements-dev.txt  Build-Abhaengigkeiten (inkl. PyInstaller)
```

---

## Sicherheit & Datenschutz

- Das Tool selbst sendet nichts uebers Netzwerk, alle Operationen sind rein
  lokal (Dateisystem).
- Backup-ZIPs enthalten Zugangsdaten (Cookies, ggf. Passwoerter) — wie jedes
  Browser-Profil-Backup entsprechend sicher aufbewahren.
