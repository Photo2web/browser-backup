# PROJEKT: BrowserBackup

Portables Windows-Tool (GUI) zum Sichern und Wiederherstellen von Browser-Profilen.
Arbeitstitel – umbenennbar.

---

## 1. Ziel

Ein portables Python-Programm (als `.exe` lauffähig, ohne Installation), das komplette
Browser-Profile (Firefox + Chromium-basiert) als ZIP sichert und auf einem anderen PC
wiederherstellt. Profile sind bei Sicherung **und** Wiederherstellung auswählbar,
inklusive der Wahl des Ziel-Profils.

---

## 2. Rahmenbedingungen / Technische Vorgaben

- **Sprache:** Python 3.11+
- **GUI:** `customtkinter` (Stil wie Fritz Monitor / DXF-Converter)
- **Packaging:** PyInstaller `--onefile --windowed`, portable Einzel-EXE
- **ZIP:** ausschließlich `zipfile` aus der Standardbibliothek (kein 7-Zip/WinRAR/WinZip nötig)
- **Prozess-Check:** `psutil`
- **Zielplattform:** Windows 10/11
- **Keine Adminrechte** erforderlich (arbeitet nur im Benutzerkontext des angemeldeten Users)

**Externe Abhängigkeiten:** `customtkinter`, `psutil`
**Standardbibliothek:** `zipfile`, `json`, `configparser`, `pathlib`, `os`, `shutil`,
`threading`, `datetime`, `platform`

---

## 3. Unterstützte Browser

| Browser | Profilbasis | Profil-Erkennung |
|---|---|---|
| Firefox | `%APPDATA%\Mozilla\Firefox\` | `profiles.ini` parsen |
| Chrome  | `%LOCALAPPDATA%\Google\Chrome\User Data\` | `Local State` → `profile.info_cache` |
| Edge    | `%LOCALAPPDATA%\Microsoft\Edge\User Data\` | wie Chrome |

**Optional (nur wenn ohne Mehraufwand):** Brave
(`%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data\`), Vivaldi – gleiche Chromium-Logik.
Nicht zwingend für v1.

Browser, deren Basisordner nicht existiert, werden im GUI ausgegraut / nicht angeboten.

---

## 4. Profilerkennung im Detail

### 4.1 Firefox
- `profiles.ini` liegt unter `%APPDATA%\Mozilla\Firefox\profiles.ini`
- Sektionen `[ProfileN]` enthalten:
  - `Name=` → Klarname
  - `Path=` → Pfad (relativ zu `Firefox/`, falls `IsRelative=1`; sonst absolut)
- Sektionen `[InstallXXted]` mit `Default=` markieren das Standard-Profil
- Profile liegen typischerweise unter `.../Firefox/Profiles/<hash>.<name>`

### 4.2 Chromium (Chrome/Edge)
- Profil-Ordner heißen `Default`, `Profile 1`, `Profile 2` …
- Die **Klarnamen** stehen in `<User Data>\Local State` →
  JSON-Pfad `profile.info_cache.<ordnername>.name`
- **Wichtig:** `Local State` liegt im `User Data`-Ordner (eine Ebene **über** den Profilen)
  und wird von allen Profilen geteilt.

---

## 5. Sicherungsumfang

**Grundsatz:** Alles außer Cache / temporäre Daten / Lock-Dateien.

### 5.1 Ausschluss-Blacklist (Startwerte – in Phase 0 gegen Realität prüfen!)

**Firefox (Ordner/Dateien, relativ zum Profil):**
```
cache2/            startupCache/      shader-cache/
thumbnails/        OfflineCache/      crashes/
minidumps/         datareporting/     lock
.parentlock        parent.lock
```

**Chromium (Ordner/Dateien, relativ zum Profil):**
```
Cache/                 Code Cache/            GPUCache/
GrShaderCache/         ShaderCache/           Media Cache/
Service Worker/CacheStorage/                  Service Worker/ScriptCache/
Application Cache/     component_crx_cache/   Crashpad/
```

> ⚠️ **Annahme, in Phase 0 verifizieren:** Die exakten Cache-Ordnernamen können je nach
> Browser-Version leicht abweichen. Die Blacklist muss zentral und leicht erweiterbar
> definiert sein (eine Konstante / Config-Struktur, kein hartkodiertes Verstreuen im Code).

### 5.2 Bewusst enthalten (nicht ausschließen!)

**Firefox:** `places.sqlite` (History+Lesezeichen), `favicons.sqlite`, `cookies.sqlite`,
`permissions.sqlite`, `prefs.js`, `logins.json`, `key4.db`, `extensions/`,
`extension-settings.json`, `addonStartup.json.lz4`, `search.json.mozlz4`,
`sessionstore.jsonlz4`, `sessionstore-backups/`, `handlers.json`, `containers.json`,
`storage/` (außer offensichtliche Cache-Unterordner).

**Chromium:** `Bookmarks`, `Preferences`, `Secure Preferences`, `History`, `Favicons`,
`Top Sites`, `Cookies`, `Login Data`, `Web Data`, `Extensions/`,
`Local Extension Settings/`, `Extension State/`, `Extension Rules/`, `Local Storage/`,
`Session Storage/`, `IndexedDB/`.
**Plus** die gemeinsame `Local State` aus dem `User Data`-Ordner (siehe 6.2).

---

## 6. Passwörter & Verschlüsselung — wichtige Design-Entscheidungen

### 6.1 Firefox (portabel)
`logins.json` + `key4.db` werden **beide** gesichert. Firefox nutzt NSS (nicht Windows-DPAPI).
→ Passwörter funktionieren auf dem Zielrechner, solange beide Dateien zusammen wiederhergestellt
werden. Bei gesetztem Primärpasswort wird es auf dem Zielrechner einmal abgefragt.

### 6.2 Chromium (NICHT portabel per Dateikopie)
Passwörter (`Login Data`) und teils Cookies sind mit einem Key verschlüsselt, der in
`Local State` liegt und seinerseits über **Windows-DPAPI** an das Benutzerkonto + den PC
gebunden ist. Auf einem anderen PC / anderen Windows-Konto sind diese Daten **nicht
entschlüsselbar**.

**Konsequenz für das Tool:**
- Die Dateien werden trotzdem mitgesichert (schadet nicht, funktioniert bei gleichem
  Windows-Konto auf demselben PC).
- Das Tool zeigt **im Log und im Ergebnis-Dialog einen deutlichen Hinweis**:
  *"Chromium-Passwörter/Cookies funktionieren nur auf demselben Windows-Konto/PC.
  Für PC-übergreifende Passwörter: Chrome-Sync oder Passwortmanager (z. B. Vaultwarden)."*

### 6.3 `Local State` beim Restore (Chromium-Sonderfall)
`Local State` ist **profilübergreifend**. Ein blindes Überschreiben kann `info_cache`
anderer Profile beschädigen.

**v1-Entscheidung:** Beim Wiederherstellen eines Chromium-Profils fragt das Tool explizit,
ob `Local State` mit übernommen werden soll:
- **Nein (Default):** vorhandene `Local State` des Zielrechners bleibt unangetastet
  (Passwörter sind dann ohnehin nicht portabel → verliert man nichts).
- **Ja:** vor dem Überschreiben wird die vorhandene `Local State` als
  `Local State.bak_<timestamp>` gesichert.

> **Annahme, offen:** Ein selektives Mergen nur des `os_crypt`-Keys wäre sauberer, ist aber
> für v1 out of scope. Als „Nice-to-have“ in FORTSCHRITT.md vermerken.

---

## 7. ZIP-Format & Manifest

- ZIP mit `zipfile.ZIP_DEFLATED`.
- Dateiname-Vorschlag: `browserbackup_<browser>_<profilname>_<YYYY-MM-DD_HHMM>.zip`
- Struktur im ZIP:
  ```
  backup_manifest.json
  profile/            ← der gesamte (gefilterte) Profilinhalt
  local_state/Local State   ← nur bei Chromium, die gemeinsame Datei
  ```
- **`backup_manifest.json`** enthält mindestens:
  ```json
  {
    "tool": "BrowserBackup",
    "tool_version": "1.0.0",
    "created_at": "2026-07-26T14:30:00",
    "browser": "chrome",
    "source_profile_dir": "Profile 1",
    "source_profile_name": "Mike privat",
    "has_local_state": true,
    "excluded_patterns": ["Cache", "Code Cache", "..."],
    "source_host": "PC-NAME",
    "source_os": "Windows 11"
  }
  ```

---

## 8. Ablauf: Sicherung

1. Browser wählen (Dropdown, nur erkannte Browser).
2. Profil wählen (Dropdown mit Klarnamen).
3. Prüfen, ob Browser-Prozess läuft → ggf. Warnung + Angebot „Browser beenden“.
4. Ziel-Ordner für die ZIP wählen.
5. Checkbox „Cache/temporäre Daten ausschließen“ (Default: an).
6. `Sichern` → läuft im Thread, Fortschrittsbalken + Log.
7. Manifest schreiben, ZIP erstellen, bei Chromium `Local State` mit aufnehmen.
8. Gesperrte/unlesbare Dateien einzeln abfangen (try/except), im Log vermerken,
   Sicherung **nicht** komplett abbrechen.
9. Abschluss-Dialog mit Zusammenfassung + Passwort-Hinweis (bei Chromium).

---

## 9. Ablauf: Wiederherstellung

1. ZIP auswählen.
2. Manifest lesen und anzeigen (Quelle: Browser, Profilname, Datum, Quell-PC).
3. Ziel-Browser + Ziel-Profil wählen (Dropdown), **oder** „Neues Profil anlegen“.
4. Modus:
   - **Vorhandenes Profil überschreiben** → vorher automatisches Sicherheits-Backup
     des aktuellen Ziel-Profils (Checkbox, Default an).
   - **Neues Profil anlegen** → für Firefox neuen Profileintrag in `profiles.ini`;
     für Chromium neuen `Profile N`-Ordner + Eintrag in `Local State`.
5. Prüfen, ob Ziel-Browser läuft → Warnung/Beenden.
6. Bei Chromium: Nachfrage zu `Local State` (siehe 6.3).
7. Entpacken ins Ziel-Profil, Fortschritt + Log.
8. Abschluss-Dialog mit Zusammenfassung + ggf. Passwort-Hinweis.

> **Offene Design-Frage für „Neues Profil anlegen“:** Das Anlegen eines *neuen* Chromium-
> Profils erfordert einen korrekten Eintrag in `info_cache` der `Local State`. In Phase 0
> die reale Struktur prüfen und entscheiden, ob v1 nur „vorhandenes überschreiben“
> unterstützt und „neu anlegen“ auf v1.1 verschoben wird. **Explizit markieren.**

---

## 10. GUI-Layout (customtkinter)

- Fenster, zwei Bereiche umschaltbar (Segmented Button oder Tabs):
  **„Sichern“** / **„Wiederherstellen“**
- **Sichern-Tab:** Browser-Dropdown, Profil-Dropdown, Ziel-Ordner-Auswahl,
  Cache-Checkbox, Fortschrittsbalken, Log-Textfeld, Button „Sichern“.
- **Wiederherstellen-Tab:** ZIP-Auswahl, Manifest-Anzeige (read-only),
  Ziel-Browser-Dropdown, Ziel-Profil-Dropdown, Radio „überschreiben / neu anlegen“,
  Sicherheits-Backup-Checkbox, Fortschrittsbalken, Log, Button „Wiederherstellen“.
- Lang laufende Operationen **immer im Thread**; GUI-Updates über `after()` oder Queue.
- Dark-Theme passend zum bestehenden Tool-Stil.

---

## 11. Nicht-Ziele (v1)

- Kein selektives Mergen einzelner DPAPI-Keys.
- Keine Portabilität von Chromium-Passwörtern zwischen verschiedenen Windows-Konten
  (technisch nicht per Dateikopie möglich).
- Keine Linux/macOS-Unterstützung (Fokus Windows).
- Kein Sync/Cloud.

---

## 12. Konventionen

- **Git-Checkpoints** nach jeder abgeschlossenen Phase.
- **FORTSCHRITT.md** mitführen (Was erledigt, was offen, Annahmen).
- Blacklist zentral und dokumentiert.
- Annahmen und Unsicherheiten im Code kommentieren, nicht stillschweigend raten.
- Version in einer Konstante `TOOL_VERSION`, pro Änderung erhöhen.
