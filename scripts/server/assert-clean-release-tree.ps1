$ErrorActionPreference = 'Stop'

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Push-Location $RepoRoot
try {
  git rev-parse --is-inside-work-tree | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw "Deploy blocked: $RepoRoot is not a git work tree"
  }

  $status = git status --porcelain=v1
  if ($status) {
    Write-Output 'Deploy blocked: working tree is dirty. Commit, stash, or discard local changes before production deploy.'
    git status --short
    exit 1
  }

  $sha = git rev-parse --verify HEAD
  Write-Output "Release tree clean: $sha"
} finally {
  Pop-Location
}
