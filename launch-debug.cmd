@echo off
call "%~dp0Play-Optimized.cmd" <nul > "%~dp0launch-output.txt" 2>&1
echo [wrapper] launcher exited with errorlevel %errorlevel% >> "%~dp0launch-output.txt"
