# Which developer tools does this Windows PC have for Halo work? Read-only; changes nothing.
#
#   powershell -ExecutionPolicy Bypass -File tools\dev_check.ps1 [-Json]
#
# Reports each tool as OK / MISSING with the command that installs it.
param([switch]$Json)
$ErrorActionPreference = "Continue"
$env:WSL_UTF8 = "1"

function Ver([string]$exe, [string[]]$a = @("--version")) {
    $c = Get-Command $exe -ErrorAction SilentlyContinue
    if (-not $c) { return $null }
    try { $o = (& $c.Source @a 2>&1 | Select-Object -First 1 | Out-String).Trim() } catch { $o = "" }
    if ($o) { return $o } else { return $c.Source }
}
$rows = New-Object System.Collections.Generic.List[object]
function Add([string]$name, $found, [string]$fix, [string]$why) {
    $rows.Add([pscustomobject]@{ Tool = $name; Status = $(if ($found) { "OK" } else { "MISSING" }); Detail = "$found"; Install = $(if ($found) { "" } else { $fix }); Needed = $why })
}

# WSL2 (+ a distro) for build_iso.ps1
$wsl = $null
if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
    $st = ((& wsl.exe --status 2>&1 | Out-String) -replace "`0", "")
    if ($LASTEXITCODE -eq 0 -and $st -notmatch "not installed|is not enabled") {
        $d = ((& wsl.exe -l -q 2>$null | Out-String) -split "`r?`n" | ForEach-Object { $_.Trim([char]0, ' ') } | Where-Object { $_ }) -join ", "
        $wsl = "WSL2; distros: " + $(if ($d) { $d } else { "none" })
    }
}
Add "WSL2" $wsl "wsl --install --no-distribution   (admin PowerShell, then restart)" "building the ISO (build_iso.ps1)"
$hasDistro = $wsl -and $wsl -notmatch "distros: none$"
Add "WSL distro" $(if ($hasDistro) { $wsl -replace '^WSL2; distros: ', '' } else { $null }) "wsl --install archlinux" "build_iso.ps1 runs podman inside it"

$docker = Ver "docker"
if (-not $docker -and (Test-Path "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe")) { $docker = "Docker Desktop installed (not running / not on PATH)" }
Add "Docker Desktop" $docker "winget install -e --id Docker.DockerDesktop" "optional; build_iso.ps1 uses podman in WSL"

$vbox = $null
foreach ($p in @("$env:VBOX_MSI_INSTALL_PATH\VBoxManage.exe", "$env:ProgramFiles\Oracle\VirtualBox\VBoxManage.exe")) {
    if ($p -and (Test-Path $p)) { $vbox = (& $p --version 2>$null | Out-String).Trim(); break }
}
Add "VirtualBox" $vbox "winget install -e --id Oracle.VirtualBox" "VM boot tests (boot_test.ps1)"

Add "git" (Ver "git") "winget install -e --id Git.Git" "source control"
Add "uv" (Ver "uv") "winget install -e --id astral-sh.uv" "SAINT's Python environment"
Add "node" (Ver "node") "winget install -e --id OpenJS.NodeJS.LTS" "Claude Code CLI (npm)"
Add "gh" (Ver "gh") "winget install -e --id GitHub.cli" "pull requests / releases"
Add "claude" (Ver "claude") "npm install -g @anthropic-ai/claude-code" "Evolve's coding agent (and this workflow)"

# USB writer: Ventoy or Rufus (portable copies are often just in Downloads)
$usb = $null
$hits = @()
foreach ($root in @("$env:ProgramFiles", "${env:ProgramFiles(x86)}", "$env:LOCALAPPDATA\Microsoft\WinGet\Packages", "$env:USERPROFILE\Downloads")) {
    if ($root -and (Test-Path $root)) {
        $hits += Get-ChildItem $root -Recurse -Depth 3 -File -Include "rufus*.exe", "Ventoy2Disk.exe" -ErrorAction SilentlyContinue | Select-Object -First 2
    }
}
if (Get-Command rufus -ErrorAction SilentlyContinue) { $usb = "rufus on PATH" }
elseif ($hits) { $usb = ($hits | ForEach-Object { $_.FullName }) -join "; " }
Add "USB writer (Rufus/Ventoy)" $usb "winget install -e --id Rufus.Rufus   (or: winget install -e --id Ventoy.Ventoy)" "writing the ISO to a USB stick"

# Firmware facts that matter for VMs and the install
$cs = Get-CimInstance Win32_ComputerSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$virt = if ($cs.HypervisorPresent) { "on (Hyper-V active)" } elseif ($cpu.VirtualizationFirmwareEnabled) { "on (SVM)" } else { $null }
Add "CPU virtualisation" $virt "enable SVM Mode in the UEFI setup (Del at power-on)" "WSL2 and VirtualBox"

if ($Json) { $rows | ConvertTo-Json; exit 0 }
$rows | Format-Table Tool, Status, Detail -AutoSize -Wrap
$missing = $rows | Where-Object Status -eq "MISSING"
if ($missing) {
    Write-Host "To install what's missing:" -ForegroundColor Yellow
    $missing | ForEach-Object { Write-Host ("  {0,-26} {1}" -f $_.Tool, $_.Install) }
} else { Write-Host "Everything needed is present." -ForegroundColor Green }
