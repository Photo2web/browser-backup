# build.ps1 - Erstellt die portable BrowserBackup.exe per PyInstaller.
#
# Voraussetzung: pip install -r requirements-dev.txt
# Aufruf: .\build.ps1
#
# --onefile   -> eine einzelne, portable .exe (kein Installer noetig)
# --windowed  -> kein Konsolenfenster im Hintergrund
# --collect-all customtkinter -> customtkinter liefert eigene Theme-/Asset-
#   Dateien (JSON, Fonts) aus, die PyInstaller sonst NICHT automatisch
#   mitnimmt. Ohne dieses Flag startet die .exe mit einem Theme-Fehler.
# psutil braucht i.d.R. kein extra Flag (PyInstaller-Hook ist eingebaut).

$ErrorActionPreference = "Stop"

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Host "PyInstaller ist nicht installiert. Installiere mit:" -ForegroundColor Yellow
    Write-Host "  pip install -r requirements-dev.txt" -ForegroundColor Yellow
    exit 1
}

Write-Host "Baue BrowserBackup.exe ..." -ForegroundColor Cyan

pyinstaller --onefile --windowed --name BrowserBackup --collect-all customtkinter main.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nFertig: dist\BrowserBackup.exe" -ForegroundColor Green
} else {
    Write-Host "`nBuild fehlgeschlagen (Exit-Code $LASTEXITCODE)." -ForegroundColor Red
    exit $LASTEXITCODE
}
