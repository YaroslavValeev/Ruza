$ErrorActionPreference = 'Stop'
$testRoot = Join-Path ([IO.Path]::GetFullPath($env:TEMP)) ("ruza-docker-sync-" + [guid]::NewGuid().ToString('N'))
$scriptsDir = Join-Path $testRoot 'scripts'
$sourceScript = Join-Path $PSScriptRoot 'docker-sync-env.ps1'
$fakeJson = '{"type":"service_account","project_id":"test-only"}'

try {
  New-Item -ItemType Directory -Path $scriptsDir -Force | Out-Null
  Copy-Item -LiteralPath $sourceScript -Destination (Join-Path $scriptsDir 'docker-sync-env.ps1')
  Set-Content -LiteralPath (Join-Path $testRoot '.env') -Value @(
    'SPREADSHEET_ID=test-spreadsheet',
    'SESSION_SECRET=test-session-secret'
  ) -Encoding UTF8
  Set-Content -LiteralPath (Join-Path $testRoot 'service-account.json') -Value $fakeJson -Encoding UTF8

  $scriptOutput = & (Join-Path $scriptsDir 'docker-sync-env.ps1') -Force
  $generated = Get-Content -LiteralPath (Join-Path $testRoot '.env.docker') -Raw
  if ($generated -notmatch '(?m)^GOOGLE_SERVICE_ACCOUNT_JSON_BASE64=([^\r\n]+)$') {
    throw 'Generated env is missing base64 credentials'
  }
  $decoded = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($Matches[1])).Trim()
  if ($decoded -ne $fakeJson) {
    throw 'Generated credentials do not round-trip to the source JSON'
  }
  if ($generated -match '(?m)^GOOGLE_SERVICE_ACCOUNT_JSON=' -or ($scriptOutput -join "`n") -match 'test-only') {
    throw 'Generated env or output exposes a legacy path or credential contents'
  }
  Write-Output '[PASS] docker-sync-env: base64 credentials round-trip without legacy path or secret output'
} finally {
  $tempRoot = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
  $resolvedTestRoot = [IO.Path]::GetFullPath($testRoot)
  if ($resolvedTestRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -and
      [IO.Path]::GetFileName($resolvedTestRoot).StartsWith('ruza-docker-sync-')) {
    Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force -ErrorAction SilentlyContinue
  }
}
