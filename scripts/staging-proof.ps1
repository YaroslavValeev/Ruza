param(
  [Parameter(Mandatory = $true)]
  [string]$ApiBaseUrl,

  [Parameter(Mandatory = $true)]
  [string]$DashboardUrl,

  [string]$Date = '2026-06-01',
  [string]$Origin = '',
  [string]$SessionCookie = '',
  [string]$SessionCookieName = 'icebeach_session',
  [switch]$AllowHttpForLocal,
  [switch]$ProbeOtpRequest,
  [string]$StaffUserId = '',
  [string]$Phone = ''
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$ScriptPath = Join-Path $RepoRoot 'scripts\staging_proof.py'

$argsList = @(
  $ScriptPath,
  '--api-base-url', $ApiBaseUrl,
  '--dashboard-url', $DashboardUrl,
  '--date', $Date,
  '--session-cookie-name', $SessionCookieName
)

if ($Origin) {
  $argsList += @('--origin', $Origin)
}
if ($SessionCookie) {
  $argsList += @('--session-cookie', $SessionCookie)
}
if ($AllowHttpForLocal) {
  $argsList += '--allow-http-for-local'
}
if ($ProbeOtpRequest) {
  $argsList += '--probe-otp-request'
}
if ($StaffUserId) {
  $argsList += @('--staff-user-id', $StaffUserId)
}
if ($Phone) {
  $argsList += @('--phone', $Phone)
}

python @argsList
exit $LASTEXITCODE
