@echo off
rem Build and open the run inspector for the newest run (runs\LATEST), served on 127.0.0.1.
rem Usage: Inspect.cmd [scene] [--run DIR] [--no-open] [--port N]      Ctrl+C stops the server.
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONUTF8=1"
call :find_python
if not defined PY (
    echo Python 3.11 or newer was not found. Run Setup.cmd first.
    pause
    exit /b 1
)
%PY% -m tools.inspector --run LATEST %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo.
    echo Inspect failed ^(exit code %RC%^): see the messages above.
    pause
)
exit /b %RC%

:find_python
rem The project's .venv first, then "py -3", then "python" (3.11 or newer).
set "PY="
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
    goto :eof
)
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PY=py -3"
    goto :eof
)
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=python"
goto :eof
