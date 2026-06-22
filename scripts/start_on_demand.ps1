param(
    [switch]$SkipHealthCheck
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot

try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker CLI not found."
    }

    Write-Host "Starting Preferenza Connector stack..."
    & docker compose up -d --build
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose up failed."
    }

    if (-not $SkipHealthCheck) {
        $healthUrl = "http://localhost:8000/api/v1/health"
        $maxAttempts = 30
        $delaySeconds = 5
        $healthy = $false

        for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
            try {
                $response = Invoke-RestMethod -Method Get -Uri $healthUrl -TimeoutSec 5
                if ($response.status) {
                    $healthy = $true
                    Write-Host "API health: $($response.status)"
                    break
                }
            }
            catch {
                Start-Sleep -Seconds $delaySeconds
            }
        }

        if (-not $healthy) {
            throw "API health check timed out. Check docker compose logs -f api."
        }
    }

    Write-Host "Migrations are run separately when needed:"
    Write-Host "  docker compose exec -T api alembic -c alembic.ini upgrade head"
    Write-Host "Suggested next command:"
    Write-Host "  .\scripts\run_sankhya_validation.ps1"
}
finally {
    Pop-Location
}

