@echo off
REM Blood Donation System - Windows Startup Script

echo Starting Blood Donation System...
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Error: Failed to create virtual environment. Make sure Python is installed.
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo Error: Failed to install dependencies.
    pause
    exit /b 1
)

REM Check if database exists, if not initialize it
if not exist "blood_donation.db" (
    echo Initializing database...
    python migrate.py
    if errorlevel 1 (
        echo Error: Database initialization failed.
        pause
        exit /b 1
    )
    
    echo Seeding initial data...
    python seed_data.py
)

REM Create upload directories if they don't exist
if not exist "static\uploads\id_documents" mkdir static\uploads\id_documents
if not exist "static\uploads\address_proofs" mkdir static\uploads\address_proofs

echo.
echo =================================================
echo Blood Donation System is starting...
echo.
echo Application will be available at:
echo http://localhost:5000
echo.
echo Admin panel: http://localhost:5000/admin/login
echo.
echo To create an admin account, press Ctrl+C to stop
echo and run: python create_admin.py
echo =================================================
echo.

REM Start the application
python app.py
