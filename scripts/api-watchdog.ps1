param(
  [Parameter(Mandatory = $true)][string]$ApiDir,
  [Parameter(Mandatory = $true)][string]$OutLog,
  [Parameter(Mandatory = $true)][string]$ErrLog,
  [Parameter(Mandatory = $true)][string]$SupervisorLog,
  [Parameter(Mandatory = $true)][string]$PidFile,
  [int]$Port = 8000,
  [int]$RestartDelaySeconds = 2,
  [string]$BindHost = '127.0.0.1'
)
$ErrorActionPreference = 'Stop'

function Write-SupervisorLog([string]$Message) {
  $timestamp = Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK'
  Add-Content -Path $SupervisorLog -Value "$timestamp $Message" -Encoding UTF8
}

New-Item -ItemType Directory -Force -Path (Split-Path $OutLog), (Split-Path $ErrLog), (Split-Path $SupervisorLog) | Out-Null
Set-Content -Path $PidFile -Value $PID -Encoding UTF8
Write-SupervisorLog "watchdog started pid=$PID port=$Port host=$BindHost"

try {
  while ($true) {
    $proc = Start-Process -FilePath 'python' -WorkingDirectory $ApiDir -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', $BindHost, '--port', "$Port" -PassThru -WindowStyle Hidden -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog
    Write-SupervisorLog "worker started pid=$($proc.Id) host=$BindHost"
    $proc.WaitForExit()
    Write-SupervisorLog "worker exited pid=$($proc.Id) code=$($proc.ExitCode)"
    Start-Sleep -Seconds $RestartDelaySeconds
  }
} finally {
  Write-SupervisorLog "watchdog stopping pid=$PID"
  Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
}
