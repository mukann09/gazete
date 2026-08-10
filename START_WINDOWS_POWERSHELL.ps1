$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "============================================"
Write-Host "  GUNDEM DEFTERI - YEREL SUNUCU"
Write-Host "============================================"
Write-Host ""
Write-Host "Klasor: $PWD"

$cmd = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $cmd = @("py","-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $cmd = @("python")
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $cmd = @("python3")
}

if (-not $cmd) {
    Write-Host ""
    Write-Host "HATA: Python bulunamadi." -ForegroundColor Red
    Write-Host "Python kurulumu: https://www.python.org/downloads/"
    Read-Host "Kapatmak icin Enter"
    exit 1
}

Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:8000"
} | Out-Null

Write-Host ""
Write-Host "Sunucu baslatiliyor: http://localhost:8000"
Write-Host "Bu pencereyi acik tutun."
Write-Host ""

if ($cmd.Count -eq 2) {
    & $cmd[0] $cmd[1] -m http.server 8000
} else {
    & $cmd[0] -m http.server 8000
}
