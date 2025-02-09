@echo off
echo 🔧 Setting up and starting ArcadeScore...

:: Step 1: Check if Python is installed
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Python3 is not installed. Please install Python3 and try again.
    exit /b
)

:: Step 2: Create a virtual environment if it doesn't exist
if not exist venv (
    echo 🔄 Creating virtual environment...
    python -m venv venv
)

:: Step 3: Activate the virtual environment
call venv\Scripts\activate.bat

:: Step 4: Install dependencies
echo 📦 Installing Python dependencies...
pip install --upgrade pip
pip install -r requirements.txt

:: Step 5: Check for 7-Zip and install if missing
set "SEVENZIP_PATH=C:\Program Files\7-Zip\7z.exe"
if not exist "%SEVENZIP_PATH%" (
    echo 🔄 7-Zip not found. Installing...
    curl -o 7zip_installer.exe https://www.7-zip.org/a/7z2301-x64.exe
    start /wait 7zip_installer.exe /S
    del 7zip_installer.exe
)

:: Step 6: Start the ArcadeScore server
echo 🚀 Starting ArcadeScore...
python run.py
