@echo off
setlocal
cd /d "%~dp0"
title Metaphor Agreement Studio - Create Desktop Shortcut

powershell -NoProfile -ExecutionPolicy Bypass -Command "$desktop=[Environment]::GetFolderPath('Desktop'); $target=Join-Path '%CD%' 'START_METAPHOR_STUDIO_WINDOWS.bat'; $shortcut=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'Metaphor Agreement Studio.lnk')); $shortcut.TargetPath=$target; $shortcut.WorkingDirectory='%CD%'; $shortcut.Description='Open Metaphor Agreement Studio'; $shortcut.Save()"

if errorlevel 1 (
  echo.
  echo The desktop shortcut could not be created.
  echo You can still use START_METAPHOR_STUDIO_WINDOWS.bat directly.
  pause
  exit /b 1
)

echo.
echo A "Metaphor Agreement Studio" shortcut was created on the Desktop.
echo You can use that shortcut from now on.
pause
endlocal
