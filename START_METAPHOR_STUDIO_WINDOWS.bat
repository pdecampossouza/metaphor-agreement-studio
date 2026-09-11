@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Metaphor Agreement Studio - Release 1.0

set "MAS_WORKSPACE=%CD%"
set "PYTHONPATH=%CD%\src"
set "PYTHONUTF8=1"
set "STREAMLIT_BROWSER_GATHER_USAGE_STATS=false"

if exist ".venv\Scripts\python.exe" goto ensure_release

echo.
echo ============================================================
echo   Metaphor Agreement Studio - First-time setup
echo ============================================================
echo.
echo A private Python environment will be created in this folder.
echo This is required only the first time.
echo The original research workbook will not be modified.
echo.

py -3.12 -c "import sys; assert (3,11) <= sys.version_info[:2] < (3,14)" >nul 2>&1 && set "PY_CMD=py -3.12" && goto python_found
py -3.11 -c "import sys; assert (3,11) <= sys.version_info[:2] < (3,14)" >nul 2>&1 && set "PY_CMD=py -3.11" && goto python_found
py -3.13 -c "import sys; assert (3,11) <= sys.version_info[:2] < (3,14)" >nul 2>&1 && set "PY_CMD=py -3.13" && goto python_found
python -c "import sys; assert (3,11) <= sys.version_info[:2] < (3,14)" >nul 2>&1 && set "PY_CMD=python" && goto python_found

goto no_python

:python_found
echo Python found. Creating the local environment...
%PY_CMD% -m venv .venv
if errorlevel 1 goto setup_failed

echo.
echo Installing Metaphor Agreement Studio Release 1.0...
echo This first installation can take a few minutes.
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --upgrade pip
if errorlevel 1 goto setup_failed
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-release.txt
if errorlevel 1 goto setup_failed

goto launch

:ensure_release
".venv\Scripts\python.exe" -c "import streamlit, openpyxl, pandas, numpy, scipy, statsmodels, sklearn, plotly, matplotlib, jinja2, reportlab" >nul 2>&1
if not errorlevel 1 goto launch

echo.
echo Updating the local environment for Release 1.0...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-release.txt
if errorlevel 1 goto setup_failed

goto launch

:launch
if not exist ".venv\Scripts\python.exe" goto setup_failed
for /f %%P in ('powershell -NoProfile -Command "$p=8501; while (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) { $p++ }; Write-Output $p"') do set "MAS_PORT=%%P"
if not defined MAS_PORT set "MAS_PORT=8501"
> ".mas_streamlit.port" echo %MAS_PORT%

echo ============================================================
echo   Metaphor Agreement Studio - Release 1.0
echo ============================================================
echo.
echo The application will open in your web browser.
echo Keep this window open while you use the application.
echo To stop it, double-click STOP_METAPHOR_STUDIO_WINDOWS.bat.
echo.
echo Local address: http://127.0.0.1:%MAS_PORT%
echo.

".venv\Scripts\python.exe" -m streamlit run app.py --server.port %MAS_PORT% --server.address 127.0.0.1 --server.headless false --browser.gatherUsageStats false
set "EXIT_CODE=%ERRORLEVEL%"
if exist ".mas_streamlit.port" del /q ".mas_streamlit.port" >nul 2>&1
if "%EXIT_CODE%"=="0" goto end

echo.
echo The application stopped with an error.
echo Please take a screenshot of this window and share it with the project maintainer.
pause
goto end

:no_python
echo.
echo ============================================================
echo   Python 3.11, 3.12, or 3.13 was not found.
echo ============================================================
echo.
echo Install Python 3.12 from python.org, then run this file again.
echo During installation, enable the option "Add python.exe to PATH".
echo.
pause
goto end

:setup_failed
echo.
echo ============================================================
echo   Setup could not be completed.
echo ============================================================
echo.
echo Check your internet connection and try again.
echo If the problem continues, take a screenshot of this window.
echo.
pause

:end
endlocal
