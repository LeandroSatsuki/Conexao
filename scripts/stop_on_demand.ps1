param(
    [switch]$RemoveVolumes
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot

try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker CLI not found."
    }

    $args = @("compose", "down")
    if ($RemoveVolumes) {
        $args += "--volumes"
    }

    Write-Host "Stopping Preferenza Connector stack..."
    & docker @args
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose down failed."
    }

    if ($RemoveVolumes) {
        Write-Host "Volumes were removed because -RemoveVolumes was set."
    }
    else {
        Write-Host "Volumes were preserved."
    }
}
finally {
    Pop-Location
}

