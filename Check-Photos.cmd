@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
    echo Kullanim: Check-Photos.cmd "C:\scan-data\ilk-nesne"
    echo Klasorde images adli alt klasor olmali. Klasoru bu dosyanin uzerine surukleyebilirsiniz.
    pause
    exit /b 2
)
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py -3 tools\monoscan.py validate "%~1"
) else (
    python tools\monoscan.py validate "%~1"
)
set "EXITCODE=%ERRORLEVEL%"
pause
exit /b %EXITCODE%
