@echo off
setlocal
cd /d "%~dp0.."
set "PYTHONPATH=%CD%\icebeach-wakeclub"

echo Starting demo API on http://127.0.0.1:8000
start "IceBeach API" cmd /k "cd /d "%CD%" && set PYTHONPATH=%PYTHONPATH% && python scripts\demo_local.py"

echo Waiting for API...
timeout /t 4 /nobreak >nul

cd /d "%CD%\icebeach-wakeclub\apps\dashboard"
if not exist node_modules (
  echo Installing dashboard packages...
  call npm ci
)

echo Starting dashboard on http://127.0.0.1:5173
start "IceBeach UI" cmd /k "npm run dev -- --host 127.0.0.1 --port 5173"

echo.
echo Open http://127.0.0.1:5173
echo Do not open agent.cvm.dev or cursorvm.com
echo Login: Operator button, then request code
echo Stop: close the two new windows
endlocal
