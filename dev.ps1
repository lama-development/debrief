# dev.ps1 - Avvia backend (FastAPI) e frontend (Vite) con un solo comando.
#
#   Uso:  .\dev.ps1
#
# Apre due finestre PowerShell separate (una per il backend, una per il frontend)
# cosi' i log restano distinti e puoi fermare ciascun servizio con Ctrl+C.

$root = $PSScriptRoot

# Frontend: installa le dipendenze solo la prima volta (se manca node_modules).
if (-not (Test-Path "$root\frontend\node_modules")) {
    Write-Host "Prima esecuzione: installo le dipendenze del frontend..." -ForegroundColor Yellow
    Push-Location "$root\frontend"
    npm install
    Pop-Location
}

Write-Host ""
Write-Host "Avvio Debrief:" -ForegroundColor Cyan
Write-Host "  Backend  -> http://127.0.0.1:8000  (docs: /docs)"
Write-Host "  Frontend -> http://localhost:5173"
Write-Host ""

# Backend: uv run dev (uvicorn con reload).
$backendCmd = "`$Host.UI.RawUI.WindowTitle='Debrief Backend'; Set-Location '$root'; uv run dev"
Start-Process powershell -ArgumentList '-NoExit', '-Command', $backendCmd

# Frontend: npm run dev (Vite).
$frontendCmd = "`$Host.UI.RawUI.WindowTitle='Debrief Frontend'; Set-Location '$root\frontend'; npm run dev"
Start-Process powershell -ArgumentList '-NoExit', '-Command', $frontendCmd
