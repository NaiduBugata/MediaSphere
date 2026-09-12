# Check production pipeline health + whether run-now is enabled.
# Usage: pwsh scripts/check_pipeline_cron.ps1
# Optional: $env:PIPELINE_ADMIN_TOKEN = "..." to probe run-now auth.

$ErrorActionPreference = "Stop"
$Base = if ($env:PIPELINE_BASE_URL) { $env:PIPELINE_BASE_URL.TrimEnd("/") } else { "https://mediasphere-1.onrender.com" }

Write-Host "Base URL: $Base"
Write-Host "GET /api/health ..."
$health = Invoke-RestMethod -Uri "$Base/api/health" -TimeoutSec 120
$health | ConvertTo-Json -Compress
Write-Host ""

Write-Host "GET /api/pipeline/health ..."
$pipe = Invoke-RestMethod -Uri "$Base/api/pipeline/health" -TimeoutSec 120
$pipe | ConvertTo-Json -Depth 5
Write-Host ""

if ($pipe.last_success) {
  $last = [datetime]::Parse($pipe.last_success).ToUniversalTime()
  $ageHrs = ([datetime]::UtcNow - $last).TotalHours
  Write-Host ("last_success age: {0:N1} hours (scheduler={1}, status={2})" -f $ageHrs, $pipe.scheduler, $pipe.status)
}

Write-Host ""
Write-Host "POST /api/pipeline/run-now (probe) ..."
$headers = @{ "Content-Type" = "application/json" }
if ($env:PIPELINE_ADMIN_TOKEN) {
  $headers["X-Pipeline-Admin-Token"] = $env:PIPELINE_ADMIN_TOKEN
}
try {
  $resp = Invoke-WebRequest -Uri "$Base/api/pipeline/run-now" -Method POST -Headers $headers -TimeoutSec 120 -UseBasicParsing
  Write-Host ("run-now HTTP {0}: {1}" -f $resp.StatusCode, $resp.Content)
} catch {
  $r = $_.Exception.Response
  if ($r) {
    $code = [int]$r.StatusCode
    $body = ""
    try {
      $reader = New-Object System.IO.StreamReader($r.GetResponseStream())
      $body = $reader.ReadToEnd()
    } catch {}
    Write-Host ("run-now HTTP {0}: {1}" -f $code, $body)
    if ($code -eq 503) {
      Write-Host "ACTION: Set PIPELINE_ADMIN_TOKEN on Render Dashboard → Environment, then mirror it in GitHub Actions secrets."
    } elseif ($code -eq 403) {
      Write-Host "Token is configured on Render, but this probe used a missing/wrong token."
    }
  } else {
    throw
  }
}
