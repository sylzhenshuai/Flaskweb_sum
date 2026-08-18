@echo off
setlocal
REM ============================================================
REM  alt_web01 - dependency setup for conda env "sum_course"
REM  Env  : C:\Users\29587\.conda\envs\sum_course  (Python 3.13)
REM  Missing: flask (required), waitress (recommended on Windows)
REM ============================================================

set PY=C:\Users\29587\.conda\envs\sum_course\python.exe

REM Change to the folder where this script lives (project root)
cd /d "%~dp0"

echo [1/3] Upgrading pip...
"%PY%" -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo [2/3] Installing project in editable mode (pulls in flask^>=3.0)...
"%PY%" -m pip install -e .
if errorlevel 1 goto :fail

echo [3/3] Installing waitress (Windows-friendly production WSGI server)...
"%PY%" -m pip install "waitress>=3.0"
if errorlevel 1 goto :fail

echo.
echo ================= VERIFY =================
"%PY%" -c "import sys, importlib.metadata as m; print('Python', sys.version.split()[0], '| Flask', m.version('flask'))"
echo ==========================================

echo.
echo Dev server : flask --app wsgi run --debug
echo Prod server: waitress-serve --listen 0.0.0.0:8000 wsgi:app
echo.
pause
exit /b 0

:fail
echo.
echo [ERROR] Setup failed. Check the messages above.
pause
exit /b 1
