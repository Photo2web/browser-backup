"""Erzeugt aus einer Auswahl installierter Programme die drei Ausgabedateien
fuer die Neuinstallation auf einem anderen Windows-Rechner:

1. ``Installationsanweisung.md`` - lesbare Liste (winget-faehig + manuell).
2. ``Install-Apps.ps1``          - selbst-elevierendes winget-Installationsskript.
3. ``Apps.ubundle``              - UniGetUI-Bundle (JSON, Schema export_version 3).

Reine String-/Datei-Erzeugung, GUI-unabhaengig und einzeln testbar.

Das UniGetUI-Bundle-Schema wurde am UniGetUI-Quellcode verifiziert
(SerializableBundle/SerializablePackage): Top-Level ``export_version`` (=3),
``packages`` und ``incompatible_packages``; je Paket ``Id/Name/Version/Source/
ManagerName`` (ManagerName = "Winget", Quelle "winget"/"msstore").
``InstallationOptions``/``Updates`` sind optional und werden weggelassen.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core import TOOL_VERSION
from core.installed_apps import InstalledApp

# Dateinamen der drei Ausgaben.
FILENAME_INSTRUCTIONS = "Installationsanweisung.md"
FILENAME_SCRIPT = "Install-Apps.ps1"
FILENAME_BUNDLE = "Apps.ubundle"

# UniGetUI: Manager-Name laut ManagerProperties.Name (verifiziert am Quellcode).
_UNIGETUI_MANAGER_NAME = "Winget"
# UniGetUI zeigt nicht zuordenbare Programme als "Local PC"-Quelle an.
_UNIGETUI_LOCAL_SOURCE = "Local PC"
_UNIGETUI_INCOMPAT_INFO = (
    "Diese Programme konnten keinem winget-Paket zugeordnet werden und muessen "
    "auf dem Zielrechner manuell installiert werden."
)


@dataclass(frozen=True)
class InstallPlanResult:
    """Ergebnis von :func:`write_install_plan` - die drei erzeugten Pfade + Zahlen."""

    instructions_path: Path
    script_path: Path
    bundle_path: Path
    installable_count: int
    manual_count: int


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _split(apps: list[InstalledApp]) -> tuple[list[InstalledApp], list[InstalledApp]]:
    """Teilt in (winget-faehig, manuell), jeweils alphabetisch nach Name."""
    installable = sorted(
        (a for a in apps if a.winget_installable), key=lambda a: a.name.lower()
    )
    manual = sorted(
        (a for a in apps if not a.winget_installable), key=lambda a: a.name.lower()
    )
    return installable, manual


def _ps_quote(value: str) -> str:
    """Als PowerShell-Single-Quoted-String kodieren (' wird zu '')."""
    return "'" + value.replace("'", "''") + "'"


# ---------------------------------------------------------------------------
# 1. Installationsanweisung (Markdown)
# ---------------------------------------------------------------------------

def build_instruction_markdown(
    apps: list[InstalledApp],
    *,
    tool_version: str = TOOL_VERSION,
    host: str | None = None,
    created: datetime | None = None,
) -> str:
    host = host if host is not None else platform.node()
    created = created if created is not None else datetime.now()
    installable, manual = _split(apps)

    lines: list[str] = [
        f"# Installationsanweisung - erzeugt am {created:%Y-%m-%d %H:%M} mit BrowserBackup {tool_version}",
        "",
        f"Quelle: {host}",
        "",
        "> Hinweis: Die winget-Installation benoetigt eine Internetverbindung.",
        "",
        f"## Automatisch installierbar (winget) - {len(installable)}",
        "",
    ]
    if installable:
        for app in installable:
            lines.append(f"- {app.name} - `{app.package_id}` (Quelle: {app.source})")
    else:
        lines.append("_(keine)_")

    lines += [
        "",
        f"## Manuell zu installieren - {len(manual)}",
        "",
        "Fuer diese Programme wurde kein winget-Paket gefunden - bitte manuell "
        "von der jeweiligen Herstellerseite installieren.",
        "",
    ]
    if manual:
        for app in manual:
            version = f" (Version {app.version})" if app.version else ""
            lines.append(f"- {app.name}{version}")
    else:
        lines.append("_(keine)_")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. PowerShell-Installationsskript
# ---------------------------------------------------------------------------

# Statisches Geruest; __PLATZHALTER__ werden per str.replace ersetzt, damit
# PowerShell-Zeichen wie $ und {} nicht mit Python-Formatierung kollidieren.
_PS_TEMPLATE = r"""<#
    Install-Apps.ps1
    Erzeugt von BrowserBackup __VERSION__ am __CREATED__.

    Installiert die ausgewaehlten Programme via winget auf einem neuen
    Windows-Rechner.

    WICHTIG:
      * Benoetigt eine Internetverbindung.
      * Das Skript startet sich selbst mit Administrator-Rechten neu (UAC-Abfrage).
      * Reihenfolge: PowerShell-7-Pruefung -> winget sicherstellen -> installieren.
#>

$ErrorActionPreference = 'Stop'
# Native Programme (winget) nicht ueber ErrorActionPreference werfen lassen -
# wir werten deren Exit-Code selbst aus.
$PSNativeCommandUseErrorActionPreference = $false

# ------------------------------------------------------------------
# 1. Selbst-Elevation als Administrator
# ------------------------------------------------------------------
$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$istAdmin  = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $istAdmin) {
    Write-Host 'Starte Skript mit Administrator-Rechten neu...' -ForegroundColor Yellow
    try {
        $hostExe = (Get-Process -Id $PID).Path
        Start-Process -FilePath $hostExe -Verb RunAs -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"')
        )
    } catch {
        Write-Host 'Administrator-Rechte wurden verweigert. Abbruch.' -ForegroundColor Red
        exit 1
    }
    exit
}
Write-Host 'Laeuft mit Administrator-Rechten.' -ForegroundColor Green

# ------------------------------------------------------------------
# 2. PowerShell-7-Pruefung (Installation ggf. nach dem winget-Setup)
# ------------------------------------------------------------------
$ps7Vorhanden = [bool](Get-Command pwsh -ErrorAction SilentlyContinue)
if ($ps7Vorhanden) {
    Write-Host 'PowerShell 7+ (pwsh) ist vorhanden.' -ForegroundColor Green
} else {
    Write-Host 'PowerShell 7+ (pwsh) fehlt - wird nach dem winget-Setup installiert.' -ForegroundColor Yellow
}

# ------------------------------------------------------------------
# 3. winget sicherstellen (faengt den "erst Microsoft Store"-Fall ab)
# ------------------------------------------------------------------
function Ensure-WinGet {
    if (Get-Command winget -ErrorAction SilentlyContinue) { return $true }

    Write-Host 'winget nicht gefunden. Registriere den App-Installer neu...' -ForegroundColor Yellow
    try {
        Add-AppxPackage -RegisterByFamilyName -MainPackage Microsoft.DesktopAppInstaller_8wekyb3d8bbwe -ErrorAction Stop
    } catch {
        Write-Host '  Registrierung fehlgeschlagen.' -ForegroundColor DarkYellow
    }
    if (Get-Command winget -ErrorAction SilentlyContinue) { return $true }

    Write-Host 'Bootstrap ueber das offizielle Microsoft.WinGet.Client-Modul...' -ForegroundColor Yellow
    try {
        Install-PackageProvider -Name NuGet -Force -ErrorAction Stop | Out-Null
        Install-Module -Name Microsoft.WinGet.Client -Force -Repository PSGallery -ErrorAction Stop | Out-Null
        Repair-WinGetPackageManager -AllUsers -ErrorAction Stop
    } catch {
        Write-Host ("  Modul-Bootstrap fehlgeschlagen: {0}" -f $_.Exception.Message) -ForegroundColor DarkYellow
    }
    if (Get-Command winget -ErrorAction SilentlyContinue) { return $true }

    Write-Host 'winget konnte nicht bereitgestellt werden.' -ForegroundColor Red
    Write-Host 'Bitte den "App-Installer" manuell aus dem Microsoft Store installieren:' -ForegroundColor Red
    Write-Host '  ms-windows-store://pdp/?ProductId=9NBLGGH4NNS1' -ForegroundColor Red
    try { Start-Process 'ms-windows-store://pdp/?ProductId=9NBLGGH4NNS1' } catch { }
    return $false
}

if (-not (Ensure-WinGet)) {
    Write-Host 'Ohne winget koennen keine Programme installiert werden. Abbruch.' -ForegroundColor Red
    Read-Host 'Zum Beenden Enter druecken'
    exit 1
}
Write-Host 'winget ist verfuegbar.' -ForegroundColor Green

# PowerShell 7 nachinstallieren, falls es fehlte
if (-not $ps7Vorhanden) {
    Write-Host 'Installiere PowerShell 7 (Microsoft.PowerShell)...' -ForegroundColor Cyan
    winget install --id Microsoft.PowerShell --source winget --exact --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -eq 0) {
        Write-Host 'PowerShell 7 installiert.' -ForegroundColor Green
    } else {
        Write-Host ("PowerShell 7 nicht installiert (winget-Code {0}). Weiter mit vorhandener Version." -f $LASTEXITCODE) -ForegroundColor DarkYellow
    }
}

# ------------------------------------------------------------------
# 4. Ausgewaehlte Programme installieren
# ------------------------------------------------------------------
$apps = @(
__APPS_ARRAY__
)

$erfolg = 0
$fehler = 0
$fehlerListe = @()

foreach ($app in $apps) {
    Write-Host ''
    Write-Host ("Installiere {0} ({1}) ..." -f $app.Name, $app.Id) -ForegroundColor Cyan
    try {
        winget install --id $app.Id --source $app.Source --exact --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
        if ($LASTEXITCODE -eq 0) {
            $erfolg++
        } else {
            $fehler++
            $fehlerListe += ("{0} (winget-Code {1})" -f $app.Name, $LASTEXITCODE)
        }
    } catch {
        $fehler++
        $fehlerListe += ("{0} ({1})" -f $app.Name, $_.Exception.Message)
    }
}

# ------------------------------------------------------------------
# 5. Zusammenfassung
# ------------------------------------------------------------------
Write-Host ''
Write-Host '====================================================' -ForegroundColor White
Write-Host ("Fertig. Erfolgreich: {0}  Fehlgeschlagen: {1}" -f $erfolg, $fehler) -ForegroundColor White
if ($fehler -gt 0) {
    Write-Host 'Fehlgeschlagen (bitte manuell pruefen):' -ForegroundColor Yellow
    foreach ($f in $fehlerListe) { Write-Host ("  - {0}" -f $f) -ForegroundColor Yellow }
}
Write-Host ''
Read-Host 'Zum Beenden Enter druecken'
"""


def _apps_array(installable: list[InstalledApp]) -> str:
    """Erzeugt die PowerShell-Hashtable-Eintraege fuer das $apps-Array."""
    if not installable:
        return ""
    entries = []
    for app in installable:
        entries.append(
            "    @{{ Id = {id}; Name = {name}; Source = {source} }}".format(
                id=_ps_quote(app.package_id or ""),
                name=_ps_quote(app.name),
                source=_ps_quote(app.source or "winget"),
            )
        )
    return ",\n".join(entries)


def build_powershell_script(
    apps: list[InstalledApp],
    *,
    tool_version: str = TOOL_VERSION,
    created: datetime | None = None,
) -> str:
    created = created if created is not None else datetime.now()
    installable, _ = _split(apps)
    return (
        _PS_TEMPLATE
        .replace("__VERSION__", tool_version)
        .replace("__CREATED__", created.strftime("%Y-%m-%d %H:%M"))
        .replace("__APPS_ARRAY__", _apps_array(installable))
    )


# ---------------------------------------------------------------------------
# 3. UniGetUI-Bundle
# ---------------------------------------------------------------------------

def build_unigetui_bundle(apps: list[InstalledApp]) -> str:
    """Erzeugt ein UniGetUI-Bundle (JSON-String, Schema export_version 3)."""
    installable, manual = _split(apps)

    packages = [
        {
            "Id": app.package_id or "",
            "Name": app.name,
            "Version": app.version or "",
            "Source": app.source or "winget",
            "ManagerName": _UNIGETUI_MANAGER_NAME,
        }
        for app in installable
    ]
    incompatible = [
        {
            "Id": "",
            "Name": app.name,
            "Version": app.version or "",
            "Source": _UNIGETUI_LOCAL_SOURCE,
        }
        for app in manual
    ]

    bundle = {
        "export_version": 3,
        "packages": packages,
        "incompatible_packages_info": _UNIGETUI_INCOMPAT_INFO,
        "incompatible_packages": incompatible,
    }
    return json.dumps(bundle, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Alles schreiben
# ---------------------------------------------------------------------------

def write_install_plan(
    apps: list[InstalledApp],
    dest_dir: Path | str,
    *,
    tool_version: str = TOOL_VERSION,
    host: str | None = None,
    created: datetime | None = None,
) -> InstallPlanResult:
    """Schreibt die drei Dateien in ``dest_dir`` und liefert die Pfade."""
    created = created if created is not None else datetime.now()
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    installable, manual = _split(apps)

    instructions_path = dest / FILENAME_INSTRUCTIONS
    script_path = dest / FILENAME_SCRIPT
    bundle_path = dest / FILENAME_BUNDLE

    instructions_path.write_text(
        build_instruction_markdown(apps, tool_version=tool_version, host=host, created=created),
        encoding="utf-8",
    )
    # PS-Skript mit BOM speichern, damit Windows PowerShell 5.1 UTF-8 korrekt liest.
    script_path.write_text(
        build_powershell_script(apps, tool_version=tool_version, created=created),
        encoding="utf-8-sig",
    )
    bundle_path.write_text(build_unigetui_bundle(apps), encoding="utf-8")

    return InstallPlanResult(
        instructions_path=instructions_path,
        script_path=script_path,
        bundle_path=bundle_path,
        installable_count=len(installable),
        manual_count=len(manual),
    )


def launch_install_script(script_path: Path | str) -> None:
    """Startet das erzeugte ``Install-Apps.ps1`` in einem eigenen PowerShell-Fenster.

    Das Skript regelt Admin-Elevation (UAC), PowerShell-7-Pruefung und den
    winget-Bootstrap selbst. Es gibt bewusst keine Rueckmeldung ins Tool zurueck
    (der elevierte Prozess laeuft getrennt) - der Fortschritt erscheint im
    PowerShell-Fenster. Startet auf DEM Rechner, auf dem BrowserBackup laeuft.

    Raises:
        FileNotFoundError: wenn das Skript nicht existiert.
    """
    path = Path(script_path)
    if not path.is_file():
        raise FileNotFoundError(f"Installationsskript nicht gefunden: {path}")

    creationflags = 0
    if sys.platform == "win32":
        # Eigenes Konsolenfenster, auch wenn BrowserBackup als --windowed-Exe laeuft.
        creationflags = subprocess.CREATE_NEW_CONSOLE

    subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)],
        creationflags=creationflags,
    )
