@echo off
REM Resolve script location and set project root
SET SCRIPTDIR=%~dp0
FOR %%I IN ("%SCRIPTDIR%..") DO SET PROJECT_ROOT=%%~fI
cd /d "%PROJECT_ROOT%"

REM Activate virtual environment (Windows)
IF EXIST ".venv\Scripts\activate.bat" (
  call .venv\Scripts\activate.bat
)

REM Check if PyInstaller is installed in .venv
pip show pyinstaller >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Installing PyInstaller in .venv...
    pip install pyinstaller
)

REM Package the cluster entrypoint into a single executable using .venv Python
python -m PyInstaller --onefile --add-data "web\cluster;web\cluster" Src\cluster\main.py

echo Packaging complete. Check the dist folder in the repo root.
pause
