param(
  [string]$JsonPath = "service-account.json"
)
$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$fullPath = if ([IO.Path]::IsPathRooted($JsonPath)) { $JsonPath } else { Join-Path $repoRoot $JsonPath }

if (-not (Test-Path $fullPath)) {
  Write-Error "File not found: $fullPath"
}

$bytes = [IO.File]::ReadAllBytes($fullPath)
$b64 = [Convert]::ToBase64String($bytes)
$b64 | Set-Clipboard
Write-Output "GOOGLE_SERVICE_ACCOUNT_JSON_BASE64 ($($b64.Length) chars) copied to clipboard."
Write-Output "Paste into server .env.docker or Timeweb App env."
