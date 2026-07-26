# BrowserBackup

Portables Windows-Tool zum Sichern und Wiederherstellen von Browser-Profilen
(Firefox, Chrome, Edge, Brave, Vivaldi, Opera, Opera GX, Ecosia). Kein
Installer, keine Adminrechte noetig.

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
  eigenen ZIP-Datei (`browserbackup_<browser>_<profil>_<datum_zeit>.zip`).
- **Wiederherstellen:** mehrere Backup-ZIPs auf einmal auswaehlen, werden
  automatisch anhand des Manifests dem passenden installierten Browser/
  Profil zugeordnet. Ziel-Profil pro Zeile per Dropdown anpassbar.
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

Falls `dist\BrowserBackup.exe` bereits gebaut wurde (siehe unten):
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
  `gmp-widevinecdm/`) — Details in `FORTSCHRITT.md`.
- Brave/Vivaldi/Opera GX sind ueber denselben Mechanismus wie Chrome/Edge
  eingebunden, aber nicht auf einer echten Installation verifiziert
  (siehe Kommentare in `core/browsers.py`).
- `restore.py` konnte aus Vorsicht nicht gegen ein echtes Profil getestet
  werden (siehe `FORTSCHRITT.md`, Abschnitt „Zurueckgestellt").

---

## Build als portable .exe (PyInstaller)

```powershell
pip install -r requirements-dev.txt
pyinstaller --onefile --windowed --name BrowserBackup --collect-all customtkinter main.py
```

Oder einfach `.\build.ps1` ausfuehren.

Ergebnis: `dist\BrowserBackup.exe` — eine einzelne, portable Datei.

**Warum `--collect-all customtkinter`?** customtkinter liefert eigene
Theme-/Asset-Dateien (JSON, Fonts) aus, die PyInstaller ohne dieses Flag
nicht automatisch mitnimmt — die .exe wuerde sonst mit einem Theme-Fehler
abstuerzen. `psutil` braucht kein zusaetzliches Flag (PyInstaller-Hook ist
eingebaut).

Der Build wurde getestet: die erzeugte `.exe` startet fehlerfrei.

---

## Projektstruktur

```
core/                Kernlogik, GUI-unabhaengig, einzeln testbar
  browsers.py         Browser-/Profil-Erkennung
  blacklist.py         Cache-Ausschlussliste
  backup.py             ZIP-Sicherung
  restore.py             ZIP-Wiederherstellung
  processes.py            Browser-Prozess-Check/-Beenden
gui/                  customtkinter-Oberflaeche
  app.py               Hauptfenster
  backup_tab.py          Sichern-Tab
  restore_tab.py          Wiederherstellen-Tab
  worker.py                Thread + Queue fuer Fortschritt
  dialogs.py                 Wiederverwendete Dialoge
main.py               Einstiegspunkt
inspect_profiles.py   Phase-0-Hilfsskript (nur Lesezugriff, zur Blacklist-Herleitung)
PROJEKT.md            Vollstaendige Spezifikation
FORTSCHRITT.md        Verlauf: erledigt / offen / Annahmen je Phase
```

---

## Sicherheit & Datenschutz

- Das Tool selbst sendet nichts uebers Netzwerk, alle Operationen sind rein
  lokal (Dateisystem).
- Backup-ZIPs enthalten Zugangsdaten (Cookies, ggf. Passwoerter) — wie jedes
  Browser-Profil-Backup entsprechend sicher aufbewahren.
