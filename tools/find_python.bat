@echo off
rem Find a Python that can run this project.
rem Sets PYEXE (program) and PYARGS (extra arguments) for the caller.
rem If PYNEEDS_INSTALL=1 the caller must create .venv and install requirements.
set "PYEXE="
set "PYARGS="
set "PYNEEDS_INSTALL="
for %%I in ("%~dp0..") do set "SCHOLARIS_ROOT=%%~fI"

rem 1. The bundled runtime: works with no Python installed and no internet.
if exist "%SCHOLARIS_ROOT%\portable\python\python.exe" (
  set "PYEXE=%SCHOLARIS_ROOT%\portable\python\python.exe"
  goto :found
)

rem 2. The virtual environment already in the folder, if it still works here.
if exist "%SCHOLARIS_ROOT%\.venv\Scripts\python.exe" (
  "%SCHOLARIS_ROOT%\.venv\Scripts\python.exe" -c "import flask, flask_login, flask_wtf, flask_sqlalchemy" >nul 2>&1
  if not errorlevel 1 (
    set "PYEXE=%SCHOLARIS_ROOT%\.venv\Scripts\python.exe"
    goto :found
  )
)

rem 3. A system Python that already has Flask installed.
py -3 -c "import flask, flask_login, flask_wtf, flask_sqlalchemy" >nul 2>&1
if not errorlevel 1 (
  set "PYEXE=py"
  set "PYARGS=-3"
  goto :found
)
python -c "import flask, flask_login, flask_wtf, flask_sqlalchemy" >nul 2>&1
if not errorlevel 1 (
  set "PYEXE=python"
  goto :found
)

rem 4. A system Python without the packages; the caller builds a venv once.
py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 (
  set "PYEXE=py"
  set "PYARGS=-3"
  set "PYNEEDS_INSTALL=1"
  goto :found
)
python -c "import sys" >nul 2>&1
if not errorlevel 1 (
  set "PYEXE=python"
  set "PYNEEDS_INSTALL=1"
  goto :found
)

exit /b 1

:found
exit /b 0
