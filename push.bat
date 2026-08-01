@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM  Publish the policy site to https://github.com/AmMysterious/ciel_study
REM
REM  Run this from THIS folder only. It is deliberately scoped to study_bot_site
REM  so the parent project - which holds .env files with the Telegram bot token
REM  and the Razorpay secret - can never be pushed to a PUBLIC repo by accident.
REM ─────────────────────────────────────────────────────────────────────────────
cd /d "%~dp0"

echo Checking nothing secret is staged...
git add -A
git status --short

REM Refuse outright if anything that smells of a secret crept in.
git diff --cached --name-only | findstr /I ".env .db token secret" >nul
if %errorlevel%==0 (
  echo.
  echo *** ABORTED: a file matching .env/.db/token/secret is staged.
  echo *** This repo is PUBLIC. Remove it before pushing.
  pause
  exit /b 1
)

set MSG=%*
if "%MSG%"=="" set MSG=update policy pages

git commit -m "%MSG%"
git push -u origin main

echo.
echo Done. Live in ~1 minute at https://ammysterious.github.io/ciel_study/
pause
