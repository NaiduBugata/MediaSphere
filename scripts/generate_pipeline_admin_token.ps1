# Generates a PIPELINE_ADMIN_TOKEN and prints exact next steps.
# Does not call Render or GitHub — you paste the value into both.
# Usage: powershell -ExecutionPolicy Bypass -File scripts/generate_pipeline_admin_token.ps1

$ErrorActionPreference = "Stop"
$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$token = [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "x").Replace("/", "y")

Write-Host ""
Write-Host "Generated PIPELINE_ADMIN_TOKEN:"
Write-Host $token
Write-Host ""
Write-Host "1) Render Dashboard -> mediasphere-api -> Environment"
Write-Host "   Add/Edit PIPELINE_ADMIN_TOKEN = (paste above) -> Save (redeploy if needed)"
Write-Host ""
Write-Host "2) GitHub -> Settings -> Secrets and variables -> Actions"
Write-Host "   New secret PIPELINE_ADMIN_TOKEN = (same value)"
Write-Host "   Optional: PIPELINE_BASE_URL = https://mediasphere-1.onrender.com"
Write-Host ""
Write-Host "3) Verify:"
Write-Host '   $env:PIPELINE_ADMIN_TOKEN = "<token>"'
Write-Host "   powershell -ExecutionPolicy Bypass -File scripts/check_pipeline_cron.ps1"
Write-Host ""
Write-Host "To also write into local server/.env (gitignored), re-run with -WriteEnv"
if ($args -contains "-WriteEnv") {
  $envFile = Join-Path $PSScriptRoot "..\server\.env"
  if (-not (Test-Path $envFile)) { throw "Missing $envFile" }
  $raw = Get-Content $envFile -Raw
  if ($raw -match "(?m)^PIPELINE_ADMIN_TOKEN=.*$") {
    $raw = [regex]::Replace($raw, "(?m)^PIPELINE_ADMIN_TOKEN=.*$", "PIPELINE_ADMIN_TOKEN=$token")
  } else {
    $raw = $raw.TrimEnd() + "`r`nPIPELINE_ADMIN_TOKEN=$token`r`n"
  }
  Set-Content -Path $envFile -Value $raw -NoNewline -Encoding UTF8
  Write-Host "Updated server/.env"
}
