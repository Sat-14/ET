@echo off
title ET Money Mentor - Setup & Launch
echo ============================================
echo    ET Money Mentor - One-Click Setup
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.10+ from python.org
    pause
    exit /b 1
)
echo [OK] Python found

:: Create venv if it doesn't exist
if not exist "venv\Scripts\python.exe" (
    echo.
    echo [1/3] Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment already exists
)

:: Install dependencies
echo.
echo [2/3] Installing dependencies (this may take 2-3 minutes on first run)...
venv\Scripts\pip install -q -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Some packages failed to install. Check the output above.
    pause
    exit /b 1
)
echo [OK] All dependencies installed

:: Check for .env
if not exist ".env" (
    echo.
    echo [WARNING] No .env file found. Creating one with placeholder...
    echo GEMINI_API_KEY=your_key_here> .env
    echo [INFO] Edit .env and add your API key before using AI chat.
    echo        Get a free Gemini key at: https://makersuite.google.com/app/apikey
)

:: Run tests
echo.
echo [3/3] Running tests...
venv\Scripts\python -m pytest tests/ -v --tb=short
if %errorlevel% neq 0 (
    echo [WARNING] Some tests failed. The app may still work.
) else (
    echo [OK] All tests passed
)

:: Launch
echo.
echo ============================================
echo    Starting ET Money Mentor
echo ============================================
echo.
echo    API Server:  http://localhost:8000
echo    Dashboard:   http://localhost:8501
echo    API Docs:    http://localhost:8000/docs
echo.
echo    Press Ctrl+C in either window to stop.
echo ============================================
echo.

:: Start FastAPI in background
start "ET Money Mentor - API" cmd /k "venv\Scripts\python -m uvicorn src.main:app --host 0.0.0.0 --port 8000"

:: Wait for API to start
timeout /t 3 /nobreak >nul

:: Start Streamlit in foreground
venv\Scripts\python -m streamlit run dashboard/app.py --server.port 8501
