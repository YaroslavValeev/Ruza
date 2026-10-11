param(
  [switch]$Unregister
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path $PSScriptRoot -Parent
$RunAgent = Join-Path $PSScriptRoot 'run-agent.ps1'

function Register-AgentTask {
  param(
    [string]$Name,
    [string]$Arguments,
    [string]$Schedule,
    [string]$StartTime
  )

  $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$RunAgent`" $Arguments"
  $trigger = switch ($Schedule) {
    'daily' { New-ScheduledTaskTrigger -Daily -At $StartTime }
    'minutes' { New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours(8) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Hours 14) }
    'reminders' {
      # A daily trigger renews repetition; a Once trigger would stop after day one.
      $daily = New-ScheduledTaskTrigger -Daily -At $StartTime
      $repeat = New-ScheduledTaskTrigger -Once -At $StartTime -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Days 1)
      $daily.Repetition = $repeat.Repetition
      $daily
    }
    default { throw "Unknown schedule $Schedule" }
  }
  if ($Schedule -eq 'reminders') {
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 3)
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  } else {
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Force | Out-Null
  }
  Write-Output "Registered task: $Name"
}

if ($Unregister) {
  @(
    'IceBeach-Agent-LateMarker',
    'IceBeach-Agent-Snapshot',
    'IceBeach-Agent-BriefMorning',
    'IceBeach-Agent-BriefEvening',
    'IceBeach-Agent-OpsAlert'
    'IceBeach-Agent-ShiftReminders'
  ) | ForEach-Object {
    Unregister-ScheduledTask -TaskName $_ -Confirm:$false -ErrorAction SilentlyContinue
    Write-Output "Unregistered: $_"
  }
  exit 0
}

Register-AgentTask -Name 'IceBeach-Agent-LateMarker' -Arguments '-Agent late_marker' -Schedule 'minutes' -StartTime '08:00'
Register-AgentTask -Name 'IceBeach-Agent-Snapshot' -Arguments '-Agent shift_snapshot' -Schedule 'daily' -StartTime '22:05'
Register-AgentTask -Name 'IceBeach-Agent-BriefMorning' -Arguments '-Agent daily_brief -Mode morning' -Schedule 'daily' -StartTime '07:00'
Register-AgentTask -Name 'IceBeach-Agent-BriefEvening' -Arguments '-Agent daily_brief -Mode evening' -Schedule 'daily' -StartTime '22:10'
Register-AgentTask -Name 'IceBeach-Agent-OpsAlert' -Arguments '-Agent ops_alert' -Schedule 'daily' -StartTime '06:55'
Register-AgentTask -Name 'IceBeach-Agent-ShiftReminders' -Arguments '-Agent shift_reminders' -Schedule 'reminders' -StartTime '00:00'

Write-Output 'Agents scheduled. Requires AGENTS_SECRET in .env and API running.'
