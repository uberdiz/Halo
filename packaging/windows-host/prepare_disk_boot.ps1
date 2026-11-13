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
#
# -Refresh puts a new build on the existing HALOLIVE partition instead: it reformats HALOLIVE only, so nothing
# from the old build is left behind. C: and the unallocated space stay as they are. Both modes make no firmware boot
# entry, remove the bootmgr copies older Setups made, and keep Windows Boot Manager first.
param(
    [string]$Iso = "",
    [int]$LiveGB = 6,
    [int]$InstallGB = 200,
    [switch]$Refresh,
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
function Write-LiveSystem([string]$dst) {
    # Extract with tar (libarchive reads the ISO's Rock Ridge names). Do NOT copy from a mounted ISO: Windows
    # shows archiso images by their plain ISO 9660 names (VMLINUZ_LINUX, 2026_11_05_..._00.UUID), so the boot
    # loader finds no kernel and the live system can't find its boot ID file.
    "Extracting the live system to ${dst}: ..."
    tar -xf $script:Iso -C "${dst}:\" 2>&1 | Where-Object { "$_" -notmatch "Can.t restore time" }
    attrib -R "${dst}:\*" /S /D | Out-Null
    $problems = 0
    foreach ($line in (tar -tvf $script:Iso)) {
        if ($line -notmatch '^-') { continue }
        $f = $line -split '\s+', 9
        $path = Join-Path "${dst}:\" ($f[8] -replace '/', '\')
        if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -ne [int64]$f[4]) { "bad copy: $($f[8])"; $problems++ }
    }
    if ($problems) { throw "$problems file(s) didn't copy correctly" }
    "  every file matches the ISO"

    # Windows' device encryption can BitLocker-encrypt a new volume on its own; firmware can't read an
    # encrypted partition. Turn it off for HALOLIVE (public files only) and wait until it's fully decrypted.
    # A decryption Windows pauses (e.g. behind a pending restart or a busy disk) is resumed; progress is shown.
    $t = 0; $last = ""
    while (($s = manage-bde -status "${dst}:" | Out-String) -notmatch 'Conversion Status:\s+Fully Decrypted|could not be opened by BitLocker') {
        $conv = if ($s -match 'Conversion Status:\s+([^\r\n]+)') { $Matches[1].Trim() } else { "unknown" }
        $pct = if ($s -match 'Percentage Encrypted:\s+([\d.,]+)') { $Matches[1] } else { "?" }
        if ($t -eq 0) { "HALOLIVE was encrypted by Windows; decrypting it..." }
        if ($conv -match 'Paused') { manage-bde -resume "${dst}:" | Out-Null }
        elseif ($conv -notmatch 'Decryption in Progress') { manage-bde -off "${dst}:" | Out-Null }
        if ("$conv $pct" -ne $last -or $t % 60 -eq 0) { "  $conv, $pct% encrypted"; $last = "$conv $pct" }
        Start-Sleep 5; $t += 5
        if ($t -gt 1800) { throw "HALOLIVE is still encrypted after 30 minutes:`n$s" }
    }
    "  HALOLIVE is not encrypted"
}

function Test-IsoChecksum {
    $sums = Join-Path (Split-Path $script:Iso) "SHA256SUMS"
    if (Test-Path $sums) {
        $want = ((Get-Content $sums | Where-Object { $_ -match [regex]::Escape((Split-Path $script:Iso -Leaf)) }) -split '\s+')[0]
        "Checking the ISO's SHA-256..."
        $got = (Get-FileHash $script:Iso -Algorithm SHA256).Hash.ToLower()
        if ($got -ne $want) { throw "ISO checksum mismatch: $got (expected $want)" }
        "  OK"
    } else { Write-Warning "No SHA256SUMS next to the ISO; not verified." }
}

function Test-IsoFitsFat32([int64]$capacity) {
    # HALOLIVE is FAT32 (firmware boots from it): no file may be 4 GiB or bigger, and everything must fit.
    # Checked BEFORE anything is formatted, so a too-big build can't leave HALOLIVE empty (v2.1.0-beta.1 did).
    $max = 0; $total = 0; $name = ""
    foreach ($line in (tar -tvf $script:Iso)) {
        if ($line -notmatch '^-') { continue }
        $f = $line -split '\s+', 9
        $n = [int64]$f[4]; $total += $n
        if ($n -gt $max) { $max = $n; $name = $f[8] }
    }
    if ($max -ge 4GB) {
        throw ("This HalOS build can't go on HALOLIVE: $name is $([math]::Round($max / 1GB, 2)) GB and FAT32 holds " +
               "files under 4 GB. Nothing was changed. Use a newer HalOS release, or write the ISO to a USB stick.")
    }
    if ($capacity -gt 0 -and $total -gt $capacity - 64MB) {
        throw ("The live system needs $([math]::Round($total / 1GB, 1)) GB but HALOLIVE holds " +
               "$([math]::Round($capacity / 1GB, 1)) GB. Nothing was changed.")
    }
    "  fits FAT32 (largest file $([math]::Round($max / 1MB)) MB, total $([math]::Round($total / 1GB, 2)) GB)"
}

# No firmware boot entry is made for HALOLIVE: it is typed as an EFI system partition, so the firmware's boot menu
# (F12) lists it on its own. Setups up to 2.1.0-beta.2 made one by copying {bootmgr} with bcdedit; that copy is a
# *Windows Boot Manager* object pointing at HALOLIVE's \EFI\BOOT\BOOTX64.EFI, and firmware/Windows put it ahead of
# the real Windows Boot Manager, so the PC started HalOS live instead of Windows. Those copies are removed here
# and Windows Boot Manager goes back to the front. Nothing else in the boot order changes.
function Remove-LiveBootCopies {
    $blocks = ((bcdedit /enum firmware) -join "`n") -split "`n\s*`n"
    foreach ($b in $blocks) {
        if ($b -match '(?m)^identifier\s+(\{[0-9a-fA-F-]{36}\})' -and ($id = $Matches[1]) -and
            $b -match '(?m)^Windows Boot Manager' -and $b -match '(?mi)^path\s+\EFI\BOOT\BOOTX64\.EFI\s*$' -and
            $b -match '(?mi)^description\s+.*\(live\)\s*$') {
            bcdedit /delete $id | Out-Null
            if ($LASTEXITCODE -eq 0) { "Removed the old live boot entry $id (it started HalOS instead of Windows)." }
            else { Write-Warning "Couldn't remove boot entry $id; remove it with: bcdedit /delete $id" }
        }
    }
    bcdedit /set '{fwbootmgr}' displayorder '{bootmgr}' /addfirst | Out-Null
}

$ESP = '{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}'
$BASIC = '{ebd0a0a2-b9e5-4433-87c0-68b6b72699c7}'

if ($Refresh) {
    # Exactly one HALOLIVE candidate, 1-16 GB, after C: on the disk that holds C:. Anything else: stop. Windows
    # reports no label for a partition typed as an ESP, so an ESP-typed one after C: counts as a candidate, and
    # its label is checked once it has a drive letter, before anything is formatted.
    $c = Get-Partition -DriveLetter C
    $disk = $c.DiskNumber
    $found = @(Get-Partition -DiskNumber $disk | Where-Object {
        $v = $_ | Get-Volume -ErrorAction SilentlyContinue
        $_.Size -gt 1GB -and $_.Size -lt 16GB -and $_.Offset -gt $c.Offset -and (
            ($v -and $v.FileSystemLabel -eq 'HALOLIVE' -and $v.FileSystem -eq 'FAT32') -or
            ($_.GptType -eq $ESP -and -not ($v -and $v.FileSystemLabel)))
    })
    if ($found.Count -ne 1) { throw "Expected one HALOLIVE partition after C: on disk $disk, found $($found.Count). Nothing changed." }
    $p = $found[0]
    $origType = $p.GptType
    $isoSize = (Get-Item $Iso).Length
    if ($isoSize -gt ($p.Size - 200MB)) {
        throw "The ISO ({0:N1} GB) doesn't fit on HALOLIVE ({1:N1} GB). Nothing changed." -f ($isoSize/1GB), ($p.Size/1GB)
    }
    Test-IsoChecksum
    Test-IsoFitsFat32 $p.Size
    "Plan: reformat HALOLIVE (disk $disk partition $($p.PartitionNumber), {0:N1} GB) and write $(Split-Path $Iso -Leaf). Nothing else changes." -f ($p.Size/1GB)
    if ($WhatIf) { "WhatIf: nothing changed."; return }
    # An ESP gets no drive letter: make it a basic partition while it's written, and an ESP again afterwards.
    $verified = $false
    Set-Partition -DiskNumber $disk -PartitionNumber $p.PartitionNumber -GptType $BASIC
    try {
        # A letter left over from an interrupted run is reused (Windows refuses a second one).
        $had = (Get-Partition -DiskNumber $disk -PartitionNumber $p.PartitionNumber).DriveLetter
        if (-not $had -or "$had" -eq [string][char]0) {
            Add-PartitionAccessPath -DiskNumber $disk -PartitionNumber $p.PartitionNumber -AssignDriveLetter
        }
        $dst = (Get-Partition -DiskNumber $disk -PartitionNumber $p.PartitionNumber).DriveLetter
        if (-not $dst -or "$dst" -eq [string][char]0) { throw "Windows didn't give HALOLIVE a drive letter. Nothing was formatted." }
        $v = Get-Volume -DriveLetter $dst
        if ($v.FileSystemLabel -ne 'HALOLIVE' -or $v.FileSystem -ne 'FAT32') {
            Remove-PartitionAccessPath -DiskNumber $disk -PartitionNumber $p.PartitionNumber -AccessPath "${dst}:\"
            throw "Partition $($p.PartitionNumber) is '$($v.FileSystemLabel)' ($($v.FileSystem)), not HALOLIVE (FAT32). Nothing was formatted."
        }
        $verified = $true
        Format-Volume -DriveLetter $dst -FileSystem FAT32 -NewFileSystemLabel HALOLIVE -Confirm:$false | Out-Null
        Write-LiveSystem $dst
        Remove-LiveBootCopies
        Remove-PartitionAccessPath -DiskNumber $disk -PartitionNumber $p.PartitionNumber -AccessPath "${dst}:\"
    } finally {
        # HALOLIVE goes back to being an ESP (firmware lists it, Windows leaves it alone); anything else gets its own type back.
        Set-Partition -DiskNumber $disk -PartitionNumber $p.PartitionNumber -GptType $(if ($verified) { $ESP } else { $origType })
    }
    "Done. HALOLIVE now holds a clean copy of this build. Restart, press F12, and pick HALOLIVE or 'HalOS (live)'."
    return
}

if (Get-Volume -FileSystemLabel HALOLIVE -ErrorAction SilentlyContinue) {
    throw "A HALOLIVE partition already exists. Use -Refresh to put a new build on it, or delete it in Disk Management first."
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
Test-IsoChecksum
Test-IsoFitsFat32 ([int64]$LiveGB * 1GB)

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
Write-LiveSystem $dst

Remove-LiveBootCopies

# The drive letter would make Windows offer to "scan and fix" the FAT32 volume; it doesn't need one.
Remove-PartitionAccessPath -DiskNumber $p.DiskNumber -PartitionNumber $p.PartitionNumber -AccessPath "${dst}:\"
# Mark it as an EFI System Partition last (BitLocker's tools refuse to act on an ESP, so this comes after the
# decryption above): firmware lists ESPs in its boot menu, and Windows never gives one a letter or encrypts it.
Set-Partition -DiskNumber $p.DiskNumber -PartitionNumber $p.PartitionNumber -GptType '{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}'
""
"Done. HALOLIVE is partition $($p.PartitionNumber) on disk $($p.DiskNumber); $InstallGB GB is unallocated after it."
"Next: restart -> F12 -> 'UEFI: ... Partition $($p.PartitionNumber)' (or the disk's name). Install HalOS into the unallocated space only."
