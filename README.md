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

- **Modus-zuerst-Navigation (v1.3):** Der Startbildschirm zeigt drei grosse
  Karten-Buttons — **Sichern**, **Wiederherstellen**, **Neuinstallation**. Nach
  der Wahl sieht man nur die Funktionen des jeweiligen Modus; ein „‹ Zurueck"-
  Button fuehrt zurueck zum Start. Sichern und Wiederherstellen haben je zwei
  Sub-Reiter `[Browser | Persoenliche Daten]`.
- **Sichern:** Browser-Profile per Checkliste (einzeln oder alle) und/oder die
  persoenlichen Ordner. Man waehlt **ein** gemeinsames Ziel; das Tool legt pro
  Sicherungslauf automatisch einen Ordner mit Zeitstempel an, darin je Modul
  einen Unterordner:

  ```
  <Ziel>/Umzug_2026-07-29_1130/
    ├── Browser/            umzug_<browser>_<profil>_<datum_zeit>.zip
    └── PersoenlicheDaten/  ZIP oder 1:1-Kopie je Ordner
  ```
- **Wiederherstellen:** mehrere Backup-ZIPs auf einmal auswaehlen, werden
  automatisch anhand des Manifests dem passenden installierten Browser/
  Profil zugeordnet. Ziel-Profil pro Zeile per Dropdown anpassbar. Ist der
  Quell-Browser nicht installiert, ist die Zeile gesperrt (kein Leerlauf).
- **Neuinstallation (v1.1):** listet alle installierten Programme (via winget)
  und erzeugt aus der Auswahl eine lesbare Installationsanweisung, ein
  selbst-elevierendes winget-PowerShell-Skript und ein UniGetUI-Bundle, um die
  Programme auf einem neuen Windows-Rechner wieder einzurichten.
- **Persoenliche Daten (v1.2):** sichert die persoenlichen Windows-Ordner
  (Dokumente, Bilder, Musik, Videos, Desktop, Downloads) wahlweise als ZIP oder
  1:1-Kopie und stellt sie wieder her. Bekannt-Ordner werden ueber die
  Windows-API aufgeloest (OneDrive/NextCloud-Umleitung wird beruecksichtigt).
- **Speicherplatz-Pruefung (cluster-genau, v1.3.1):** vor dem Start wird
  geprueft, ob das Ziel gross genug ist — inklusive **Cluster-Verschnitt**
  (jede Datei belegt mindestens einen ganzen Cluster; USB-/exFAT-Platten haben
  oft 128 KB+ grosse Cluster, was bei vielen kleinen Dateien viel Platz kostet).
  Damit meldet das Tool zu wenig Platz *vorher*, statt die Zielplatte mitten in
  der Sicherung volllaufen zu lassen. Der ZIP-Modus braucht dabei deutlich
  weniger Platz als eine 1:1-Kopie.
- **Fortschrittsbalken** mit Prozentzahl und Farbverlauf von Rot (0 %) nach
  Gruen (100 %) — in allen Sicher-/Wiederherstell-Vorgaengen.
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

Beim Start erscheint der **Startbildschirm** mit drei Karten-Buttons. Nach der
Wahl eines Modus fuehrt oben links **„‹ Zurueck"** wieder dorthin zurueck. In
**Sichern** und **Wiederherstellen** wechselt man ueber die Sub-Reiter oben
zwischen **Browser** und **Persoenliche Daten**.

### Sichern

1. Auf dem Startbildschirm **„Sichern"** waehlen.
2. **Einen gemeinsamen Zielordner** waehlen (oben) — dort landet pro Lauf ein
   Ordner `Umzug_<Datum_Zeit>/` mit den Unterordnern `Browser/` und
   `PersoenlicheDaten/`.
3. Sub-Reiter **Browser**: gewuenschte Profile anhaken (oder „Alle auswaehlen");
   „Cache/temporaere Daten ausschliessen" ist standardmaessig an (kleinere
   Backups). Sub-Reiter **Persoenliche Daten**: Ordner anhaken und Format
   waehlen (ZIP oder 1:1-Kopie).
4. „Sichern" klicken. Reicht der Platz am Ziel (inkl. Cluster-Verschnitt) nicht,
   warnt das Tool *vorher*. Laeuft ein betroffener Browser noch, fragt es nach
   (Beenden / Trotzdem fortfahren / Abbrechen).
5. Am Ende erscheint eine Zusammenfassung; bei Chromium-Browsern zusaetzlich
   der Passwort-Hinweis von oben.

### Wiederherstellen

0. Auf dem Startbildschirm **„Wiederherstellen"** waehlen, dann Sub-Reiter
   **Browser** bzw. **Persoenliche Daten**.
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

1. Auf dem Startbildschirm **„Neuinstallation"** waehlen. Es gibt zwei Auswahl-Bereiche:
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
  personal_data.py      Persoenliche Ordner sichern/wiederherstellen (v1.2);
                        Speicherplatz + Cluster-Verschnitt (cluster_size/disk_reservation, v1.3.1)
  runfolder.py          Lauf-Ordner Umzug_<datum>/ mit Modul-Unterordnern (v1.3)
gui/                  customtkinter-Oberflaeche
  app.py                Hauptfenster + Screen-Router (Home <-> Modi)
  home_screen.py        Startbildschirm mit drei Karten-Buttons (v1.3)
  home_icons.py         Zur Laufzeit gezeichnete Icons (Pillow) (v1.3)
  backup_mode.py        Sichern-Modus: gemeinsames Ziel + Sub-Reiter (v1.3)
  restore_mode.py       Wiederherstellen-Modus: Sub-Reiter (v1.3)
  backup_tab.py         Browser sichern (Sub-Reiter)
  restore_tab.py        Browser wiederherstellen (Sub-Reiter)
  reinstall_tab.py      Neuinstallation
  personal_tab.py       Persoenliche Daten: Backup-/Restore-Frame (v1.3-Split)
  progress.py           ColorProgressBar (Prozent + rot->gruen) (v1.3)
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
