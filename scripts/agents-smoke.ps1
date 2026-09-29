$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path $PSScriptRoot -Parent
$ApiBase = if ($env:AGENTS_API_BASE) { $env:AGENTS_API_BASE.TrimEnd('/') } else { 'http://127.0.0.1:8000' }
$Failures = 0

function Pass([string]$Code, [string]$Message) { Write-Output "[PASS] $Code`: $Message" }
function Fail([string]$Code, [string]$Message) { Write-Output "[FAIL] $Code`: $Message"; $script:Failures += 1 }

if (-not $env:AGENTS_SECRET) {
  Fail 'env.agents_secret' 'AGENTS_SECRET is empty — set in .env for full agents smoke'
}

try {
  $health = Invoke-RestMethod -Uri "$ApiBase/health"
  if ($health.status -eq 'ok') { Pass 'health' 'API ok' } else { Fail 'health' "status=$($health.status)" }
} catch {
  Fail 'health' $_.Exception.Message
}

if ($env:AGENTS_SECRET) {
  $headers = @{ 'X-Agents-Secret' = $env:AGENTS_SECRET }
  $date = (Get-Date).ToString('yyyy-MM-dd')
  foreach ($pair in @(
    @{ code = 'agents.preflight'; method = 'GET'; uri = "$ApiBase/internal/agents/preflight?date=$date" },
    @{ code = 'agents.brief'; method = 'GET'; uri = "$ApiBase/internal/agents/daily-brief?date=$date&mode=morning" },
    @{ code = 'agents.intake_sync'; method = 'POST'; uri = "$ApiBase/internal/agents/intake-sync" }
  )) {
    try {
      $resp = Invoke-RestMethod -Method $pair.method -Uri $pair.uri -Headers $headers
      Pass $pair.code 'ok'
      if ($pair.code -eq 'agents.preflight') {
        Write-Output "  blockers=$($resp.blockers) warnings=$($resp.warnings)"
      }
    } catch {
      Fail $pair.code $_.Exception.Message
    }
  }
}

Push-Location (Join-Path $RepoRoot 'icebeach-wakeclub')
try {
  $env:PYTHONPATH = '.'
  python -m apps.agents.cli list | Out-Null
  if ($LASTEXITCODE -eq 0) { Pass 'agents.cli' 'cli list ok' } else { Fail 'agents.cli' "exit=$LASTEXITCODE" }
} catch {
  Fail 'agents.cli' $_.Exception.Message
} finally {
  Pop-Location
}

Write-Output ''
Write-Output "SUMMARY failures=$Failures"
exit $(if ($Failures -gt 0) { 1 } else { 0 })
