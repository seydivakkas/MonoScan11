@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
echo MonoScan11 - Publish current source to GitHub (no force push)
where git >nul 2>nul
if errorlevel 1 (
  echo ERROR: Git for Windows is required: https://git-scm.com/downloads/win
  pause
  exit /b 1
)
if not exist ".git" (
  git init -b main
  if errorlevel 1 goto fail
)
set "EXISTING_REMOTE="
for /f "delims=" %%R in ('git remote get-url origin 2^>nul') do set "EXISTING_REMOTE=%%R"
if defined EXISTING_REMOTE (
  if /I not "!EXISTING_REMOTE!"=="https://github.com/seydivakkas/MonoScan11.git" (
    echo ERROR: Existing origin is different: !EXISTING_REMOTE!
    echo Aborting without changing the remote.
    pause
    exit /b 1
  )
) else (
  git remote add origin https://github.com/seydivakkas/MonoScan11.git
  if errorlevel 1 goto fail
)
git add .
if errorlevel 1 goto fail
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "feat: SwiftUI screens ARKit capture and Windows ZIP contract"
  if errorlevel 1 goto fail
) else (
  echo No local changes to commit.
)
echo.
echo Pushing current branch to origin/main (without --force)...
git push -u origin HEAD:main
if errorlevel 1 goto fail
echo.
echo GitHub publish command completed. Check Actions for CI results.
pause
exit /b 0
:fail
echo.
echo FAILED. Existing local files were not deleted.
echo Review the Git error and run again only after fixing the cause.
pause
exit /b 1
