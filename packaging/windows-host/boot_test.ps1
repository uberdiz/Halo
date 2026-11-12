# Boot-test the Halo ISO on this Windows PC in VirtualBox: UEFI and legacy BIOS, one throwaway VM each.
#
#   powershell -ExecutionPolicy Bypass -File packaging\windows-host\boot_test.ps1
#       [-Iso dist\halo\Halo-x86_64.iso] [-Firmware both|efi|bios] [-TimeoutMin 25] [-Keep]
#
# Reuses packaging\linux\vm\boot_test.ps1 (PASS = the image's own BOOT-OK + DESKTOP-OK + SAINT-OK markers on
# the serial port). Before booting it checks the ISO against SHA256SUMS, so a truncated copy is caught here
# instead of looking like a boot failure. VMs are named Halo-test-efi / Halo-test-bios; an old one with the
# same name is deleted first (they are disposable and only ever have their own virtual disk).
param(
    [string]$Iso = "",
    [ValidateSet("both", "efi", "bios")][string]$Firmware = "both",
    [int]$TimeoutMin = 25,
    [switch]$Keep
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path "$PSScriptRoot\..\..").Path
$vmDir = Join-Path $repo "packaging\linux\vm"
. "$vmDir\vbox.ps1"

try { $vb = Get-VBoxManage } catch { Write-Host $_.Exception.Message -ForegroundColor Red; exit 1 }
if (-not $Iso) { $Iso = Join-Path $repo "dist\halo\Halo-x86_64.iso" }
if (-not (Test-Path $Iso)) {
    Write-Host "ISO not found: $Iso`nBuild it first: packaging\windows-host\build_iso.ps1" -ForegroundColor Red
    exit 1
}
$Iso = (Resolve-Path $Iso).Path

# Hardware virtualisation: with Hyper-V/WSL2 on, VirtualBox runs through Hyper-V (works, slower).
$cs = Get-CimInstance Win32_ComputerSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
if (-not $cs.HypervisorPresent -and -not $cpu.VirtualizationFirmwareEnabled) {
    Write-Host "Hardware virtualisation (AMD SVM) is off in the firmware. Enable 'SVM Mode' in the BIOS/UEFI setup." -ForegroundColor Red
    exit 1
}
if ($cs.HypervisorPresent) { Write-Host "note: Hyper-V is active (WSL2); VirtualBox uses it as its backend, boots are slower." -ForegroundColor Yellow }

$sums = Join-Path (Split-Path $Iso) "SHA256SUMS"
if (Test-Path $sums) {
    $want = (Get-Content $sums | Where-Object { $_ -match [regex]::Escape((Split-Path $Iso -Leaf)) } | Select-Object -First 1) -split '\s+' | Select-Object -First 1
    if ($want) {
        Write-Host "Checking SHA-256 of $(Split-Path $Iso -Leaf)..."
        $have = (Get-FileHash -Algorithm SHA256 $Iso).Hash.ToLower()
        if ($have -ne $want.ToLower()) {
            Write-Host "SHA-256 mismatch: the ISO is damaged or truncated (have $have, want $want). Copy it again." -ForegroundColor Red
            exit 1
        }
        Write-Host "  SHA-256 OK"
    }
} else { Write-Host "note: no SHA256SUMS next to the ISO; not verified." -ForegroundColor Yellow }

$modes = if ($Firmware -eq "both") { @("efi", "bios") } else { @($Firmware) }
$results = [ordered]@{}
foreach ($fw in $modes) {
    $name = "Halo-test-$fw"
    Write-Host "`n==> $name ($fw)" -ForegroundColor Cyan
    Remove-TestVm $vb $name
    $args_ = @{ Iso = $Iso; Name = $name; Firmware = $fw; TimeoutMin = $TimeoutMin }
    if ($Keep) { $args_.Keep = $true }
    try {
        & "$vmDir\boot_test.ps1" @args_
        $results[$fw] = if ($LASTEXITCODE -eq 0) { "PASS" } else { "FAIL" }
    } catch {
        Write-Host "  $name stopped: $($_.Exception.Message)" -ForegroundColor Red
        $results[$fw] = "FAIL"
    }
}
Write-Host "`nResults:" -ForegroundColor Cyan
$results.GetEnumerator() | ForEach-Object { Write-Host ("  {0,-5} {1}   evidence: dist\boot-test-Halo-test-{0}\" -f $_.Key, $_.Value) }
if ($results.Values -contains "FAIL") { exit 1 }
