@echo off
setlocal enabledelayedexpansion

:: Mouse Jitter AFK Bypass - Installation Script
:: This script will copy the modified task files to your ok-dna installation

echo ========================================
echo Mouse Jitter AFK Bypass - Installer
echo ========================================
echo.

:: Check if running from the correct directory
if not exist "src\tasks\CommissionsTask.py" (
    echo ERROR: This script must be run from the mousejitter folder!
    echo Please make sure you're in the correct directory.
    echo.
    pause
    exit /b 1
)

:: Try to auto-detect ok-dna installation
set "OK_DNA_PATH="

:: Check common installation locations
if exist "%LOCALAPPDATA%\ok-dna\data\apps\ok-dna\working\src\tasks" (
    set "OK_DNA_PATH=%LOCALAPPDATA%\ok-dna\data\apps\ok-dna\working"
    echo Found ok-dna installation at: !OK_DNA_PATH!
    echo.
) else (
    echo Could not auto-detect ok-dna installation.
    echo.
)

:: Ask user to confirm or provide path
if defined OK_DNA_PATH (
    echo Is this the correct ok-dna installation path?
    echo !OK_DNA_PATH!
    echo.
    choice /C YN /M "Use this path"
    if errorlevel 2 set "OK_DNA_PATH="
)

:: If path not found or user declined, ask for manual input
if not defined OK_DNA_PATH (
    echo.
    echo Please enter the full path to your ok-dna installation folder
    echo Example: C:\Users\YourName\AppData\Local\ok-dna\data\apps\ok-dna\working
    echo.
    set /p "OK_DNA_PATH=Enter path: "
)

:: Validate the path
if not exist "!OK_DNA_PATH!\src\tasks" (
    echo.
    echo ERROR: Invalid path! Could not find src\tasks folder.
    echo Please make sure you entered the correct ok-dna installation path.
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Installing files...
echo ========================================
echo.

:: Create backup folder with timestamp
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c-%%a-%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
set "BACKUP_FOLDER=!OK_DNA_PATH!\backup_!mydate!_!mytime!"

echo Creating backup at: !BACKUP_FOLDER!
mkdir "!BACKUP_FOLDER!\tasks" 2>nul
mkdir "!BACKUP_FOLDER!\tasks\fullauto" 2>nul

:: Backup existing files
echo Backing up existing files...
if exist "!OK_DNA_PATH!\src\tasks\CommissionsTask.py" copy "!OK_DNA_PATH!\src\tasks\CommissionsTask.py" "!BACKUP_FOLDER!\tasks\" >nul
if exist "!OK_DNA_PATH!\src\tasks\AutoExploration.py" copy "!OK_DNA_PATH!\src\tasks\AutoExploration.py" "!BACKUP_FOLDER!\tasks\" >nul
if exist "!OK_DNA_PATH!\src\tasks\AutoDefence.py" copy "!OK_DNA_PATH!\src\tasks\AutoDefence.py" "!BACKUP_FOLDER!\tasks\" >nul
if exist "!OK_DNA_PATH!\src\tasks\AutoExpulsion.py" copy "!OK_DNA_PATH!\src\tasks\AutoExpulsion.py" "!BACKUP_FOLDER!\tasks\" >nul
if exist "!OK_DNA_PATH!\src\tasks\fullauto\AutoFishTask.py" copy "!OK_DNA_PATH!\src\tasks\fullauto\AutoFishTask.py" "!BACKUP_FOLDER!\tasks\fullauto\" >nul
if exist "!OK_DNA_PATH!\src\tasks\fullauto\AutoExploration_Fast.py" copy "!OK_DNA_PATH!\src\tasks\fullauto\AutoExploration_Fast.py" "!BACKUP_FOLDER!\tasks\fullauto\" >nul
if exist "!OK_DNA_PATH!\src\tasks\fullauto\ImportTask.py" copy "!OK_DNA_PATH!\src\tasks\fullauto\ImportTask.py" "!BACKUP_FOLDER!\tasks\fullauto\" >nul

:: Copy new files
echo.
echo Installing new files...
echo.

echo [1/7] CommissionsTask.py
copy /Y "src\tasks\CommissionsTask.py" "!OK_DNA_PATH!\src\tasks\" >nul
if errorlevel 1 (echo   FAILED!) else (echo   OK)

echo [2/7] AutoExploration.py
copy /Y "src\tasks\AutoExploration.py" "!OK_DNA_PATH!\src\tasks\" >nul
if errorlevel 1 (echo   FAILED!) else (echo   OK)

echo [3/7] AutoDefence.py
copy /Y "src\tasks\AutoDefence.py" "!OK_DNA_PATH!\src\tasks\" >nul
if errorlevel 1 (echo   FAILED!) else (echo   OK)

echo [4/7] AutoExpulsion.py
copy /Y "src\tasks\AutoExpulsion.py" "!OK_DNA_PATH!\src\tasks\" >nul
if errorlevel 1 (echo   FAILED!) else (echo   OK)

echo [5/7] AutoFishTask.py
copy /Y "src\tasks\fullauto\AutoFishTask.py" "!OK_DNA_PATH!\src\tasks\fullauto\" >nul
if errorlevel 1 (echo   FAILED!) else (echo   OK)

echo [6/7] AutoExploration_Fast.py
copy /Y "src\tasks\fullauto\AutoExploration_Fast.py" "!OK_DNA_PATH!\src\tasks\fullauto\" >nul
if errorlevel 1 (echo   FAILED!) else (echo   OK)

echo [7/7] ImportTask.py
copy /Y "src\tasks\fullauto\ImportTask.py" "!OK_DNA_PATH!\src\tasks\fullauto\" >nul
if errorlevel 1 (echo   FAILED!) else (echo   OK)

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo Backup created at: !BACKUP_FOLDER!
echo.
echo IMPORTANT: Please restart ok-dna for changes to take effect.
echo.
echo What's new:
echo - Mouse jitter AFK prevention (Jitter Mode setting)
echo - English translations for task names
echo - Fixed sound notifications
echo - Fixed Auto Exploration round continuation
echo.
pause
