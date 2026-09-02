param(
  [string]$Validator = '.\scripts\validate-production-env.ps1'
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$ValidatorPath = Resolve-Path (Join-Path $RepoRoot $Validator)
$ValidEnv = Join-Path $env:TEMP 'ruza-production-env.valid'
$BadEnv = Join-Path $env:TEMP 'ruza-production-env.bad'

function Write-ValidEnv([string]$Path) {
  @'
APP_ENV=production
SPREADSHEET_ID=1Jos8absjdLueLoWXZDJS67PRHXfrQ-fnTq-yiXk2_18
INTAKE_SPREADSHEET_ID=1kyNQVjeLLe4Ra6oWuf84fHqSjUlWXI8MakVMOrCgic0
INTAKE_TAB_NAME=Ruza
GOOGLE_SERVICE_ACCOUNT_JSON_BASE64=eyJ0eXBlIjoic2VydmljZV9hY2NvdW50In0=
SESSION_SECRET=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
SESSION_MAX_AGE_SECONDS=28800
SESSION_COOKIE_NAME=icebeach_session
SESSION_COOKIE_SECURE=true
ALLOW_LEGACY_STAFF_LOGIN=false
AUTH_CODE_TTL_SECONDS=300
AUTH_CODE_RATE_LIMIT_WINDOW_SECONDS=600
AUTH_CODE_RATE_LIMIT_MAX_ATTEMPTS=5
AUTH_DEBUG_CODE_IN_RESPONSE=false
ALLOW_MANUAL_OTP_DELIVERY=false
OTP_DELIVERY_WEBHOOK_URL=https://otp.icebeach.ru/send
OTP_DELIVERY_WEBHOOK_TOKEN=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
OTP_DELIVERY_TIMEOUT_SECONDS=8
CORS_ALLOW_ORIGINS=https://dashboard.icebeach.ru
CORS_ALLOW_ORIGIN_REGEX=
API_HOST=0.0.0.0
API_PORT=8000
DISABLE_SYSTEM_PROXY_FOR_GOOGLE=true
SHEETS_TAB_CACHE_TTL_SECONDS=15
AGENTS_SECRET=cccccccccccccccccccccccccccccccc
AGENTS_STAFF_USER_ID=system-agent
AGENTS_API_BASE=http://api:8000
AGENTS_API_TIMEOUT_SECONDS=120
PUBLIC_CLUB_ID=ice_beach_ruza
'@ | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Write-BadEnv([string]$Path) {
  @'
APP_ENV=local
SPREADSHEET_ID=replace-me
INTAKE_SPREADSHEET_ID=replace-me
INTAKE_TAB_NAME=Ruza
GOOGLE_SERVICE_ACCOUNT_JSON_BASE64=replace-me
SESSION_SECRET=short
SESSION_COOKIE_SECURE=false
ALLOW_LEGACY_STAFF_LOGIN=false
AUTH_DEBUG_CODE_IN_RESPONSE=true
ALLOW_MANUAL_OTP_DELIVERY=true
OTP_DELIVERY_WEBHOOK_URL=http://localhost/send
OTP_DELIVERY_WEBHOOK_TOKEN=replace-me
CORS_ALLOW_ORIGINS=http://127.0.0.1:5173
AGENTS_SECRET=short
PUBLIC_CLUB_ID=ice_beach_ruza
'@ | Set-Content -LiteralPath $Path -Encoding UTF8
}

try {
  Write-Output '=== TEST PRODUCTION ENV GUARDS (PowerShell) ==='
  Write-ValidEnv $ValidEnv
  Write-BadEnv $BadEnv

  & powershell -ExecutionPolicy Bypass -File $ValidatorPath -EnvFile $ValidEnv
  if ($LASTEXITCODE -ne 0) {
    throw "valid production env was rejected with exit code $LASTEXITCODE"
  }
  Write-Output '[PASS] valid production env accepted'

  & powershell -ExecutionPolicy Bypass -File $ValidatorPath -EnvFile $BadEnv
  if ($LASTEXITCODE -eq 0) {
    throw 'bad debug/local env was accepted'
  }
  Write-Output '[PASS] bad debug/local env blocked'
} finally {
  Remove-Item -LiteralPath $ValidEnv,$BadEnv -Force -ErrorAction SilentlyContinue
}
