@echo off
setlocal EnableExtensions
title Scholaris - Student Records Office
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"

call "%~dp0tools\find_python.bat"
if errorlevel 1 goto no_python

if defined PYNEEDS_INSTALL call :install_packages
if errorlevel 1 goto broken_install

echo.
echo  Starting Scholaris...
"%PYEXE%" %PYARGS% "%~dp0launch.py" %*
if errorlevel 1 (
  echo.
  echo  The server stopped with an error. Read the message above.
  pause
)
exit /b 0

:install_packages
echo.
echo  First run on this computer: installing the Python packages.
echo  This needs internet once and takes about a minute.
echo.
"%PYEXE%" %PYARGS% -m venv "%CD%\.venv"
if errorlevel 1 exit /b 1
"%CD%\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check --quiet --upgrade pip
"%CD%\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check --quiet -r "%CD%\requirements.txt"
if errorlevel 1 exit /b 1
set "PYEXE=%CD%\.venv\Scripts\python.exe"
set "PYARGS="
set "PYNEEDS_INSTALL="
exit /b 0

:broken_install
echo.
echo  Setup could not finish.
echo  Check the internet connection and try again, or use the copy of this
echo  folder that includes the "portable" directory (no install needed).
echo.
pause
exit /b 1

:no_python
echo.
echo  Python 3 was not found on this computer.
echo.
echo  Two ways to fix it:
echo    1. Use the copy of this folder that contains the "portable" folder.
echo       It carries its own Python, so nothing needs to be installed.
echo    2. Install Python 3.11 from https://www.python.org/downloads/
echo       and tick "Add python.exe to PATH" in the installer.
echo.
pause
exit /b 1
