# Build the Halo ISO on Windows, through WSL2, and copy it back verified.
#
#   powershell -ExecutionPolicy Bypass -File packaging\windows-host\build_iso.ps1
#       [-Distro archlinux] [-Mode test|fast|release] [-WorkDir /var/tmp/halo-build] [-SrcDir /var/tmp/halo-src]
#       [-InstallDeps] [-NoCopy] [-- extra build_iso.sh options via -BuildArgs "..."]
#
# What it does:
#   1. checks WSL2 and the distro (default: Arch Linux, `wsl --install archlinux`); says exactly what to run if
#      either is missing. -InstallDeps installs podman + git inside the distro (as root, no prompt).
#   2. clones the COMMITTED state of this checkout (HEAD) to -SrcDir on the Linux side. Uncommitted changes are
#      not included (build_iso.sh refuses a dirty tree anyway); commit first.
#   3. runs packaging/arch/build_in_container.sh there (podman, privileged Arch container), with the build tree,
#      container storage and pacman cache under -WorkDir on the Linux disk (needs ~25 GB free; never /mnt/c).
#   4. copies dist/halo back to <checkout>\dist\halo\ through a .part file, checks SHA-256 against SHA256SUMS,
#      and only then renames it into place. A mismatch deletes the .part and retries once.
#      (Build 7's first copy was truncated mid-way and that truncated ISO failed on USB; see HALOS_TEST_RESULTS.md.)
param(
    [string]$Distro = "archlinux",
    [ValidateSet("test", "fast", "release")][string]$Mode = "test",
    [string]$WorkDir = "/var/tmp/halo-build",
    [string]$SrcDir = "/var/tmp/halo-src",
    [string]$BuildArgs = "",
    [switch]$InstallDeps,
    [switch]$NoCopy
)
# "Continue": PowerShell 5.1 turns any native stderr into a terminating error under "Stop". Every step checks
# its own exit code instead (Fail), and the file operations below use -ErrorAction Stop.
$ErrorActionPreference = "Continue"
$env:WSL_UTF8 = "1"                       # wsl.exe prints UTF-16 otherwise, which breaks -match
$repo = (Resolve-Path "$PSScriptRoot\..\..").Path

function Fail([string]$msg) { Write-Host "build_iso: $msg" -ForegroundColor Red; exit 1 }
function Step([string]$msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function InWsl([string]$script) {
    # Everything runs as root inside the distro: no sudo prompts, and mkarchiso needs root anyway.
    $script = $script -replace "`r", ""
    & wsl.exe -d $Distro -u root -- bash -lc $script | Out-Host
    return $LASTEXITCODE
}

# ---- 1. WSL2 and the distro
Step "Checking WSL2"
if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { Fail "wsl.exe not found; Windows 10 2004+/11 is needed." }
# The not-installed stub prints UTF-16 whatever WSL_UTF8 says: drop the NULs before matching.
$status = ((& wsl.exe --status 2>&1 | Out-String) -replace "`0", "")
$wslRc = $LASTEXITCODE
if ($wslRc -ne 0 -or $status -match "not installed|is not enabled") {
    Fail ("WSL2 isn't installed yet. In an *administrator* PowerShell run:`n" +
          "    wsl --install --no-distribution`n" +
          "restart Windows, then:`n" +
          "    wsl --install $Distro`n" +
          "and run this script again (with -InstallDeps the first time).")
}
$distros = (& wsl.exe -l -q 2>$null | Out-String) -split "`r?`n" | ForEach-Object { $_.Trim([char]0, ' ') } | Where-Object { $_ }
if ($distros -notcontains $Distro) {
    Fail ("WSL distro '$Distro' isn't installed (found: $($distros -join ', ')). Install it with:`n" +
          "    wsl --install $Distro`n" +
          "(or pass -Distro Ubuntu-24.04 to use Ubuntu), then run this again with -InstallDeps.")
}
$verbose = (& wsl.exe -l -v 2>$null | Out-String)
if ($verbose -match "(?m)^\s*\*?\s*$([regex]::Escape($Distro))\s+\S+\s+1\s*$") {
    Fail "'$Distro' runs under WSL 1; convert it: wsl --set-version $Distro 2"
}

if ($InstallDeps) {
    Step "Installing podman and git in $Distro"
    $rc = InWsl @'
set -e
if command -v pacman >/dev/null; then pacman -Sy --needed --noconfirm podman git
elif command -v apt-get >/dev/null; then apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y podman git
elif command -v dnf >/dev/null; then dnf install -y podman git
else echo "unknown package manager" >&2; exit 1; fi
'@
    if ($rc -ne 0) { Fail "installing podman/git in $Distro failed (exit $rc)." }
}
$rc = InWsl "command -v git >/dev/null && { command -v podman >/dev/null || command -v docker >/dev/null; }"
if ($rc -ne 0) { Fail "$Distro needs git and podman (or docker). Run again with -InstallDeps." }

# ---- 2. free space on the Linux side, and on C: (the WSL disk image grows there)
Step "Checking free space"
$freeGb = (& wsl.exe -d $Distro -u root -- bash -c "mkdir -p '$WorkDir' && df -BG --output=avail '$WorkDir' | tail -1 | tr -dc 0-9" | Out-String).Trim()
if ([int]$freeGb -lt 25) { Fail "only $freeGb GB free for $WorkDir inside $Distro; the build needs ~25 GB." }
$cFree = [math]::Round((Get-PSDrive C).Free / 1GB)
Write-Host "  ${WorkDir}: $freeGb GB free; C: $cFree GB free (the WSL virtual disk lives on C: and grows)"
if ($cFree -lt 30) { Write-Host "  warning: under 30 GB free on C:; the WSL disk may fill it." -ForegroundColor Yellow }

# ---- 3. source: the committed HEAD of this checkout (works for git worktrees too)
Step "Cloning the committed source (HEAD) to $SrcDir"
$commit = (& git -C $repo rev-parse HEAD).Trim()
$common = (& git -C $repo rev-parse --path-format=absolute --git-common-dir).Trim()
if ((& git -C $repo status --porcelain --untracked-files=no | Measure-Object).Count -gt 0) {
    Write-Host "  note: uncommitted changes in $repo are NOT part of this build (commit them first)." -ForegroundColor Yellow
}
$commonWsl = (& wsl.exe -d $Distro -u root -- wslpath -a ($common -replace '\\', '/') | Out-String).Trim()
$rc = InWsl @"
set -e
git config --global --add safe.directory '*'
if [ -d '$SrcDir/.git' ]; then git -C '$SrcDir' fetch -q '$commonWsl' '$commit'
else rm -rf '$SrcDir'; git clone -q --no-checkout '$commonWsl' '$SrcDir'; fi
git -C '$SrcDir' checkout -q -f --detach '$commit'
git -C '$SrcDir' clean -fdq -e dist/
echo "  source at `$(git -C '$SrcDir' rev-parse --short HEAD)"
"@
if ($rc -ne 0) { Fail "couldn't clone $common into $SrcDir (exit $rc)." }

# ---- 4. build
Step "Building (mode $Mode); the first build downloads ~3 GB and takes 30-60 min"
$started = Get-Date
$rc = InWsl "cd '$SrcDir' && rm -rf dist/halo && bash packaging/arch/build_in_container.sh --workdir '$WorkDir' --mode $Mode $BuildArgs"
if ($rc -ne 0) { Fail "the build failed (exit $rc). Logs: $WorkDir/build/mkarchiso.log inside $Distro." }
Write-Host ("  built in {0:N0} min" -f ((Get-Date) - $started).TotalMinutes)
if ($NoCopy) { Write-Host "Built: \\wsl.localhost\$Distro$SrcDir/dist/halo (not copied: -NoCopy)"; exit 0 }

# ---- 5. copy back through .part files, verify SHA-256, then rename
Step "Copying dist/halo to $repo\dist\halo (verified)"
$src = "\\wsl.localhost\$Distro" + ($SrcDir -replace '/', '\') + "\dist\halo"
if (-not (Test-Path "$src\SHA256SUMS")) { $src = "\\wsl$\$Distro" + ($SrcDir -replace '/', '\') + "\dist\halo" }
if (-not (Test-Path "$src\SHA256SUMS")) { Fail "no SHA256SUMS in $src; the build didn't finish." }
$dest = Join-Path $repo "dist\halo"
New-Item -ItemType Directory -Force $dest | Out-Null
$sums = @{}
foreach ($l in Get-Content "$src\SHA256SUMS") { if ($l -match '^([0-9a-f]{64})\s+\*?(.+)$') { $sums[$Matches[2].Trim()] = $Matches[1] } }

foreach ($f in Get-ChildItem $src -File) {
    $part = Join-Path $dest ($f.Name + ".part")
    $final = Join-Path $dest $f.Name
    $ok = $false
    foreach ($try in 1, 2) {
        if (Test-Path $part) { Remove-Item -Force $part }
        Copy-Item -LiteralPath $f.FullName -Destination $part -ErrorAction Stop
        $len = (Get-Item $part).Length
        if ($len -ne $f.Length) { Write-Host "  $($f.Name): size $len != $($f.Length), retrying" -ForegroundColor Yellow; continue }
        if ($sums.ContainsKey($f.Name)) {
            $h = (Get-FileHash -Algorithm SHA256 $part).Hash.ToLower()
            if ($h -ne $sums[$f.Name]) { Write-Host "  $($f.Name): SHA-256 mismatch, retrying" -ForegroundColor Yellow; continue }
            Write-Host "  $($f.Name): SHA-256 OK ($h)"
        }
        $ok = $true
        break
    }
    if (-not $ok) { Remove-Item -Force -ErrorAction SilentlyContinue $part; Fail "copying $($f.Name) failed twice; nothing was replaced." }
    Move-Item -Force $part $final -ErrorAction Stop
}
$iso = Join-Path $dest "Halo-x86_64.iso"
Write-Host "`nDone: $iso ($([math]::Round((Get-Item $iso).Length / 1GB, 2)) GB), commit $($commit.Substring(0, 10))" -ForegroundColor Green
Write-Host "Next: packaging\windows-host\boot_test.ps1   (VM boot test, UEFI + BIOS)"
Write-Host "      packaging\windows-host\write_usb.md    (USB stick)"
