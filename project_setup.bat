@echo off
setlocal enabledelayedexpansion
echo ==============================================
echo   LivePortrait Setup (Run Inside Repo)
echo ==============================================
echo.

REM ---- SAFETY CHECK ----
if not exist "gui.py" (
    echo [ERROR] You are not inside the LivePortrait repository!
    echo Please move this script inside the folder containing 'gui.py' and try again.
    pause
    exit /b
)


REM ---- 2. SKIPPING CLONE (Already inside) ----
echo.
echo [2/8] Repository check...
echo     Running inside repository. [OK]

REM ---- 3. DOWNLOAD WEIGHTS (FIXED STRUCTURE) ----
echo.
echo [3/8] Checking Weights...

if exist "pretrained_weights\insightface" (
    echo     [Skipping] Weights already present.
) else (
    echo     Installing gdown...
    pip install gdown >nul 2>&1

    echo     Downloading pretrained weights...
    if exist "weights_temp" rmdir /S /Q "weights_temp"
    
    REM Download into a temp folder first
    gdown --folder https://drive.google.com/drive/folders/1UtKgzKjFAOmZkhNK-OYT0caJ_w2XAnib -O weights_temp

    echo     Organizing directory structure...
    if not exist "pretrained_weights" mkdir pretrained_weights

    REM Copy CONTENTS of temp into pretrained_weights
    xcopy "weights_temp\*" "pretrained_weights\" /E /I /Y >nul

    echo     Cleaning up temp files...
    rmdir /S /Q weights_temp
    echo     Weights successfully organized.
)

REM ---- 4. CHECK/INSTALL CONDA ----
echo.
echo [4/8] Checking Conda...
where conda >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    if exist "%UserProfile%\Miniconda3\Scripts\activate.bat" (
        echo     Conda found in default path. Activating...
        call "%UserProfile%\Miniconda3\Scripts\activate.bat"
    ) else (
        echo     Installing Miniconda...
        powershell -Command "Invoke-WebRequest https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe -OutFile miniconda_installer.exe"
        start /wait "" miniconda_installer.exe /InstallationType=JustMe /RegisterPython=0 /S /D=%UserProfile%\Miniconda3
        del miniconda_installer.exe
        call "%UserProfile%\Miniconda3\Scripts\activate.bat"
    )
) ELSE (
    echo     Conda is installed.
)

REM ---- 5. CREATE ENVIRONMENT ----
echo.
echo [5/8] Checking Environment...
conda env list | find "final_setup" >nul
if %errorlevel% equ 0 (
    echo     [Skipping] Environment 'final_setup' already exists.
    call conda activate final_setup
) else (
    echo     Creating environment: final_setup...
    call conda create -y -n final_setup python=3.10
    call conda activate final_setup
)

REM ---- 6-8. INSTALL DEPENDENCIES ----
echo.
echo [6-8/8] Checking Dependencies...

if exist "install_complete.flag" (
    echo     [Skipping] Dependencies already installed.
) else (
    echo     1. Installing PyTorch (CUDA 12.1)...
    pip install torch==2.2.2 torchvision==0.17.2 torchaudio==2.2.2 --index-url https://download.pytorch.org/whl/cu121
    
    echo     2. Installing ffmpeg...
    call conda install -y -c conda-forge ffmpeg
    
    echo     3. Installing pip requirements...
    pip install -r requirements.txt
    
    REM Create a flag file so we don't run this next time
    echo done > install_complete.flag
    echo     Dependencies installed.
)

REM ---- 9. LAUNCH ----
echo.
echo ==============================================
echo 🎉 SETUP COMPLETE! Starting Application...
echo ==============================================
streamlit run gui.py
pause
