@echo off
title Industrial Solar Power Prediction System
echo ========================================================
echo Industrial Solar Power Prediction and Feasibility System
echo ========================================================
echo.

:: Navigate to project directory
if exist "%~dp0backend\app.py" (
    cd /d "%~dp0"
) else if exist "%~dp0industrial-solar-system\backend\app.py" (
    cd /d "%~dp0industrial-solar-system"
)

:: Verify Python installation
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found in system PATH.
    echo Please install Python 3.10 or higher.
    pause
    exit /b 1
)

echo [1/3] Verifying Python environment...
python -c "import flask, flask_cors, sklearn, pandas, numpy, joblib" >nul 2>nul
if %errorlevel% neq 0 (
    echo [Notice] Missing dependencies detected. Installing from requirements.txt...
    pip install -r backend\requirements.txt
)

echo [2/3] Opening browser at http://localhost:5000 in 4 seconds...
start "" cmd /c "timeout /t 4 /nobreak >nul & start http://localhost:5000"

echo [3/3] Starting Flask Application Server on http://localhost:5000 ...
echo ========================================================
echo The server is active. Keep this terminal window open.
echo If you click in this window and it pauses, press Enter.
echo Press Ctrl+C to stop the application.
echo ========================================================
echo.

python backend\app.py

pause
