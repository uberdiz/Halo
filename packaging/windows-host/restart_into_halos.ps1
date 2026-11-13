# Restart into HalOS once, from Windows (Windows stays the default afterwards). Run as Administrator:
#
#   powershell -ExecutionPolicy Bypass -File packaging\windows-host\restart_into_halos.ps1 [-Live] [-NoRestart]
#
# Finds the firmware boot entry the HalOS installer made ("HalOS"; -Live: the live system on HALOLIVE,
# "HalOS (live)") and sets it as the firmware's next boot only (bcdedit bootsequence). Nothing else changes.
param([switch]$Live, [switch]$NoRestart)
$ErrorActionPreference = "Stop"
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not ([Security.Principal.WindowsPrincipal]$id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this from an Administrator PowerShell."
}
$want = if ($Live) { "HalOS (live)" } else { "HalOS" }
# bcdedit /enum firmware: blocks of "identifier {guid}" ... "description <name>".
$guid = $null; $cur = $null
foreach ($line in (bcdedit /enum firmware)) {
    if ($line -match '^identifier\s+(\{[0-9a-fA-F-]{36}\})') { $cur = $Matches[1] }
    elseif ($line -match '^description\s+(.+?)\s*$' -and $Matches[1] -eq $want -and $cur) { $guid = $cur; break }
}
if (-not $guid -and $Live) {
    # HALOLIVE has no entry of its own (the firmware lists it in its boot menu); Setup shows this line.
    "HALOLIVE-READY: restart, press your PC's boot-menu key (F12 on most PCs) and pick HALOLIVE (or 'UEFI: ... Partition'). Windows stays the default."
    exit 0
}
if (-not $guid) {
    throw "No firmware boot entry named '$want'. Install HalOS first, or start it from the PC's boot menu (F12)."
}
bcdedit /set '{fwbootmgr}' bootsequence $guid | Out-Null
if ($LASTEXITCODE -ne 0) { throw "bcdedit couldn't set the next boot to $want." }
"Next restart starts $want ($guid); after that, Windows is the default again."
if (-not $NoRestart) { shutdown /r /t 5 /c "Restarting into $want" }
