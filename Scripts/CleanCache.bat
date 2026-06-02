@echo off
REM Clean Python cache: __pycache__ folders and .pyc/.pyo files

REM Remove __pycache__ folder in Src
if exist "Src\__pycache__" (
    echo Removing Src\__pycache__
    rmdir /s /q "Src\__pycache__"
)

REM Remove localpycs folder in build\Main
if exist "build\Main\localpycs" (
    echo Removing build\Main\localpycs
    rmdir /s /q "build\Main\localpycs"
)

REM Remove .pyc and .pyo files recursively in Src
for /r "Src" %%F in (*.pyc *.pyo) do (
    echo Deleting %%F
    del /f /q "%%F"
)

echo Python cache cleaned.
pause
