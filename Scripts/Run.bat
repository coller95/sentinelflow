@echo off
REM Resolve script location and set project root
SET SCRIPTDIR=%~dp0
FOR %%I IN ("%SCRIPTDIR%..") DO SET PROJECT_ROOT=%%~fI
cd /d "%PROJECT_ROOT%"

REM Activate virtual environment (Windows)
IF EXIST ".venv\Scripts\activate.bat" (
  call .venv\Scripts\activate.bat
)

python -m Src.cluster.main %*
