param(
    [string]$ApiBaseUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot

try {
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        Write-Host "Docker Compose status:"
        & docker compose ps
    }
    else {
        Write-Host "Docker CLI not found."
    }

    try {
        $health = Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/v1/health" -TimeoutSec 5
        Write-Host "API health: $($health.status)"
        Write-Host "Database: $($health.database)"
        Write-Host "Redis: $($health.redis)"
        Write-Host "Timestamp: $($health.timestamp)"
    }
    catch {
        Write-Host "API health check failed at $ApiBaseUrl/api/v1/health"
    }
}
finally {
    Pop-Location
}

