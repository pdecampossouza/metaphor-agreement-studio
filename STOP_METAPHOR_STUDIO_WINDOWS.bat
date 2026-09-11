@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Stop Metaphor Agreement Studio

set "MAS_PORT=8501"
if exist ".mas_streamlit.port" set /p MAS_PORT=<".mas_streamlit.port"

echo.
echo Stopping Metaphor Agreement Studio on port %MAS_PORT%...
powershell -NoProfile -Command "$connections = Get-NetTCPConnection -LocalPort %MAS_PORT% -State Listen -ErrorAction SilentlyContinue; if ($connections) { $connections | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }; exit 0 } else { exit 2 }"
if errorlevel 2 goto not_running

if exist ".mas_streamlit.port" del /q ".mas_streamlit.port" >nul 2>&1
echo Studio stopped.
timeout /t 2 >nul
goto end

:not_running
if exist ".mas_streamlit.port" del /q ".mas_streamlit.port" >nul 2>&1
echo No running Studio process was found on port %MAS_PORT%.
timeout /t 2 >nul

:end
endlocal
