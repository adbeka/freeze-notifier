@echo off
REM Non-interactive launcher for Task Scheduler - no pause, no pip install.
REM Run run.bat manually once first to create venv/ and local.env.bat.
REM See README.md "Многопользовательский запуск" for how to register this
REM as a scheduled task with restart-on-failure.

cd /d "%~dp0"

if not exist venv\Scripts\python.exe (
    echo venv missing - run run.bat manually once to set it up.
    exit /b 1
)
call venv\Scripts\activate.bat

if not exist local.env.bat (
    echo local.env.bat missing - run run.bat manually once to generate it.
    exit /b 1
)
call local.env.bat
set FREEZE_DB_PATH=%~dp0freeze.db

set CERT_FILE=%~dp0certs\cert.pem
set KEY_FILE=%~dp0certs\key.pem

REM Task Scheduler runs this with no console attached, so uvicorn's output
REM would otherwise vanish - log to one file per day (new file each day
REM keeps any single file from growing forever; old ones just pile up in
REM logs\, delete/archive them by hand on whatever schedule you want).
set LOG_DIR=%~dp0logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set LOG_DATE=%%d
set LOG_FILE=%LOG_DIR%\%LOG_DATE%.log

if exist "%CERT_FILE%" if exist "%KEY_FILE%" (
    uvicorn app.main:app --host 0.0.0.0 --port 8443 --ssl-certfile "%CERT_FILE%" --ssl-keyfile "%KEY_FILE%" >> "%LOG_FILE%" 2>&1
) else (
    uvicorn app.main:app --host 0.0.0.0 --port 8000 >> "%LOG_FILE%" 2>&1
)
