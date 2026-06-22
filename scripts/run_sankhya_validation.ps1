param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$requiredEnvVars = @(
    "SANKHYA_BASE_URL",
    "SANKHYA_CLIENT_ID",
    "SANKHYA_CLIENT_SECRET",
    "SANKHYA_X_TOKEN"
)

$missing = @()
foreach ($name in $requiredEnvVars) {
    if ([string]::IsNullOrWhiteSpace([System.Environment]::GetEnvironmentVariable($name))) {
        $missing += $name
    }
}

if ($missing.Count -gt 0) {
    throw "Missing required environment variables: $($missing -join ', ')"
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot

try {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        throw "Python CLI not found."
    }

    Write-Host "Running Sankhya read-only validation..."
    & python backend/scripts/validate_sankhya_readonly.py
    if ($LASTEXITCODE -ne 0) {
        throw "Validation script failed."
    }

    $reportDir = Join-Path $repoRoot "backend/reports"
    $latestReport = Get-ChildItem -Path $reportDir -Filter "sankhya_readonly_validation_*.json" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if ($latestReport) {
        Write-Host "Latest report: $($latestReport.FullName)"
    }
    else {
        Write-Host "Validation completed, but no report file was found."
    }
}
finally {
    Pop-Location
}

