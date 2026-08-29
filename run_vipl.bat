@echo off
setlocal EnableExtensions
title VIPL Application Launcher

cd /d "%~dp0"
if not exist "logs" mkdir "logs"

echo.
echo ============================================================
echo   VIPL Investigation and Death Claim Management System
echo ============================================================
echo.

set "PYTHON_EXE="
for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
if not defined PYTHON_EXE for /d %%D in ("%LocalAppData%\Programs\Python\Python*") do if exist "%%~fD\python.exe" set "PYTHON_EXE=%%~fD\python.exe"
if not defined PYTHON_EXE (
  echo [ERROR] Python is not installed or not available in PATH.
  if /I not "%~1"=="--no-browser" pause
  exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js is not installed or not available in PATH.
  if /I not "%~1"=="--no-browser" pause
  exit /b 1
)

rem The existing PostgreSQL service requires a password not available to this
rem workspace. The launcher therefore uses a local SQLite development database
rem by default. Set VIPL_DATABASE_URL before running to use PostgreSQL, e.g.:
rem set VIPL_DATABASE_URL=postgresql+asyncpg://postgres:PASSWORD@localhost:5432/investigation_db
if defined VIPL_DATABASE_URL (
  set "DATABASE_URL=%VIPL_DATABASE_URL%"
) else (
  set "DATABASE_URL=sqlite+aiosqlite:///./vipl_dev.db"
)
set "APP_ENV=development"
set "DEBUG=true"
set "SUPER_ADMIN_NAME=Super Administrator"
set "SUPER_ADMIN_EMAIL=admin@investigation.local"
set "SUPER_ADMIN_PASSWORD=Admin@123456"

echo [1/6] Checking backend dependencies...
pushd backend
"%PYTHON_EXE%" -c "import fastapi, sqlalchemy, aiosqlite, docx, openpyxl" >nul 2>nul
if errorlevel 1 (
  echo       Installing Python dependencies...
  "%PYTHON_EXE%" -m pip install -r requirements.txt -r requirements-dev.txt
  if errorlevel 1 goto :failed
)

echo [2/6] Applying database migration...
"%PYTHON_EXE%" -m alembic upgrade head
if errorlevel 1 goto :failed

echo [3/6] Creating roles, templates and Super Admin...
"%PYTHON_EXE%" scripts\seed.py
if errorlevel 1 goto :failed

echo [4/6] Preparing the client document templates...
rem Turns the insurer specimen forms into {{ tag }} templates so DOCX/PDF
rem generation works on a fresh install. Safe to re-run; originals untouched.
"%PYTHON_EXE%" -m scripts.tag_templates >nul 2>nul
if errorlevel 1 echo       Skipped - run "python -m scripts.tag_templates" from backend to see why.
popd

echo [5/6] Checking frontend dependencies...
if not exist "frontend\node_modules" (
  pushd frontend
  call npm.cmd install
  if errorlevel 1 goto :failed_frontend
  popd
)

echo [6/6] Starting backend and frontend...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health -TimeoutSec 2 ^| Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -WindowStyle Hidden -FilePath '%PYTHON_EXE%' -WorkingDirectory '%~dp0backend' -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -RedirectStandardOutput '%~dp0logs\backend.log' -RedirectStandardError '%~dp0logs\backend-error.log'"

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5173/ -TimeoutSec 2 ^| Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -WindowStyle Hidden -FilePath 'npm.cmd' -WorkingDirectory '%~dp0frontend' -ArgumentList @('run','dev','--','--host','127.0.0.1') -RedirectStandardOutput '%~dp0logs\frontend.log' -RedirectStandardError '%~dp0logs\frontend-error.log'"

echo       Waiting for services...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ok=$false; 1..30 | ForEach-Object { try { $r=Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health -TimeoutSec 2; if($r.StatusCode -eq 200){$ok=$true; break} } catch {}; Start-Sleep -Seconds 1 }; if(-not $ok){exit 1}"
if errorlevel 1 (
  echo [ERROR] Backend did not become healthy. Check logs\backend.log
  if /I not "%~1"=="--no-browser" pause
  exit /b 1
)

echo.
echo ============================================================
echo   VIPL is running successfully
echo   App:  http://localhost:5173
echo   API:  http://localhost:8000/docs
echo.
echo   Email:    admin@investigation.local
echo   Password: Admin@123456
echo ============================================================
echo.
if /I not "%~1"=="--no-browser" start "" http://localhost:5173
exit /b 0

:failed_frontend
popd
:failed
popd
echo.
echo [ERROR] VIPL startup failed. Review the message above.
if /I not "%~1"=="--no-browser" pause
exit /b 1
