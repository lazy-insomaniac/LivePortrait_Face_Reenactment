@echo off
setlocal

echo ================================
echo   Launching LivePortrait GUI
echo ================================
echo.

REM ---- CHECK CONDA ----
where conda >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    if exist "%UserProfile%\Miniconda3\Scripts\activate.bat" (
        echo Activating Miniconda...
        call "%UserProfile%\Miniconda3\Scripts\activate.bat"
    ) else (
        echo [ERROR] Conda not found! Install Miniconda first.
        pause
        exit /b
    )
) ELSE (
    echo Conda detected.
)

REM ---- ACTIVATE ENVIRONMENT ----
echo.
echo Activating environment: test_drive...
call conda activate test_drive

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to activate environment 'test_drive'.
    echo Make sure it exists: conda env list
    pause
    exit /b
)

REM ---- RUN GUI ----
echo.
echo 🚀 Starting LivePortrait...
call streamlit run gui.py

echo.
echo (Close this window to stop LivePortrait)
pause
