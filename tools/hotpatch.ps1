<#
Dev hot-patch from Windows: copy this working tree's SAINT files to a running HalOS over SSH (into
/opt/saint/app) and restart SAINT there. Defaults to the test VM (127.0.0.1:2224, root). Uncommitted changes
are included; files git ignores are not. Uses Windows' own OpenSSH (ssh.exe, scp.exe) and tar.exe.

    tools\hotpatch.ps1 [-Host 127.0.0.1] [-Port 2224] [-User root] [-Key C:\path\to\key]
#>
param(
    [Alias("Host")][string]$HostName = "127.0.0.1",
    [int]$Port = 2224,
    [string]$User = "root",
    [string]$Key = ""
)
$ErrorActionPreference = "Stop"
$root = (git -C $PSScriptRoot rev-parse --show-toplevel).Trim()
Set-Location $root
$tmp = Join-Path ([IO.Path]::GetTempPath()) ("saint-hotpatch-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
    # Tracked and new files, without the ones deleted in the working tree.
    $files = git ls-files -co --exclude-standard | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf }
    $list = Join-Path $tmp "files.txt"
    [IO.File]::WriteAllLines($list, [string[]]$files, (New-Object Text.UTF8Encoding $false))
    $tar = Join-Path $tmp "saint-hotpatch.tar"
    & tar.exe -cf $tar -T $list
    if ($LASTEXITCODE -ne 0) { throw "tar failed" }
    Write-Host "hotpatch: $($files.Count) files -> $User@${HostName}:$Port"
    $opts = @("-o", "StrictHostKeyChecking=accept-new")
    if ($Key) { $opts += @("-i", $Key) }
    & scp.exe -P $Port @opts $tar (Join-Path $root "tools\hotpatch_remote.sh") "$User@${HostName}:/tmp/"
    if ($LASTEXITCODE -ne 0) { throw "scp failed" }
    & ssh.exe -p $Port @opts "$User@$HostName" "bash /tmp/hotpatch_remote.sh /tmp/saint-hotpatch.tar"
    if ($LASTEXITCODE -ne 0) { throw "the remote step failed" }
}
finally {
    Remove-Item -Recurse -Force -LiteralPath $tmp -ErrorAction SilentlyContinue
}
