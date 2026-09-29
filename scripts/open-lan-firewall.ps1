# Открывает порты 5173 (dashboard) и 8000 (API) для телефонов в локальной сети.
# Запускать от имени администратора PowerShell.
#Requires -RunAsAdministrator

$ErrorActionPreference = 'Stop'

$rules = @(
    @{ Name = 'Ice Beach Dashboard 5173'; Port = 5173 },
    @{ Name = 'Ice Beach API 8000'; Port = 8000 }
)

foreach ($rule in $rules) {
    $existing = Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue
    if ($existing) {
        Remove-NetFirewallRule -DisplayName $rule.Name
    }

    New-NetFirewallRule `
        -DisplayName $rule.Name `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $rule.Port `
        -Profile Any `
        | Out-Null

    Write-Host "Правило: $($rule.Name) TCP $($rule.Port) (все профили сети)" -ForegroundColor Green
}

Write-Host ''
& (Join-Path $PSScriptRoot 'mobile-lan-url.ps1')
