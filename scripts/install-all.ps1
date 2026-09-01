param(
    [switch]$SkipBrowsers,
    [switch]$SkipEnvFile
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$EnvironmentFile = Join-Path $RepoRoot "environment.yml"
$EnvTemplate = Join-Path $RepoRoot ".env.example"
$EnvFile = Join-Path $RepoRoot ".env"

if (-not (Get-Command conda -ErrorAction SilentlyContinue)) {
    throw "Conda was not found. Install Miniforge first, then rerun this script."
}

function Invoke-InEduAiEnvironment {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & conda run --no-capture-output --name edu-ai @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed in the edu-ai environment: $($Arguments -join ' ')"
    }
}

Write-Host "==> Create or update the edu-ai Conda environment" -ForegroundColor Cyan
& conda env update --name edu-ai --file $EnvironmentFile --prune
if ($LASTEXITCODE -ne 0) { throw "Conda environment update failed." }

Write-Host "==> Install OpenMAIC dependencies" -ForegroundColor Cyan
Invoke-InEduAiEnvironment pnpm --dir (Join-Path $RepoRoot "openmaic-sidecar") install --frozen-lockfile

Write-Host "==> Install frontend dependencies" -ForegroundColor Cyan
Invoke-InEduAiEnvironment pnpm --dir (Join-Path $RepoRoot "frontend") install --frozen-lockfile

if (-not $SkipBrowsers) {
    Write-Host "==> Install Playwright Chromium binaries" -ForegroundColor Cyan
    Invoke-InEduAiEnvironment pnpm --dir (Join-Path $RepoRoot "openmaic-sidecar") exec playwright install chromium
    Invoke-InEduAiEnvironment pnpm --dir (Join-Path $RepoRoot "frontend") exec playwright install chromium
}

if (-not $SkipEnvFile -and -not (Test-Path -LiteralPath $EnvFile)) {
    Copy-Item -LiteralPath $EnvTemplate -Destination $EnvFile
    Write-Host "==> Created $EnvFile; fill in secrets before starting services" -ForegroundColor Yellow
}

Write-Host "Installation complete." -ForegroundColor Green
