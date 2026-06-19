param(
  [string]$Date = '2026-06-10',
  [string]$StaffUserId = '23232323',
  [string]$Phone = '+79160117179',
  [string]$ClientQuery = '+79160117179',
  [string]$RideType = 'skim'
)

$ErrorActionPreference = 'Stop'
$ApiBase = 'http://127.0.0.1:8000'
$Script:Failures = 0

function Pass([string]$Code, [string]$Message) {
  Write-Output "[PASS] $Code`: $Message"
}

function Fail([string]$Code, [string]$Message) {
  Write-Output "[FAIL] $Code`: $Message"
  $Script:Failures += 1
}

function Assert-True([bool]$Condition, [string]$Code, [string]$PassMessage, [string]$FailMessage) {
  if ($Condition) {
    Pass $Code $PassMessage
  } else {
    Fail $Code $FailMessage
  }
}

Write-Output "=== SMOKE DATE ==="
Write-Output $Date
Write-Output ''

try {
  $health = Invoke-RestMethod -Uri "$ApiBase/health"
  Assert-True ($health.status -eq 'ok') 'health' 'API health is ok' "unexpected health payload: $($health | ConvertTo-Json -Compress)"
} catch {
  Fail 'health' $_.Exception.Message
  Write-Output "SUMMARY failures=$Script:Failures"
  exit 1
}

$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

try {
  $requestCodeBody = @{ staff_user_id = $StaffUserId; phone = $Phone } | ConvertTo-Json
  $codeResp = Invoke-RestMethod -WebSession $session -Method Post -Uri "$ApiBase/auth/request-code" -ContentType 'application/json' -Body $requestCodeBody
  Assert-True (-not [string]::IsNullOrWhiteSpace($codeResp.debug_code)) 'auth.request_code' 'debug code issued' 'debug code is empty'

  $verifyBody = @{ staff_user_id = $StaffUserId; code = $codeResp.debug_code } | ConvertTo-Json
  $loginResp = Invoke-RestMethod -WebSession $session -Method Post -Uri "$ApiBase/auth/verify-code" -ContentType 'application/json' -Body $verifyBody
  Assert-True (-not [string]::IsNullOrWhiteSpace($loginResp.role)) 'auth.verify_code' "session role=$($loginResp.role)" 'login response missing role'
} catch {
  Fail 'auth' $_.Exception.Message
  Write-Output "SUMMARY failures=$Script:Failures"
  exit 1
}

try {
  $preflight = Invoke-RestMethod -WebSession $session -Uri "$ApiBase/preflight/summary?date=$Date"
  Assert-True ($preflight.blockers -eq 0) 'preflight.blockers' 'no blockers' "blockers=$($preflight.blockers)"
  Assert-True ($preflight.warnings -eq 0) 'preflight.warnings' 'no warnings' "warnings=$($preflight.warnings)"
} catch {
  Fail 'preflight' $_.Exception.Message
}

$slot = $null
try {
  $availability = Invoke-RestMethod -WebSession $session -Uri "$ApiBase/availability?date=$Date"
  $slot = $availability | Where-Object { $_.available -gt 0 -and $_.status -eq 'active' } | Select-Object -Last 1
  Assert-True ($null -ne $slot) 'availability.slot' 'free slot found' 'no free slot found'
} catch {
  Fail 'availability' $_.Exception.Message
}

$client = $null
try {
  $clients = Invoke-RestMethod -WebSession $session -Uri "$ApiBase/clients?query=$([uri]::EscapeDataString($ClientQuery))"
  $client = $clients | Select-Object -First 1
  Assert-True ($null -ne $client) 'clients.query' "client=$($client.client_id)" 'no client found'
} catch {
  Fail 'clients' $_.Exception.Message
}

$createdBooking = $null
if ($slot -and $client) {
  try {
    $payload = @{
      client_id = $client.client_id
      date = $Date
      time = $slot.time
      boat_id = $slot.boat_id
      coach_required = $false
      ride_type = $RideType
      wetsuit_required = $true
      wetsuit_size = 'XL'
      wetsuit_gender = 'male'
      discount = 0
      notes = 'smoke-test-auto'
    } | ConvertTo-Json

    $bookingCreate = Invoke-RestMethod -WebSession $session -Method Post -Uri "$ApiBase/bookings" -ContentType 'application/json' -Body $payload
    Assert-True ($bookingCreate.status -eq 'confirmed') 'bookings.create' "created=$($bookingCreate.booking_id)" "unexpected status=$($bookingCreate.status)"

    $bookingsAfterCreate = Invoke-RestMethod -WebSession $session -Uri "$ApiBase/bookings?date=$Date"
    $createdBooking = $bookingsAfterCreate | Where-Object { $_.booking_id -eq $bookingCreate.booking_id } | Select-Object -First 1
    Assert-True ($null -ne $createdBooking) 'bookings.persisted' 'created booking found in list' 'created booking missing from list'
    if ($createdBooking) {
      Assert-True ($createdBooking.ride_type -eq $RideType) 'bookings.ride_type' "ride_type=$($createdBooking.ride_type)" "ride_type=$($createdBooking.ride_type)"
      Assert-True ($createdBooking.wetsuit_gender -eq 'male') 'bookings.wetsuit_gender' "gender=$($createdBooking.wetsuit_gender)" "gender=$($createdBooking.wetsuit_gender)"
      Assert-True ($createdBooking.wetsuit_size -eq 'XL') 'bookings.wetsuit_size' "size=$($createdBooking.wetsuit_size)" "size=$($createdBooking.wetsuit_size)"
    }

    $pilotQueue = Invoke-RestMethod -WebSession $session -Uri "$ApiBase/pilot/today?boat_id=$($slot.boat_id)&date_from=$Date&date_to=$Date"
    $pilotItem = $pilotQueue | Where-Object { $_.booking_id -eq $bookingCreate.booking_id } | Select-Object -First 1
    Assert-True ($null -ne $pilotItem) 'pilot.queue' 'booking visible in pilot queue' 'booking missing in pilot queue'

    $statusPayload = @{ status = 'cancelled' } | ConvertTo-Json
    $bookingCancelled = Invoke-RestMethod -WebSession $session -Method Patch -Uri "$ApiBase/bookings/$($bookingCreate.booking_id)/status" -ContentType 'application/json' -Body $statusPayload
    Assert-True ($bookingCancelled.status -eq 'cancelled') 'bookings.cancel' 'booking cancelled' "unexpected status=$($bookingCancelled.status)"
  } catch {
    Fail 'bookings' $_.Exception.Message
  }
}

try {
  $kpi = Invoke-RestMethod -WebSession $session -Uri "$ApiBase/kpi/summary?period=season&date_from=2026-06-01&date_to=2026-10-01"
  Assert-True ($null -ne $kpi.ride_breakdown) 'kpi.breakdown' 'ride breakdown present' 'ride breakdown missing'
} catch {
  Fail 'kpi' $_.Exception.Message
}

Write-Output ''
Write-Output "SUMMARY failures=$Script:Failures"
exit $(if ($Script:Failures -gt 0) { 1 } else { 0 })
