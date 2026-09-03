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

if exist "%CERT_FILE%" if exist "%KEY_FILE%" (
    uvicorn app.main:app --host 0.0.0.0 --port 8443 --ssl-certfile "%CERT_FILE%" --ssl-keyfile "%KEY_FILE%"
) else (
    uvicorn app.main:app --host 0.0.0.0 --port 8000
)
