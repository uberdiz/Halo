# Export what HalOS's "Bring everything" wizard brings, from inside Windows, to a USB drive or another disk.
# Use it before "Replace Windows", or when the Windows disk can't be read from HalOS (BitLocker, another PC).
#
#   powershell -ExecutionPolicy Bypass -File export_for_halos.ps1 -Destination E:\ [-NoFiles] [-Models] [-WifiPasswords]
#
# Reads only: nothing on this PC is changed, moved or deleted. Writes E:\HalOS-Export\, laid out like a Windows
# profile (Users\<you>\...), so HalOS reads it exactly like a Windows disk. Close your browsers first so their
# bookmark files aren't locked.
#   -NoFiles        skip Documents, Desktop, Pictures, Music, Videos, Downloads (just settings, apps, history)
#   -Models         also copy AI models from Ollama (can be many GB; saves downloading them again)
#   -WifiPasswords  also export saved Wi-Fi passwords (in plain text in the export: keep the drive safe)
param(
    [Parameter(Mandatory = $true)][string]$Destination,
    [switch]$NoFiles,
    [switch]$Models,
    [switch]$WifiPasswords,
    [switch]$WhatIf
)
$ErrorActionPreference = "Stop"
$user = $env:USERNAME
$profileDir = $env:USERPROFILE
$out = Join-Path $Destination "HalOS-Export"
$me = Join-Path $out "Users\$user"
$parts = New-Object System.Collections.Generic.List[string]

function Copy-Part([string]$from, [string]$to, [string]$what, [string[]]$exclude = @()) {
    if (-not (Test-Path -LiteralPath $from)) { return }
    "  $what"
    if ($WhatIf) { return }
    New-Item -ItemType Directory -Force -Path (Split-Path $to) | Out-Null
    if (Test-Path -LiteralPath $from -PathType Leaf) {
        Copy-Item -LiteralPath $from -Destination $to -Force
    } else {
        $xf = @(); foreach ($e in $exclude) { $xf += $e }
        $args = @($from, $to, "/E", "/R:1", "/W:1", "/NFL", "/NDL", "/NJH", "/NJS", "/NP", "/XJ")
        if ($xf.Count) { $args += "/XF"; $args += $xf }
        robocopy @args | Out-Null
        if ($LASTEXITCODE -ge 8) { Write-Warning "Some files of '$what' couldn't be copied (are they open?)." }
    }
    $script:parts.Add($what)
}

$need = 2GB
if (-not $NoFiles) {
    foreach ($f in "Documents", "Desktop", "Pictures", "Music", "Videos", "Downloads") {
        $p = Join-Path $profileDir $f
        if (Test-Path $p) { $need += (Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum }
    }
}
$free = (Get-PSDrive -Name ($Destination.Substring(0, 1))).Free
"Export for HalOS: $user on $env:COMPUTERNAME -> $out"
"  needs about {0:N1} GB, {1:N1} GB free there" -f ($need / 1GB), ($free / 1GB)
if ($free -lt $need) { throw "Not enough space on $Destination. Use a bigger drive, or -NoFiles." }

if (-not $NoFiles) {
    foreach ($f in "Documents", "Desktop", "Pictures", "Music", "Videos", "Downloads") {
        Copy-Part (Join-Path $profileDir $f) (Join-Path $me $f) $f
    }
}
# Browsers: bookmarks only (the same files the wizard reads from a Windows disk). No passwords or cookies.
foreach ($b in @(@("Google\Chrome\User Data", "Chrome"), @("Microsoft\Edge\User Data", "Edge"),
                 @("BraveSoftware\Brave-Browser\User Data", "Brave"))) {
    $base = Join-Path $env:LOCALAPPDATA $b[0]
    if (-not (Test-Path $base)) { continue }
    Get-ChildItem $base -Directory | Where-Object { $_.Name -eq "Default" -or $_.Name -like "Profile *" } | ForEach-Object {
        Copy-Part (Join-Path $_.FullName "Bookmarks") (Join-Path $me "AppData\Local\$($b[0])\$($_.Name)\Bookmarks") "$($b[1]) bookmarks ($($_.Name))"
    }
}
$ff = Join-Path $env:APPDATA "Mozilla\Firefox\Profiles"
if (Test-Path $ff) {
    Get-ChildItem $ff -Directory | ForEach-Object {
        Copy-Part (Join-Path $_.FullName "places.sqlite") (Join-Path $me "AppData\Roaming\Mozilla\Firefox\Profiles\$($_.Name)\places.sqlite") "Firefox bookmarks"
    }
}
# SAINT, Claude, VS Code, fonts, wallpaper
Copy-Part (Join-Path $env:LOCALAPPDATA "SAINT") (Join-Path $me "AppData\Local\SAINT") "SAINT history and memory" @("*.onnx", "*.bin", "*.gguf", "*.safetensors")
Copy-Part (Join-Path $profileDir ".claude") (Join-Path $me ".claude") "Claude Code history, settings and skills" @(".credentials.json", "credentials.json")
Copy-Part (Join-Path $env:APPDATA "Claude\claude_desktop_config.json") (Join-Path $me "AppData\Roaming\Claude\claude_desktop_config.json") "Claude app MCP servers"
Copy-Part (Join-Path $env:APPDATA "Code\User") (Join-Path $me "AppData\Roaming\Code\User") "VS Code settings" @("*.vscdb", "*.vscdb.backup")
$ext = Join-Path $profileDir ".vscode\extensions"
if (Test-Path $ext) {
    "  VS Code extension list"
    if (-not $WhatIf) {
        New-Item -ItemType Directory -Force -Path (Join-Path $me ".vscode\extensions") | Out-Null
        Get-ChildItem $ext -Directory | ForEach-Object { New-Item -ItemType Directory -Force -Path (Join-Path $me ".vscode\extensions\$($_.Name)") | Out-Null }
    }
    $parts.Add("VS Code extension list")
}
Copy-Part (Join-Path $env:LOCALAPPDATA "Microsoft\Windows\Fonts") (Join-Path $me "AppData\Local\Microsoft\Windows\Fonts") "Fonts you installed"
Copy-Part (Join-Path $env:APPDATA "Microsoft\Windows\Themes\TranscodedWallpaper") (Join-Path $me "AppData\Roaming\Microsoft\Windows\Themes\TranscodedWallpaper") "Wallpaper"
if ($Models) {
    Copy-Part (Join-Path $profileDir ".ollama\models") (Join-Path $me ".ollama\models") "AI models (Ollama)"
}

# Installed apps (names only), for the Apps step
"  Installed apps list"
$apps = foreach ($k in "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
                       "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
                       "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*") {
    Get-ItemProperty $k -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -and -not $_.SystemComponent } |
        ForEach-Object { [pscustomobject]@{ name = $_.DisplayName; publisher = $_.Publisher } }
}
$parts.Add("Installed apps list")

# Wi-Fi networks: names always; passwords only with -WifiPasswords
"  Wi-Fi networks" + $(if ($WifiPasswords) { " (with passwords)" } else { " (names only)" })
$parts.Add("Wi-Fi networks")
if (-not $WhatIf) {
    New-Item -ItemType Directory -Force -Path $out | Out-Null
    $apps | Sort-Object name -Unique | ConvertTo-Json -Depth 2 | Set-Content -Path (Join-Path $out "apps.json") -Encoding utf8
    $wifi = Join-Path $out "wifi"
    New-Item -ItemType Directory -Force -Path $wifi | Out-Null
    if ($WifiPasswords) { netsh wlan export profile folder="$wifi" key=clear | Out-Null }
    else { netsh wlan export profile folder="$wifi" | Out-Null }
    [pscustomobject]@{ version = 1; user = $user; computer = $env:COMPUTERNAME; created = (Get-Date).ToString("o");
                       windows = [Environment]::OSVersion.VersionString; parts = $parts } |
        ConvertTo-Json | Set-Content -Path (Join-Path $out "HALOS-EXPORT.json") -Encoding utf8
}
""
if ($WhatIf) { "WhatIf: nothing was written." } else { "Done. In HalOS, open Settings > Migrate from Windows; it finds $out on the drive." }
