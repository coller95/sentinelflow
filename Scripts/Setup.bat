@echo off
REM Resolve script location and set project root
SET SCRIPTDIR=%~dp0
FOR %%I IN ("%SCRIPTDIR%..") DO SET PROJECT_ROOT=%%~fI
cd /d "%PROJECT_ROOT%"

python -m venv .venv
IF EXIST ".venv\Scripts\activate.bat" (
  call .venv\Scripts\activate.bat
  python -m pip install -U pip
  pip install -r requirements.txt
)
