@echo off
rem Lighting comparison harness: one-time setup on Windows.
rem Finds Python 3.11+ ("py -3", then "python"), creates .venv next to this file, installs requirements.txt and
rem the Chromium build Playwright drives for the threejs-web runner. Safe to run again (reuses .venv).
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONUTF8=1"

set "PY="
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY=python"
)
if not defined PY (
    echo.
    echo Python 3.11 or newer was not found ^(tried "py -3" and "python"^).
    echo Install it from https://www.python.org/downloads/windows/ with "Add python.exe to PATH" ticked,
    echo then run Setup.cmd again.
    goto :fail
)
echo Using Python:
%PY% -c "import sys; print('  ' + sys.executable + '  ' + sys.version.split()[0])"
if errorlevel 1 goto :fail

if exist ".venv\Scripts\python.exe" (
    echo Reusing the existing .venv
) else (
    echo Creating .venv ...
    %PY% -m venv .venv
    if errorlevel 1 goto :fail
)
set "VPY=.venv\Scripts\python.exe"

echo.
echo Installing the Python packages in requirements.txt ...
"%VPY%" -m pip install --upgrade pip
if errorlevel 1 goto :fail
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo Installing Chromium for the threejs-web runner ...
"%VPY%" -m playwright install chromium
if errorlevel 1 goto :fail

echo.
echo Setup complete.
echo.
echo Next steps:
echo   Run-Harness.cmd                   run every step: references, engines, metrics, gates, temporal, report
echo                                     (the first run renders the Mitsuba references, about half an hour)
echo   Run-Harness.cmd --phase0 --perf   also the Phase 0 parity and the performance measurements
echo   Run-Harness.cmd --help            all options (--scenes, --engines, --spp-scale, ...)
echo   Inspect.cmd [scene]               open the viewer for the newest run (named in runs\LATEST)
echo Each run is a folder under runs\ with its report.md.
echo.
pause
exit /b 0

:fail
echo.
echo Setup failed: see the messages above.
pause
exit /b 1
