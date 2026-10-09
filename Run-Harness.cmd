@echo off
rem Run the whole lighting harness (python -m tools.run_all): references, engines, metrics, gates, temporal, report.
rem Usage: Run-Harness.cmd [--scenes SELECTION] [--engines a,b] [--phase0] [--perf] [--spp-scale F] [--help]
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONUTF8=1"
call :find_python
if not defined PY (
    echo Python 3.11 or newer was not found. Run Setup.cmd first.
    pause
    exit /b 1
)
%PY% -m tools.run_all %*
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
    echo Harness finished: every step ok.
) else (
    echo Harness finished with failures ^(exit code %RC%^): see the output above and the run's report.md.
)
echo The newest run is named in runs\LATEST; Inspect.cmd opens its viewer.
pause
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
