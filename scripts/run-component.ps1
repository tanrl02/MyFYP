param([Parameter(Mandatory=$true)][ValidateSet('api','dashboard','mobile')][string]$Component)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
$runtimeRoot = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies'
$nodeDirectory = Join-Path $runtimeRoot 'node\bin'
$pnpmPath = Join-Path $runtimeRoot 'bin\fallback\pnpm.cmd'
if (Test-Path -LiteralPath $nodeDirectory) { $env:PATH = (Split-Path $pnpmPath -Parent) + ';' + $nodeDirectory + ';' + $env:PATH }
if (-not (Test-Path -LiteralPath $pnpmPath)) {
    $pnpmPath = (Get-Command pnpm.cmd -ErrorAction Stop).Source
}
switch ($Component) {
    'api' {
        Write-Host 'Synthetic demo API: http://127.0.0.1:8000/docs'
        Write-Host 'LAN access enabled for your phone. No real patient data or secure login.'
        & '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8000
    }
    'dashboard' {
        $env:NEXT_TELEMETRY_DISABLED = '1'
        Write-Host 'Open http://127.0.0.1:3000 in your browser.'
        & $pnpmPath dashboard
    }
    'mobile' {
        if (-not $env:EXPO_PUBLIC_API_URL) {
            $network = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.IPv4Address } | Select-Object -First 1
            if (-not $network) { throw 'No LAN address found. Set EXPO_PUBLIC_API_URL to http://your-computer-IP:8000 and retry.' }
            $phoneApiAddress = $network.IPv4Address.IPAddress | Select-Object -First 1
            $env:EXPO_PUBLIC_API_URL = 'http://' + $phoneApiAddress + ':8000'
        }
        $env:EXPO_NO_TELEMETRY = '1'
        Write-Host ('Phone API: ' + $env:EXPO_PUBLIC_API_URL)
        Write-Host 'Keep phone and computer on the same private Wi-Fi; scan the QR code in Expo Go.'
        & $pnpmPath mobile
    }
}
if ($LASTEXITCODE -ne 0) { throw "$Component exited with code $LASTEXITCODE. See the error above." }
