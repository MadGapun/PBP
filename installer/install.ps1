#Requires -Version 5.1
# ============================================================================
# PBP - install.ps1 ist VERALTET und tut nichts mehr (#1149)
# ============================================================================
# Dieser PowerShell-Installer richtete PBP in einer .venv ein und schrieb in einen Datenordner, den die aktuelle Version
# nicht mehr benutzt; nach einem gescheiterten pip meldete er trotzdem "OK". Er wurde durch INSTALLIEREN.bat ersetzt.
#
# Auf Windows:  Doppelklick auf INSTALLIEREN.bat im entpackten PBP-Ordner.
# ============================================================================
Write-Host ""
Write-Host "  install.ps1 ist veraltet und wird nicht mehr benutzt."
Write-Host ""
Write-Host "  Bitte stattdessen im entpackten PBP-Ordner doppelklicken:"
Write-Host "    INSTALLIEREN.bat"
Write-Host ""
Write-Host "  Anleitung: https://github.com/MadGapun/PBP/wiki/Installation"
Write-Host ""
exit 1
