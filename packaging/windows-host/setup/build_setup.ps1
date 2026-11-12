# Builds HalOS-Setup.exe with the C# compiler that comes with .NET Framework 4 (on every Windows 10/11; nothing
# to install). The two disk scripts are embedded in the EXE as resources.
#
#   powershell -ExecutionPolicy Bypass -File packaging\windows-host\setup\build_setup.ps1 [-Out dist\HalOS-Setup.exe]
param([string]$Out = "")
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$repo = (Resolve-Path "$here\..\..\..").Path
if (-not $Out) { $Out = Join-Path $repo "dist\HalOS-Setup.exe" }
New-Item -ItemType Directory -Force -Path (Split-Path $Out) | Out-Null
$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { throw "The .NET Framework 4 C# compiler isn't on this PC ($csc)." }
$hostDir = Split-Path $here
$args = @("/nologo", "/target:winexe", "/optimize+", "/out:$Out", "/win32manifest:$here\app.manifest",
          "/r:System.dll", "/r:System.Drawing.dll", "/r:System.Windows.Forms.dll",
          "/resource:$hostDir\prepare_disk_boot.ps1,prepare_disk_boot.ps1",
          "/resource:$hostDir\restart_into_halos.ps1,restart_into_halos.ps1")
$ico = Join-Path $here "HalOS.ico"
if (Test-Path $ico) { $args += "/win32icon:$ico" }
$args += "$here\HalOSSetup.cs"
& $csc @args
if ($LASTEXITCODE -ne 0) { throw "csc failed ($LASTEXITCODE)" }
"{0} ({1:N0} KB)" -f $Out, ((Get-Item $Out).Length / 1KB)
