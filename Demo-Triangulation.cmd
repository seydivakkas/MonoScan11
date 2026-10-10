@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py -3 tools\monoscan.py demo demo-output
) else (
    python tools\monoscan.py demo demo-output
)
set "EXITCODE=%ERRORLEVEL%"
if "%EXITCODE%"=="0" echo Sentetik PLY: demo-output\synthetic_points.ply
if not "%EXITCODE%"=="0" echo Daha once uretildiyse demo-output klasorunu yeniden adlandirin.
pause
exit /b %EXITCODE%
