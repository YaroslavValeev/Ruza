# Сборка debug APK для sideload (без Google Play).
# Требуется: Node.js, JDK 17+, Android SDK (Android Studio).
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$dashboard = Join-Path $repoRoot "icebeach-wakeclub\apps\dashboard"
Set-Location $dashboard

function Get-LanIPv4 {
    Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object {
            $_.IPAddress -notlike "127.*" -and
            $_.IPAddress -notlike "169.254.*"
        } |
        Select-Object -ExpandProperty IPAddress -First 1
}

$ip = Get-LanIPv4
if (-not $ip) {
    Write-Host "LAN IP не найден. Задайте вручную: `$env:MOBILE_LAN_HOST='192.168.1.10'" -ForegroundColor Yellow
    $ip = "127.0.0.1"
}

$env:VITE_API_BASE_URL = "http://${ip}:8000"
$env:CAPACITOR_SERVER_URL = "http://${ip}:5173"
Write-Host "VITE_API_BASE_URL=$($env:VITE_API_BASE_URL)"
Write-Host "CAPACITOR_SERVER_URL=$($env:CAPACITOR_SERVER_URL)"

if (-not (Test-Path "node_modules")) {
    npm install
}

npm install @capacitor/core @capacitor/cli @capacitor/android

npm run build

if (-not (Test-Path "android")) {
    npx cap add android
}

npx cap sync android

Push-Location android
try {
    if ($IsWindows -or $env:OS -match "Windows") {
        .\gradlew.bat assembleDebug
    } else {
        ./gradlew assembleDebug
    }
} finally {
    Pop-Location
}

$apk = Join-Path $dashboard "android\app\build\outputs\apk\debug\app-debug.apk"
if (Test-Path $apk) {
    Write-Host ""
    Write-Host "APK готов:" -ForegroundColor Green
    Write-Host $apk
} else {
    Write-Host "APK не найден. Проверьте Android SDK и лог Gradle." -ForegroundColor Red
    exit 1
}
