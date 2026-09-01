[CmdletBinding()]
param(
    [switch]$Quiet
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$runtimeDir = Join-Path $repoRoot '.runtime'
$manifestPath = Join-Path $runtimeDir 'dev-processes.json'

function Write-Status {
    param([string]$Message)
    if (-not $Quiet) {
        Write-Host "[Edu-AI] $Message" -ForegroundColor Cyan
    }
}

if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    Write-Status 'No managed local services are recorded.'
    exit 0
}

try {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $entries = @($manifest.processes)
    [array]::Reverse($entries)

    foreach ($entry in $entries) {
        $pidValue = [int]$entry.pid
        $commandFile = [string]$entry.commandFile
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $pidValue" -ErrorAction SilentlyContinue

        if ($null -eq $process) {
            Write-Status "$($entry.name) already stopped (PID $pidValue)."
        } elseif (-not ([string]$process.CommandLine).Contains($commandFile)) {
            Write-Status "Skipped reused or unowned PID $pidValue for $($entry.name)."
        } else {
            Write-Status "Stopping $($entry.name) (PID $pidValue)..."
            & taskkill.exe /PID $pidValue /T /F | Out-Null
        }

        if (Test-Path -LiteralPath $commandFile -PathType Leaf) {
            Remove-Item -LiteralPath $commandFile -Force
        }
    }

    Remove-Item -LiteralPath $manifestPath -Force
    Write-Status 'Managed local services stopped.'
    exit 0
} catch {
    Write-Host "[Edu-AI] ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
