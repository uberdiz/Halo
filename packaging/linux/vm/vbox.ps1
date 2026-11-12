# Shared by create_vm.ps1 and boot_test.ps1 (dot-source it):  . "$PSScriptRoot\vbox.ps1"
#
#   Get-VBoxManage       the VBoxManage.exe path, or a clear "not installed -> winget install" error
#   Get-VmDir <name>     the folder VirtualBox keeps that VM in (honours a changed default machine folder)
#   Remove-TestVm <name> power off and delete a disposable test VM (only ones these scripts made)

function Get-VBoxManage {
    $candidates = @()
    if ($env:VBOX_MSI_INSTALL_PATH) { $candidates += (Join-Path $env:VBOX_MSI_INSTALL_PATH "VBoxManage.exe") }
    $candidates += "$env:ProgramFiles\Oracle\VirtualBox\VBoxManage.exe"
    $onPath = Get-Command VBoxManage.exe -ErrorAction SilentlyContinue
    if ($onPath) { $candidates += $onPath.Source }
    foreach ($c in $candidates) { if ($c -and (Test-Path $c)) { return $c } }
    throw ("VirtualBox isn't installed (no VBoxManage.exe). Install it with:`n" +
           "    winget install --id Oracle.VirtualBox -e`n" +
           "then open a new PowerShell window and run this again. (With WSL2/Hyper-V on, VirtualBox 7 still works; " +
           "it runs on top of Hyper-V and is somewhat slower.)")
}

function Get-VmDir([string]$vb, [string]$name) {
    $line = & $vb showvminfo $name --machinereadable | Select-String '^CfgFile='
    $cfg = ($line.ToString() -split '=', 2)[1].Trim('"') -replace '\\\\', '\'
    return (Split-Path $cfg)
}

function Remove-TestVm([string]$vb, [string]$name) {
    if (-not ((& $vb list vms) -match "`"$name`"")) { return }
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $vb controlvm $name poweroff 2>&1 | Out-Null
    Start-Sleep -Seconds 2
    & $vb unregistervm $name --delete 2>&1 | Out-Null
    $ErrorActionPreference = $old
}
