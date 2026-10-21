@echo off
setlocal EnableExtensions
title Scholaris - Reset demo data
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

call "%~dp0tools\find_python.bat"
if errorlevel 1 (
  echo.
  echo  Python was not found. Use the folder that includes "portable".
  echo.
  pause
  exit /b 1
)

if defined PYNEEDS_INSTALL (
  echo.
  echo  Run START_SCHOLARIS.bat once first so the packages are installed.
  echo.
  pause
  exit /b 1
)

echo.
echo  Rebuilding the demo college. Any changes made in the demo will be lost.
echo  Close the running website window first, then press any key.
pause >nul

"%PYEXE%" %PYARGS% "%~dp0launch.py" --reset --check
echo.
pause
