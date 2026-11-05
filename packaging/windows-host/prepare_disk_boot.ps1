# Boot the Halo live system from the internal disk instead of a USB stick (run as Administrator).
#
#   powershell -ExecutionPolicy Bypass -File packaging\windows-host\prepare_disk_boot.ps1 [-Iso dist\halo\build9\Halo-x86_64.iso]
#       [-LiveGB 6] [-InstallGB 200] [-WhatIf]
#
# What it does, on the disk that holds C: only:
#   1. refuses if BitLocker protection is on for C: (suspend it first), or C: can't shrink by LiveGB + InstallGB
#   2. verifies the ISO against SHA256SUMS
#   3. shrinks C: by LiveGB + InstallGB
#   4. creates a LiveGB FAT32 partition labelled HALOLIVE right after C: and copies the ISO's files onto it
#      (Halo's boot entries find the live system by its archisosearchuuid file, so any partition works)
#   5. leaves InstallGB unallocated for the installer
# Then: restart, F12, pick "UEFI: <2 TB disk> Partition N (HALOLIVE)". In the installer use the unallocated space,
# NOT the HALOLIVE partition. Afterwards remove HALOLIVE in Disk Management (or keep it as a rescue system).
# -WhatIf prints the plan and changes nothing.
param(
    [string]$Iso = "",
    [int]$LiveGB = 6,
    [int]$InstallGB = 200,
    [switch]$WhatIf
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path "$PSScriptRoot\..\..").Path
if (-not $Iso) { $Iso = Join-Path $repo "dist\halo\build9\Halo-x86_64.iso" }
$Iso = (Resolve-Path $Iso).Path

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not ([Security.Principal.WindowsPrincipal]$id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this from an Administrator PowerShell."
}
if (Get-Volume -FileSystemLabel HALOLIVE -ErrorAction SilentlyContinue) {
    throw "A HALOLIVE partition already exists. Delete it in Disk Management first, or reuse it."
}

# 1. Safety checks
$bl = Get-BitLockerVolume -MountPoint C: -ErrorAction SilentlyContinue
if ($bl -and $bl.ProtectionStatus -eq 'On') {
    throw "BitLocker protection is ON for C:. Suspend it first:  manage-bde -protectors -disable C: -RebootCount 3  (keep your recovery key)."
}
$c = Get-Partition -DriveLetter C
$needBytes = [int64]($LiveGB + $InstallGB) * 1GB
# diskpart's "shrink querymax" (Get-PartitionSupportedSize fails on some systems with StorageWMI 4).
function Invoke-Diskpart([string[]]$lines) {
    $f = New-TemporaryFile
    Set-Content -Path $f -Value $lines -Encoding ascii
    try { diskpart /s $f } finally { Remove-Item $f }
}
$q = (Invoke-Diskpart @("select volume C", "shrink querymax")) | Out-String
$mq = [regex]::Match($q, 'reclaimable bytes is:\s+([\d.,]+)\s+(GB|MB|TB)')
if (-not $mq.Success) { throw "Couldn't read how far C: can shrink:`n$q" }
$num = [double]($mq.Groups[1].Value -replace ',', '')
$maxShrink = [int64]($num * @{ MB = 1MB; GB = 1GB; TB = 1TB }[$mq.Groups[2].Value])
"C: is {0:N1} GB on disk {1}; it can shrink by up to {2:N1} GB; this needs {3} GB." -f ($c.Size/1GB), $c.DiskNumber, ($maxShrink/1GB), ($LiveGB + $InstallGB)
if ($maxShrink -lt $needBytes) {
    throw "C: can only shrink by {0:N1} GB (unmovable files). Run 'defrag C: /O', or temporarily turn off the page file / System Restore, then retry." -f ($maxShrink/1GB)
}

# 2. ISO checksum
$sums = Join-Path (Split-Path $Iso) "SHA256SUMS"
if (Test-Path $sums) {
    $want = ((Get-Content $sums | Where-Object { $_ -match [regex]::Escape((Split-Path $Iso -Leaf)) }) -split '\s+')[0]
    "Checking the ISO's SHA-256..."
    $got = (Get-FileHash $Iso -Algorithm SHA256).Hash.ToLower()
    if ($got -ne $want) { throw "ISO checksum mismatch: $got (expected $want)" }
    "  OK"
} else { Write-Warning "No SHA256SUMS next to the ISO; not verified." }

"Plan:"
"  shrink C: from {0:N1} GB to {1:N1} GB" -f ($c.Size/1GB), (($c.Size - $needBytes)/1GB)
"  create a $LiveGB GB FAT32 partition HALOLIVE after C: and copy the ISO onto it"
"  leave $InstallGB GB unallocated for the Halo installer"
if ($WhatIf) { "WhatIf: nothing changed."; return }

# 3-4. Shrink, create, format, copy
$r = (Invoke-Diskpart @("select volume C", "shrink desired=$([int64]($LiveGB + $InstallGB) * 1024)")) | Out-String
$after = (Get-Partition -DriveLetter C).Size
if (($c.Size - $after) -lt ($needBytes - 1MB)) { throw "Shrinking C: didn't work:`n$r" }
"Shrunk C: to {0:N1} GB" -f ($after/1GB)
$p = New-Partition -DiskNumber $c.DiskNumber -Size ([int64]$LiveGB * 1GB) -GptType '{ebd0a0a2-b9e5-4433-87c0-68b6b72699c7}' -AssignDriveLetter
Format-Volume -Partition $p -FileSystem FAT32 -NewFileSystemLabel HALOLIVE -Confirm:$false | Out-Null
$dst = (Get-Partition -DiskNumber $p.DiskNumber -PartitionNumber $p.PartitionNumber | Get-Volume).DriveLetter
$m = Mount-DiskImage -ImagePath $Iso -PassThru
try {
    $src = ($m | Get-Volume).DriveLetter
    "Copying the live system to ${dst}: ..."
    robocopy "${src}:\" "${dst}:\" /E /NFL /NDL /NJH /NP /R:1 /W:1 | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE)" }
    $a = (Get-Item "${src}:\halo\x86_64\airootfs.sfs").Length; $b = (Get-Item "${dst}:\halo\x86_64\airootfs.sfs").Length
    if ($a -ne $b) { throw "airootfs.sfs copy is incomplete ($b of $a bytes)" }
    if (-not (Get-ChildItem "${dst}:\boot" -Filter *.uuid)) { throw "the boot ID file (boot\*.uuid) is missing on HALOLIVE" }
} finally { Dismount-DiskImage -ImagePath $Iso | Out-Null }

# A firmware boot entry, last in the order (Windows stays the default): some firmware only lists the EFI
# system partition in its F12 menu, not other FAT32 partitions. bcdedit stores the partition by its ID.
$out = bcdedit /copy '{bootmgr}' /d "Halo OS (live)"
$guid = [regex]::Match(($out | Out-String), '\{[0-9a-fA-F-]{36}\}').Value
if ($guid) {
    bcdedit /set $guid device "partition=${dst}:" | Out-Null
    bcdedit /set $guid path '\EFI\BOOT\BOOTX64.EFI' | Out-Null
    bcdedit /set '{fwbootmgr}' displayorder $guid /addlast | Out-Null
    "Added firmware boot entry 'Halo OS (live)' $guid (remove later: bcdedit /delete $guid)"
} else { Write-Warning "Couldn't add a firmware boot entry ($out); use F12 and pick the HALOLIVE partition." }

# The drive letter would make Windows offer to "scan and fix" the FAT32 volume; it doesn't need one.
Remove-PartitionAccessPath -DiskNumber $p.DiskNumber -PartitionNumber $p.PartitionNumber -AccessPath "${dst}:\"
""
"Done. HALOLIVE is partition $($p.PartitionNumber) on disk $($p.DiskNumber); $InstallGB GB is unallocated after it."
"Next: restart -> F12 -> 'UEFI: ... Partition $($p.PartitionNumber)' (or the disk's name). Install Halo into the unallocated space only."
