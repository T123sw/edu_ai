param(
    [switch]$SkipPython,
    [switch]$SkipNode,
    [switch]$SkipOptional,
    [switch]$SkipPlaywrightBrowsers,
    [switch]$SkipEnvFiles,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$FrontendDir = Join-Path $RepoRoot "Edu_AI"
$BackendDir = Join-Path $FrontendDir "api\src"
$Html2PptDir = Join-Path $BackendDir "modules\html2ppt"
$DomToPptxDir = Join-Path $Html2PptDir "dom-to-pptx"
$AiLecturerDir = Join-Path $BackendDir "modules\AI_Lecturer"
$EduAgentDir = Join-Path $RepoRoot "EduAgent"

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Block
    )
    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Block
}

function Assert-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found in PATH."
    }
}

function Get-NpmCommand {
    $npmCmd = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
    if ($npmCmd) {
        return $npmCmd.Source
    }

    $npm = Get-Command "npm" -ErrorAction SilentlyContinue
    if ($npm) {
        return $npm.Source
    }

    throw "Required command 'npm' was not found in PATH."
}

function Invoke-NpmCi {
    param([string]$Directory)
    $npm = Get-NpmCommand
    & $npm ci --prefix $Directory
}

function Copy-IfMissing {
    param(
        [string]$Source,
        [string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source)) {
        Write-Host "Skip missing template: $Source" -ForegroundColor Yellow
        return
    }

    if (Test-Path -LiteralPath $Destination) {
        Write-Host "Keep existing file: $Destination"
        return
    }

    Copy-Item -LiteralPath $Source -Destination $Destination
    Write-Host "Created: $Destination"
}

Write-Host "Edu-AI dependency installer"
Write-Host "Repository: $RepoRoot"

if (-not $SkipPython) {
    Assert-Command $Python
    Invoke-Step "Upgrade pip tooling" {
        & $Python -m pip install --upgrade pip setuptools wheel
    }
    Invoke-Step "Install backend Python dependencies" {
        & $Python -m pip install -r (Join-Path $BackendDir "requirements-media.txt")
    }
    if (-not $SkipOptional) {
        Invoke-Step "Install AI Lecturer offline-video Python dependencies" {
            & $Python -m pip install -r (Join-Path $AiLecturerDir "requirements-offline-py312.txt")
        }
        Invoke-Step "Install EduAgent Python dependencies" {
            & $Python -m pip install -r (Join-Path $EduAgentDir "requirements.txt")
        }
    }
    if (-not $SkipPlaywrightBrowsers) {
        Invoke-Step "Install Playwright Chromium browser" {
            & $Python -m playwright install chromium
        }
    }
}

if (-not $SkipNode) {
    Invoke-Step "Install frontend Node dependencies" {
        Invoke-NpmCi $FrontendDir
    }
    Invoke-Step "Install html2ppt service Node dependencies" {
        Invoke-NpmCi $Html2PptDir
    }
    Invoke-Step "Install dom-to-pptx Node dependencies" {
        Invoke-NpmCi $DomToPptxDir
    }
}

if (-not $SkipEnvFiles) {
    Invoke-Step "Create local env/config files when missing" {
        Copy-IfMissing (Join-Path $FrontendDir ".env.example") (Join-Path $FrontendDir ".env")
        Copy-IfMissing (Join-Path $BackendDir ".env.example") (Join-Path $BackendDir ".env")
        Copy-IfMissing (Join-Path $Html2PptDir ".env.example") (Join-Path $Html2PptDir ".env")
        Copy-IfMissing (Join-Path $EduAgentDir "config.toml.example") (Join-Path $EduAgentDir "config.toml")
    }
}

Write-Host ""
Write-Host "Dependency installation finished." -ForegroundColor Green
Write-Host "Next: fill local .env/config.toml files with real API keys and machine-specific paths."
