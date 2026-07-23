$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
$python = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
  $python = "python"
}
& $python -m PyInstaller `
  --noconfirm `
  --onefile `
  --windowed `
  --name FeedWatch `
  --paths . `
  --collect-all customtkinter `
  app\main.py
Write-Host "Build complete: dist\FeedWatch.exe"
