param(
  [int]$PrNumber = 4,
  [string]$ExpectedTag = '',
  [switch]$SkipTests,
  [switch]$SkipBuild,
  [switch]$SkipGitHub
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$AppRoot = Join-Path $RepoRoot 'icebeach-wakeclub'
$DashboardRoot = Join-Path $AppRoot 'apps\dashboard'

$script:Blockers = 0
$script:Warnings = 0
$script:External = 0

function Pass([string]$Code, [string]$Message) {
  Write-Output "[PASS] $Code`: $Message"
}

function Warn([string]$Code, [string]$Message) {
  Write-Output "[WARN] $Code`: $Message"
  $script:Warnings += 1
}

function Blocker([string]$Code, [string]$Message) {
  Write-Output "[BLOCKER] $Code`: $Message"
  $script:Blockers += 1
}

function External([string]$Code, [string]$Message) {
  Write-Output "[EXTERNAL] $Code`: $Message"
  $script:External += 1
}

function Require-Command([string]$Name) {
  $cmd = Get-Command $Name -ErrorAction SilentlyContinue
  return $null -ne $cmd
}

function Invoke-Step([string]$Code, [scriptblock]$Step) {
  try {
    & $Step
  } catch {
    Blocker $Code $_.Exception.Message
  }
}

Push-Location $RepoRoot
try {
  Write-Output '=== RUZA PRODUCTION V1 LOCAL AUDIT ==='
  Write-Output "Repo: $RepoRoot"
  Write-Output ''

  $head = (git rev-parse --verify HEAD).Trim()
  Pass 'git.head' $head

  $status = git status --porcelain=v1
  if ($status) {
    Blocker 'git.clean' 'working tree is dirty; production deploy is forbidden from dirty state'
    $status | ForEach-Object { Write-Output "  $_" }
  } else {
    Pass 'git.clean' 'working tree is clean'
  }

  $tagsAtHead = @(git tag --points-at HEAD)
  if (-not $ExpectedTag) {
    $ExpectedTag = $tagsAtHead |
      Where-Object { $_ -match '^v1\.0\.0-rc\.\d+$' } |
      Sort-Object { [int]($_ -replace '^v1\.0\.0-rc\.', '') } -Descending |
      Select-Object -First 1
    if (-not $ExpectedTag) {
      Blocker 'git.local_tag' 'no v1.0.0-rc.N tag points at HEAD'
    }
  }

  if ($tagsAtHead -contains $ExpectedTag) {
    Pass 'git.local_tag' "$ExpectedTag points at HEAD"
  } elseif ($ExpectedTag) {
    Blocker 'git.local_tag' "$ExpectedTag does not point at HEAD"
  }

  if (-not $SkipGitHub) {
    if (Require-Command 'gh') {
      Invoke-Step 'github.pr' {
        $pr = gh pr view $PrNumber --json headRefOid,mergeStateStatus,isDraft,statusCheckRollup,url | ConvertFrom-Json
        if ($pr.headRefOid -ne $head) {
          Blocker 'github.pr_sha' "PR #$PrNumber head $($pr.headRefOid) != local HEAD $head"
        } else {
          Pass 'github.pr_sha' "PR #$PrNumber matches local HEAD"
        }
        if ($pr.mergeStateStatus -eq 'CLEAN') {
          Pass 'github.merge_state' 'merge state CLEAN'
        } else {
          Blocker 'github.merge_state' "merge state $($pr.mergeStateStatus)"
        }
        if ($pr.isDraft) {
          Warn 'github.pr_draft' "PR #$PrNumber is draft until external production gates are complete"
        } else {
          Pass 'github.pr_draft' "PR #$PrNumber is ready for review"
        }
        $failedChecks = @($pr.statusCheckRollup | Where-Object { $_.conclusion -ne 'SUCCESS' })
        if ($failedChecks.Count -eq 0 -and $pr.statusCheckRollup.Count -gt 0) {
          Pass 'github.ci' "all $($pr.statusCheckRollup.Count) checks are green"
        } else {
          Blocker 'github.ci' 'one or more PR checks are not green'
          $failedChecks | ForEach-Object { Write-Output "  $($_.name): $($_.status) $($_.conclusion)" }
        }
        Write-Output "  PR: $($pr.url)"
      }

      Invoke-Step 'github.tag' {
        $tag = gh api "repos/YaroslavValeev/Ruza/git/refs/tags/$ExpectedTag" | ConvertFrom-Json
        if ($tag.object.sha -eq $head) {
          Pass 'github.remote_tag' "$ExpectedTag points at HEAD"
        } else {
          Blocker 'github.remote_tag' "$ExpectedTag points at $($tag.object.sha), expected $head"
        }
      }
    } else {
      Warn 'github.cli' 'gh CLI is unavailable; PR and remote tag checks skipped'
    }
  } else {
    Warn 'github.skipped' 'GitHub checks skipped by flag'
  }

  foreach ($path in @(
    'docs\PRODUCTION_V1_AUDIT.md',
    'docs\PRODUCTION_V1_GATES.md',
    'docs\INTAKE_SYNC.md',
    'docs\STAGING_DEPLOY.md',
    '.env.docker.example',
    'icebeach-wakeclub\apps\api\.env.production.example',
    'scripts\validate-production-env.ps1',
    'scripts\server\validate-production-env.sh',
    'scripts\test-production-env-guards.ps1',
    'scripts\server\test-production-env-guards.sh',
    'scripts\test-clean-release-tree.ps1',
    'scripts\server\test-clean-release-tree.sh'
  )) {
    if (Test-Path (Join-Path $RepoRoot $path)) {
      Pass "doc.$path" 'present'
    } else {
      Blocker "doc.$path" 'missing'
    }
  }

  Invoke-Step 'deploy.env_guard' {
    $deployScript = Get-Content -LiteralPath (Join-Path $RepoRoot 'scripts\server\deploy-api.sh') -Raw
    if ($deployScript -match 'validate-production-env\.sh') {
      Pass 'deploy.env_guard' 'deploy-api.sh validates production env before docker run'
    } else {
      Blocker 'deploy.env_guard' 'deploy-api.sh does not call validate-production-env.sh'
    }
  }

  Invoke-Step 'deploy.clean_guard' {
    $deployScript = Get-Content -LiteralPath (Join-Path $RepoRoot 'scripts\server\deploy-api.sh') -Raw
    if ($deployScript -match 'assert-clean-release-tree\.sh') {
      Pass 'deploy.clean_guard' 'deploy-api.sh validates clean release tree before docker run'
    } else {
      Blocker 'deploy.clean_guard' 'deploy-api.sh does not call assert-clean-release-tree.sh'
    }
  }

  Invoke-Step 'ci.env_guard' {
    $ci = Get-Content -LiteralPath (Join-Path $RepoRoot '.github\workflows\ci.yml') -Raw
    foreach ($jobName in @('production-env-guard-linux', 'production-env-guard-windows')) {
      if ($ci -notmatch [regex]::Escape($jobName)) {
        Blocker 'ci.env_guard' "$jobName missing from CI"
        return
      }
    }
    Pass 'ci.env_guard' 'production env guard runs in CI on Linux and Windows'
  }

  Invoke-Step 'ci.clean_guard' {
    $ci = Get-Content -LiteralPath (Join-Path $RepoRoot '.github\workflows\ci.yml') -Raw
    foreach ($jobName in @('clean-release-tree-guard-linux', 'clean-release-tree-guard-windows')) {
      if ($ci -notmatch [regex]::Escape($jobName)) {
        Blocker 'ci.clean_guard' "$jobName missing from CI"
        return
      }
    }
    Pass 'ci.clean_guard' 'clean release tree guard runs in CI on Linux and Windows'
  }

  if (-not $SkipTests) {
    Invoke-Step 'tests.api' {
      Push-Location $AppRoot
      try {
        python -m pytest -q
        if ($LASTEXITCODE -eq 0) {
          Pass 'tests.api' 'pytest passed'
        } else {
          Blocker 'tests.api' "pytest exited with $LASTEXITCODE"
        }
      } finally {
        Pop-Location
      }
    }
  } else {
    Warn 'tests.api' 'skipped by flag'
  }

  if (-not $SkipBuild) {
    Invoke-Step 'dashboard.build' {
      Push-Location $DashboardRoot
      try {
        npm run build
        if ($LASTEXITCODE -eq 0) {
          Pass 'dashboard.build' 'npm run build passed'
        } else {
          Blocker 'dashboard.build' "npm run build exited with $LASTEXITCODE"
        }
      } finally {
        Pop-Location
      }
    }
  } else {
    Warn 'dashboard.build' 'skipped by flag'
  }

  Write-Output ''
  Write-Output '=== EXTERNAL PRODUCTION V1 GATES ==='
  External 'timeweb.staging' 'deploy staging with HTTPS'
  External 'auth.otp_provider' 'configure and prove real OTP delivery provider'
  External 'intake.live_sources' 'prove live website and Telegram intake delivery'
  External 'backup.restore_write' 'run restore-test with -Write against a separate staging spreadsheet'
  External 'ops.monitoring' 'enable monitoring, alerting, and run rollback drill'
  External 'mobile.ios_safari' 'run core scenario on iOS Safari over HTTPS'
  External 'shift.real' 'complete one controlled real shift without P0 incident'

  Write-Output ''
  Write-Output "SUMMARY local_blockers=$script:Blockers warnings=$script:Warnings external_gates=$script:External"
  if ($script:Blockers -gt 0) {
    exit 1
  }
} finally {
  Pop-Location
}
