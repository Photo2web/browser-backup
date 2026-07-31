"""Erzeugt aus einer Auswahl installierter Programme ein PowerShell-Skript
``Deinstallieren.ps1``, das sie der Reihe nach entfernt.

Parallel zu ``installplan.py`` aufgebaut: eine reine, testbare Skript-Erzeugung
plus eine ``write_and_launch_uninstall``-Funktion, die das Skript in einem
eigenen Konsolenfenster startet. Das Skript

* eleviert sich selbst als Administrator (UAC), sobald ein systemweites
  (``machine``) Programm dabei ist - dasselbe Muster wie das Install-Skript;
* entfernt still, wo moeglich (``QuietUninstallString`` bzw. MSI ``/qn``), sonst
  erscheint der Hersteller-Uninstaller zum Durchklicken;
* zaehlt Erfolg/Fehler je Programm und zeigt am Ende eine Zusammenfassung.

Ausgefuehrt werden die ``UninstallString``-Werte aus der Registry - genau die
Befehle, die Windows selbst zum Deinstallieren nutzt.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from core import TOOL_VERSION

FILENAME_UNINSTALL = "Deinstallieren.ps1"

# Produkt-GUID eines MSI-Uninstallers, z.B. {90140000-...}.
_MSI_GUID_RE = re.compile(
    r"\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}"
)


def _ps_quote(value: str) -> str:
    """Als PowerShell-Single-Quoted-String kodieren (' wird zu '')."""
    return "'" + value.replace("'", "''") + "'"


def command_for(program) -> tuple[str, bool]:
    """Liefert (Befehlszeile, still?) fuer ein Programm.

    Bevorzugt den stillen Weg: QuietUninstallString; sonst MSI auf ``/qn``
    umschreiben; sonst den normalen UninstallString (interaktiv)."""
    quiet = (getattr(program, "quiet_uninstall_string", None) or "").strip()
    if quiet:
        return quiet, True
    raw = (getattr(program, "uninstall_string", None) or "").strip()
    match = _MSI_GUID_RE.search(raw)
    if match and "msiexec" in raw.lower():
        return f"msiexec.exe /x{match.group(0)} /qn /norestart", True
    return raw, False


_PS_TEMPLATE = r"""<#
    Deinstallieren.ps1
    Erzeugt von Umzugstool __VERSION__ am __CREATED__.

    Entfernt die ausgewaehlten Programme. Still wo moeglich, sonst erscheint der
    Hersteller-Uninstaller. Systemweite Programme erfordern Administrator-Rechte.
#>

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$needsAdmin = __NEEDS_ADMIN__

# ------------------------------------------------------------------
# Selbst-Elevation als Administrator (nur wenn systemweite Programme dabei)
# ------------------------------------------------------------------
$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$istAdmin  = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if ($needsAdmin -and -not $istAdmin) {
    Write-Host 'Starte mit Administrator-Rechten neu (Programme aller Benutzer)...' -ForegroundColor Yellow
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

# ------------------------------------------------------------------
# Ausgewaehlte Programme entfernen
# ------------------------------------------------------------------
$apps = @(
__APPS_ARRAY__
)

$erfolg = 0
$fehler = 0
$fehlerListe = @()

foreach ($app in $apps) {
    Write-Host ''
    Write-Host ("Entferne {0} ..." -f $app.Name) -ForegroundColor Cyan
    if (-not $app.Silent) {
        Write-Host '  (Hersteller-Uninstaller - bitte im erscheinenden Fenster fortfahren)' -ForegroundColor DarkYellow
    }
    try {
        & cmd.exe /c $app.Cmd
        if ($LASTEXITCODE -eq 0) {
            $erfolg++
        } else {
            $fehler++
            $fehlerListe += ("{0} (Code {1})" -f $app.Name, $LASTEXITCODE)
        }
    } catch {
        $fehler++
        $fehlerListe += ("{0} ({1})" -f $app.Name, $_.Exception.Message)
    }
}

# ------------------------------------------------------------------
# Zusammenfassung
# ------------------------------------------------------------------
Write-Host ''
Write-Host '====================================================' -ForegroundColor White
Write-Host ("Fertig. Entfernt: {0}  Fehlgeschlagen: {1}" -f $erfolg, $fehler) -ForegroundColor White
if ($fehler -gt 0) {
    Write-Host 'Fehlgeschlagen (bitte manuell pruefen):' -ForegroundColor Yellow
    foreach ($f in $fehlerListe) { Write-Host ("  - {0}" -f $f) -ForegroundColor Yellow }
}
Write-Host ''
Read-Host 'Zum Beenden Enter druecken'
"""


def _apps_array(programs) -> str:
    """PowerShell-Hashtable-Eintraege fuer das $apps-Array."""
    entries = []
    for program in programs:
        cmd, silent = command_for(program)
        entries.append(
            "    @{{ Name = {name}; Cmd = {cmd}; Silent = {silent} }}".format(
                name=_ps_quote(program.name),
                cmd=_ps_quote(cmd),
                silent="$true" if silent else "$false",
            )
        )
    return ",\n".join(entries)


def build_uninstall_script(programs, *, tool_version: str = TOOL_VERSION,
                           created: datetime | None = None) -> str:
    """Erzeugt den Inhalt von ``Deinstallieren.ps1`` fuer die Programmauswahl."""
    created = created if created is not None else datetime.now()
    needs_admin = any(getattr(p, "scope", "") == "machine" for p in programs)
    return (
        _PS_TEMPLATE
        .replace("__VERSION__", tool_version)
        .replace("__CREATED__", created.strftime("%Y-%m-%d %H:%M"))
        .replace("__NEEDS_ADMIN__", "$true" if needs_admin else "$false")
        .replace("__APPS_ARRAY__", _apps_array(programs))
    )


def write_and_launch_uninstall(programs, work_dir, *,
                               tool_version: str = TOOL_VERSION) -> Path:
    """Schreibt ``Deinstallieren.ps1`` nach ``work_dir`` und startet es in einem
    eigenen Konsolenfenster. Gibt den Skriptpfad zurueck.

    Raises:
        OSError: wenn das Skript nicht geschrieben werden kann.
    """
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    script = work / FILENAME_UNINSTALL
    # BOM, damit Windows PowerShell 5.1 die UTF-8-Umlaute korrekt liest.
    script.write_text(
        build_uninstall_script(programs, tool_version=tool_version),
        encoding="utf-8-sig",
    )

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_CONSOLE
    subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        creationflags=creationflags,
    )
    return script
