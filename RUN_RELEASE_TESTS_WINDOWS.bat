@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Metaphor Agreement Studio - Release Verification

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo Please run START_METAPHOR_STUDIO_WINDOWS.bat once before running the tests.
  pause
  exit /b 1
)

set "MAS_WORKSPACE=%CD%"
set "PYTHONPATH=%CD%\src"
set "PYTHONUTF8=1"
set "MAS_EDUARDO_WORKBOOK=%CD%\imports\Teste de Concordancia - Revisor Eduardo.xlsx"

echo.
echo Installing release verification tools...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-dev-release.txt
if errorlevel 1 goto failed

echo.
echo Running the complete Release 1.0 automated test suite...
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 goto failed

echo.
echo Running code-quality checks...
".venv\Scripts\python.exe" -m ruff check app.py src tests
if errorlevel 1 goto failed

echo.
echo ============================================================
echo   Release verification passed.
echo ============================================================
echo.
pause
exit /b 0

:failed
echo.
echo ============================================================
echo   A release verification check failed.
echo ============================================================
echo.
echo Take a screenshot of this window and share it with the project maintainer.
echo.
pause
exit /b 1
