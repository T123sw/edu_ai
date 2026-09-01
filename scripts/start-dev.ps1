[CmdletBinding()]
param(
    [switch]$Check,
    [switch]$NoBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$frontendDir = Join-Path $repoRoot 'frontend'
$backendDir = Join-Path $repoRoot 'backend/src'
$openmaicDir = Join-Path $repoRoot 'openmaic-sidecar'
$runtimeDir = Join-Path $repoRoot '.runtime'
$manifestPath = Join-Path $runtimeDir 'dev-processes.json'
$envPath = Join-Path $repoRoot '.env'

function Write-Stage {
    param([string]$Message)
    Write-Host "[Edu-AI] $Message" -ForegroundColor Cyan
}

function Assert-File {
    param([string]$Path, [string]$Description)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Description not found: $Path"
    }
}

function Assert-Directory {
    param([string]$Path, [string]$Description)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Description not found: $Path"
    }
}

function Resolve-CommandPath {
    param([string]$Name)
    $command = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $command) {
        throw "Required command was not found: $Name"
    }
    return $command.Source
}

function Import-DotEnv {
    param([string]$Path)

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) {
            continue
        }

        $parts = $trimmed.Split(@('='), 2)
        if ($parts.Count -ne 2) {
            continue
        }

        $name = $parts[0].Trim()
        if ($name -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
            continue
        }

        $value = $parts[1].Trim()
        if ($value.Length -ge 2) {
            $first = $value.Substring(0, 1)
            $last = $value.Substring($value.Length - 1, 1)
            if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
}

function Assert-PortFree {
    param([int]$Port, [string]$Service)

    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    if ($listeners.Count -gt 0) {
        $owners = ($listeners | Select-Object -ExpandProperty OwningProcess -Unique) -join ', '
        throw "$Service port $Port is already occupied by PID(s): $owners. Run stop.bat if this is an Edu-AI process."
    }
}

function Write-Manifest {
    param([System.Collections.IDictionary]$Manifest)

    $Manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
}

function New-ServiceCommandFile {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$Command
    )

    $path = Join-Path $runtimeDir "$Name.cmd"
    $lines = @(
        '@echo off',
        "title Edu-AI $Name",
        "cd /d `"$WorkingDirectory`"",
        $Command
    )
    $lines | Set-Content -LiteralPath $path -Encoding ASCII
    return $path
}

function Wait-ForHttp {
    param(
        [string]$Name,
        [string]$Uri,
        [int]$TimeoutSeconds = 120
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 3
            if ([int]$response.StatusCode -ge 200 -and [int]$response.StatusCode -lt 500) {
                Write-Stage "$Name is ready: $Uri"
                return
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "$Name did not become ready within $TimeoutSeconds seconds: $Uri"
}

try {
    Write-Stage "Validating canonical repository layout at $repoRoot"
    Assert-File (Join-Path $frontendDir 'package.json') 'Frontend package.json'
    Assert-File (Join-Path $backendDir 'app/main.py') 'FastAPI entrypoint'
    Assert-File (Join-Path $openmaicDir 'package.json') 'OpenMAIC package.json'
    Assert-File (Join-Path $openmaicDir 'app/api/health/route.ts') 'OpenMAIC health route'
    Assert-File $envPath 'Root .env (copy .env.example to .env first)'
    Assert-Directory (Join-Path $frontendDir 'node_modules') 'Frontend dependencies'
    Assert-Directory (Join-Path $openmaicDir 'node_modules') 'OpenMAIC dependencies'

    $pythonPath = Resolve-CommandPath 'python.exe'
    $pythonVersion = (& $pythonPath --version 2>&1 | Out-String).Trim()
    if ($pythonVersion -notmatch '^Python 3\.12(\.|$)') {
        throw "Python 3.12 is required; found $pythonVersion at $pythonPath"
    }
    & $pythonPath -c 'import fastapi, uvicorn' 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "FastAPI/Uvicorn imports failed for $pythonPath. Run scripts/install-all.ps1."
    }

    $nodePath = Resolve-CommandPath 'node.exe'
    $nodeVersion = (& $nodePath --version 2>&1 | Out-String).Trim()
    if ($nodeVersion -notmatch '^v(?<major>\d+)\.') {
        throw "Could not parse Node.js version: $nodeVersion"
    }
    if ([int]$Matches.major -lt 22) {
        throw "Node.js 22 or newer is required for Windows development; found $nodeVersion at $nodePath"
    }

    $corepackPath = Resolve-CommandPath 'corepack.cmd'
    $pnpmVersion = (& $corepackPath pnpm --version 2>&1 | Out-String).Trim()
    if ($pnpmVersion -notmatch '^10\.') {
        throw "pnpm 10 is required; found $pnpmVersion"
    }

    foreach ($service in @(
        @{ Port = 3000; Name = 'OpenMAIC' },
        @{ Port = 8001; Name = 'FastAPI' },
        @{ Port = 5173; Name = 'Frontend' }
    )) {
        Assert-PortFree -Port $service.Port -Service $service.Name
    }

    if (Test-Path -LiteralPath $manifestPath) {
        throw "A stale launcher manifest exists: $manifestPath. Run stop.bat before starting again."
    }

    Import-DotEnv -Path $envPath
    Write-Stage "Python: $pythonVersion"
    Write-Stage "Node.js: $nodeVersion"
    Write-Stage "pnpm: $pnpmVersion"

    if ($Check) {
        Write-Stage 'Startup check passed. No services were started.'
        exit 0
    }

    New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
    $localDataRoot = Join-Path $runtimeDir 'data'
    New-Item -ItemType Directory -Path $localDataRoot -Force | Out-Null
    foreach ($mapping in @{
        STORAGE_ROOT = 'storage'
        COURSE_STORAGE_ROOT = 'course_data'
        TEMP_DIR = 'tmp'
        OPENMAIC_DATA_ROOT = 'openmaic'
    }.GetEnumerator()) {
        $current = [Environment]::GetEnvironmentVariable($mapping.Key, 'Process')
        if (-not $current -or $current.StartsWith('/data/edu_ai/')) {
            $localPath = Join-Path $localDataRoot $mapping.Value
            New-Item -ItemType Directory -Path $localPath -Force | Out-Null
            [Environment]::SetEnvironmentVariable($mapping.Key, $localPath, 'Process')
        }
    }
    $journal = [Environment]::GetEnvironmentVariable('SHADOW_FAILURE_JOURNAL', 'Process')
    if (-not $journal -or $journal.StartsWith('/data/edu_ai/')) {
        [Environment]::SetEnvironmentVariable(
            'SHADOW_FAILURE_JOURNAL',
            (Join-Path $localDataRoot 'storage/database_shadow_failures.jsonl'),
            'Process'
        )
    }

    $manifest = [ordered]@{
        repoRoot = $repoRoot
        startedAtUtc = [DateTime]::UtcNow.ToString('o')
        processes = @()
    }

    $services = @(
        @{
            Name = 'openmaic'
            DisplayName = 'OpenMAIC'
            WorkingDirectory = $openmaicDir
            Command = "call `"$corepackPath`" pnpm dev -- --hostname 127.0.0.1 --port 3000"
            Port = 3000
            Health = 'http://127.0.0.1:3000/api/health'
        },
        @{
            Name = 'backend'
            DisplayName = 'FastAPI'
            WorkingDirectory = $backendDir
            Command = "`"$pythonPath`" -m uvicorn app.main:app --host 127.0.0.1 --port 8001"
            Port = 8001
            Health = 'http://127.0.0.1:8001/health'
        },
        @{
            Name = 'frontend'
            DisplayName = 'Frontend'
            WorkingDirectory = $frontendDir
            Command = "set `"VITE_API_BASE_URL=http://127.0.0.1:8001`" && call `"$corepackPath`" pnpm dev -- --host 127.0.0.1 --port 5173"
            Port = 5173
            Health = 'http://127.0.0.1:5173/'
        }
    )

    foreach ($service in $services) {
        Write-Stage "Starting $($service.DisplayName)..."
        $commandFile = New-ServiceCommandFile -Name $service.Name -WorkingDirectory $service.WorkingDirectory -Command $service.Command
        $process = Start-Process -FilePath $env:ComSpec -WorkingDirectory $service.WorkingDirectory -ArgumentList @('/d', '/k', "`"$commandFile`"") -PassThru
        $manifest.processes += [ordered]@{
            name = $service.Name
            pid = $process.Id
            port = $service.Port
            commandFile = $commandFile
        }
        Write-Manifest -Manifest $manifest
        Wait-ForHttp -Name $service.DisplayName -Uri $service.Health
    }

    Write-Stage 'All services are healthy.'
    Write-Host 'Frontend:  http://127.0.0.1:5173'
    Write-Host 'Backend:   http://127.0.0.1:8001/docs'
    Write-Host 'OpenMAIC:  http://127.0.0.1:3000'

    if (-not $NoBrowser) {
        Start-Process 'http://127.0.0.1:5173'
    }
    exit 0
} catch {
    Write-Host "[Edu-AI] ERROR: $($_.Exception.Message)" -ForegroundColor Red
    if (Test-Path -LiteralPath $manifestPath) {
        & (Join-Path $PSScriptRoot 'stop-dev.ps1') -Quiet
    }
    exit 1
}
