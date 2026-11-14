# Prerequisites for Audio8Bit GUI on Windows
$ErrorActionPreference = 'Stop'
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
  Write-Error 'winget is not installed. Install Python 3.11 x64 and FFmpeg manually.'
  exit 1
}
winget install --id Python.Python.3.11 --exact --accept-source-agreements --accept-package-agreements
winget install --id Gyan.FFmpeg --exact --accept-source-agreements --accept-package-agreements
Write-Host 'Done. Restart Audio8BitGUI so it detects the updated PATH.'
