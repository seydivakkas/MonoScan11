@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py -3 -m unittest discover -s tests -v
) else (
    python -m unittest discover -s tests -v
)
set "EXITCODE=%ERRORLEVEL%"
if "%EXITCODE%"=="0" (echo [PASS] Python testleri tamamlandi.) else (echo [FAIL] Python testleri basarisiz.)
pause
exit /b %EXITCODE%
