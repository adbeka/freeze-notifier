@echo off
REM Starts the freeze-window schedule server locally for testing/demo.
REM Needs Python 3.9+ on this machine (python.org install is enough,
REM "Install for all users" is not required).

cd /d "%~dp0"

if not exist venv\Scripts\python.exe (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Failed to create venv - is Python installed and on PATH?
        pause
        exit /b 1
    )
)

call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo pip install failed - see errors above.
    pause
    exit /b 1
)

if not exist local.env.bat (
    echo Generating local.env.bat with a random API key...
    powershell -NoProfile -Command "$k = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N'); Set-Content -Path local.env.bat -Value ('REM Local secrets - gitignored, never commit this file.' + [Environment]::NewLine + 'set FREEZE_API_KEY=' + $k)"
    if errorlevel 1 (
        echo Failed to generate local.env.bat - copy local.env.bat.example to local.env.bat and set a key manually.
        pause
        exit /b 1
    )
)
call local.env.bat
set FREEZE_DB_PATH=%~dp0freeze.db

echo.
echo ================================================================
echo Server starting at http://127.0.0.1:8000
echo.
echo   Admin (IT, create freeze windows):   http://127.0.0.1:8000/admin/
echo     X-API-Key: %FREEZE_API_KEY%
echo.
echo   Status page (engineer view):         http://127.0.0.1:8000/status/?segment=dept-ro
echo ================================================================
echo.
echo Stop the server: Ctrl+C in this window.
echo.

uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
