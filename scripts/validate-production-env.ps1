param(
  [string]$EnvFile = '.env.docker'
)

$ErrorActionPreference = 'Stop'
$script:Blockers = 0

function Pass([string]$Code, [string]$Message) {
  Write-Output "[PASS] $Code`: $Message"
}

function Blocker([string]$Code, [string]$Message) {
  Write-Output "[BLOCKER] $Code`: $Message"
  $script:Blockers += 1
}

function Read-EnvFile([string]$Path) {
  $envMap = @{}
  Get-Content -LiteralPath $Path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
    $idx = $line.IndexOf('=')
    if ($idx -lt 1) { return }
    $key = $line.Substring(0, $idx).Trim()
    $value = $line.Substring($idx + 1).Trim().Trim('"').Trim("'")
    $envMap[$key] = $value
  }
  return $envMap
}

function Value([hashtable]$Env, [string]$Key) {
  if ($Env.ContainsKey($Key)) { return [string]$Env[$Key] }
  return ''
}

function Require-Value([hashtable]$Env, [string]$Key) {
  $value = Value $Env $Key
  if ([string]::IsNullOrWhiteSpace($value)) {
    Blocker $Key 'missing or empty'
  } else {
    Pass $Key 'present'
  }
}

function Require-Exact([hashtable]$Env, [string]$Key, [string]$Expected) {
  $value = Value $Env $Key
  if ($value -ceq $Expected) {
    Pass $Key "$Expected"
  } else {
    Blocker $Key "expected '$Expected', got '$value'"
  }
}

function Block-Placeholder([hashtable]$Env, [string]$Key) {
  $value = Value $Env $Key
  if ([string]::IsNullOrWhiteSpace($value)) { return }
  $patterns = @(
    'replace',
    'change-me',
    'your_',
    'example\.com',
    'example/',
    '<',
    '>'
  )
  foreach ($pattern in $patterns) {
    if ($value -match $pattern) {
      Blocker $Key 'contains placeholder/example value'
      return
    }
  }
}

function Require-Https([hashtable]$Env, [string]$Key) {
  $value = Value $Env $Key
  if ($value -match '^https://') {
    Pass $Key 'https'
  } else {
    Blocker $Key "must start with https://"
  }
}

$resolved = Resolve-Path -LiteralPath $EnvFile -ErrorAction SilentlyContinue
if (-not $resolved) {
  Blocker 'env.file' "not found: $EnvFile"
  Write-Output "SUMMARY blockers=$script:Blockers"
  exit 1
}

$envMap = Read-EnvFile $resolved.Path
Write-Output "=== PRODUCTION ENV VALIDATION ==="
Write-Output "Env file: $($resolved.Path)"

foreach ($key in @(
  'APP_ENV',
  'SPREADSHEET_ID',
  'INTAKE_SPREADSHEET_ID',
  'INTAKE_TAB_NAME',
  'SESSION_SECRET',
  'SESSION_COOKIE_SECURE',
  'ALLOW_LEGACY_STAFF_LOGIN',
  'AUTH_DEBUG_CODE_IN_RESPONSE',
  'ALLOW_MANUAL_OTP_DELIVERY',
  'OTP_DELIVERY_WEBHOOK_URL',
  'OTP_DELIVERY_WEBHOOK_TOKEN',
  'CORS_ALLOW_ORIGINS',
  'AGENTS_SECRET',
  'PUBLIC_CLUB_ID'
)) {
  Require-Value $envMap $key
  Block-Placeholder $envMap $key
}

Require-Exact $envMap 'APP_ENV' 'production'
Require-Exact $envMap 'SESSION_COOKIE_SECURE' 'true'
Require-Exact $envMap 'ALLOW_LEGACY_STAFF_LOGIN' 'false'
Require-Exact $envMap 'AUTH_DEBUG_CODE_IN_RESPONSE' 'false'
Require-Exact $envMap 'ALLOW_MANUAL_OTP_DELIVERY' 'false'
Require-Https $envMap 'OTP_DELIVERY_WEBHOOK_URL'

$cors = Value $envMap 'CORS_ALLOW_ORIGINS'
if ($cors -match 'localhost|127\.0\.0\.1|http://') {
  Blocker 'CORS_ALLOW_ORIGINS' 'production origins must be HTTPS public origins, not localhost/http'
} else {
  Pass 'CORS_ALLOW_ORIGINS' 'no localhost/http origins'
}

if ((Value $envMap 'SESSION_SECRET').Length -lt 32) {
  Blocker 'SESSION_SECRET' 'must be at least 32 characters'
} else {
  Pass 'SESSION_SECRET.length' '>= 32'
}

if ((Value $envMap 'AGENTS_SECRET').Length -lt 24) {
  Blocker 'AGENTS_SECRET' 'must be at least 24 characters'
} else {
  Pass 'AGENTS_SECRET.length' '>= 24'
}

$credentials = @()
foreach ($key in @(
  'GOOGLE_SERVICE_ACCOUNT_JSON',
  'GOOGLE_SERVICE_ACCOUNT_JSON_INLINE',
  'GOOGLE_SERVICE_ACCOUNT_JSON_BASE64'
)) {
  $credentialValue = Value $envMap $key
  if (-not [string]::IsNullOrWhiteSpace($credentialValue)) {
    $credentials += $key
  }
}

if ($credentials.Count -eq 1) {
  Pass 'google.credentials' 'exactly one credentials option configured'
} else {
  Blocker 'google.credentials' "configure exactly one of GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SERVICE_ACCOUNT_JSON_INLINE, GOOGLE_SERVICE_ACCOUNT_JSON_BASE64; found $($credentials.Count)"
}

Write-Output "SUMMARY blockers=$script:Blockers"
if ($script:Blockers -gt 0) {
  exit 1
}
