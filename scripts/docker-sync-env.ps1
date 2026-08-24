param(
  [switch]$Force
)
$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$sourceEnv = Join-Path $repoRoot '.env'
$targetEnv = Join-Path $repoRoot '.env.docker'
$serviceAccount = Join-Path $repoRoot 'service-account.json'

if (-not (Test-Path $sourceEnv)) {
  Write-Error "Missing $sourceEnv — create from .env.docker.example or merge from old 1.txt/2.txt"
}

if ((Test-Path $targetEnv) -and -not $Force) {
  Write-Output ".env.docker exists (use -Force to overwrite from .env)"
}

$lines = Get-Content $sourceEnv -Encoding UTF8
$map = @{}
foreach ($line in $lines) {
  $trimmed = $line.Trim()
  if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
  $idx = $trimmed.IndexOf('=')
  if ($idx -lt 1) { continue }
  $key = $trimmed.Substring(0, $idx).Trim()
  $value = $trimmed.Substring($idx + 1).Trim().Trim('"')
  $map[$key] = $value
}

$required = @('SPREADSHEET_ID', 'SESSION_SECRET')
foreach ($key in $required) {
  if (-not $map.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($map[$key])) {
    Write-Error "Missing $key in .env"
  }
}

if (-not (Test-Path $serviceAccount)) {
  Write-Warning "service-account.json not found at $serviceAccount — mount will fail until file exists"
}

function Get-EnvValue([hashtable]$Map, [string]$Key, [string]$Default = '') {
  if ($Map.ContainsKey($Key) -and -not [string]::IsNullOrWhiteSpace($Map[$Key])) {
    return $Map[$Key]
  }
  return $Default
}

$dockerLines = @(
  '# Auto-generated from .env by scripts/docker-sync-env.ps1',
  '# DO NOT COMMIT',
  'APP_ENV=local',
  "SPREADSHEET_ID=$(Get-EnvValue $map 'SPREADSHEET_ID')",
  "SESSION_SECRET=$(Get-EnvValue $map 'SESSION_SECRET')",
  "SESSION_MAX_AGE_SECONDS=$(Get-EnvValue $map 'SESSION_MAX_AGE_SECONDS' '28800')",
  "SESSION_COOKIE_NAME=$(Get-EnvValue $map 'SESSION_COOKIE_NAME' 'icebeach_session')",
  'SESSION_COOKIE_SECURE=false',
  "ALLOW_LEGACY_STAFF_LOGIN=$(Get-EnvValue $map 'ALLOW_LEGACY_STAFF_LOGIN' 'false')",
  "AUTH_CODE_TTL_SECONDS=$(Get-EnvValue $map 'AUTH_CODE_TTL_SECONDS' '900')",
  "AUTH_CODE_RATE_LIMIT_WINDOW_SECONDS=$(Get-EnvValue $map 'AUTH_CODE_RATE_LIMIT_WINDOW_SECONDS' '600')",
  "AUTH_CODE_RATE_LIMIT_MAX_ATTEMPTS=$(Get-EnvValue $map 'AUTH_CODE_RATE_LIMIT_MAX_ATTEMPTS' '5')",
  "AUTH_DEBUG_CODE_IN_RESPONSE=$(Get-EnvValue $map 'AUTH_DEBUG_CODE_IN_RESPONSE' 'true')",
  'API_HOST=0.0.0.0',
  'API_PORT=8000',
  'CORS_ALLOW_ORIGINS=http://127.0.0.1:5173,http://localhost:5173',
  'DISABLE_SYSTEM_PROXY_FOR_GOOGLE=true',
  'SHEETS_TAB_CACHE_TTL_SECONDS=15',
  'GOOGLE_SERVICE_ACCOUNT_JSON=/run/secrets/service-account.json',
  'VITE_API_BASE_URL=/api'
)

Set-Content -Path $targetEnv -Value ($dockerLines -join "`n") -Encoding UTF8 -NoNewline
Add-Content -Path $targetEnv -Value "`n" -Encoding UTF8

Write-Output "Synced .env -> .env.docker"
Write-Output "Google SA mount: service-account.json -> /run/secrets/service-account.json"
