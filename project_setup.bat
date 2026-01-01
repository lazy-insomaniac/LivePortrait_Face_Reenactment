@echo off
setlocal EnableDelayedExpansion

echo ==============================================
echo   LivePortrait Setup (Fixed - DLL Safe)
echo ==============================================
echo.

REM ---- SAFETY CHECK ----
if not exist "gui.py" (
    echo [ERROR] gui.py not found!
    echo Run this script INSIDE the LivePortrait repo.
    pause
    exit /b
)

REM ---- CONDA CHECK ----
echo [1/8] Checking Conda...
where conda >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Installing Miniconda...
    powershell -Command "Invoke-WebRequest https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe -OutFile miniconda.exe"
    start /wait "" miniconda.exe /S /D=%UserProfile%\Miniconda3
    del miniconda.exe
    call "%UserProfile%\Miniconda3\Scripts\activate.bat"
) else (
    if "%CONDA_DEFAULT_ENV%"=="" (
        if exist "%UserProfile%\Miniconda3\Scripts\activate.bat" (
            call "%UserProfile%\Miniconda3\Scripts\activate.bat"
        )
    )
)

REM ---- CHECK / CREATE ENV ----
echo [2/8] Checking environment: test_drive...
call conda env list | findstr /R /C:"^test_drive " >nul
if %ERRORLEVEL% NEQ 0 (
    echo Environment not found. Creating new one...
    call conda create -y -n test_drive python=3.10
) else (
    echo Environment exists. Reusing it.
)

call conda activate test_drive
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to activate environment.
    pause
    exit /b
)

REM ---- FFmpeg & DLL FIX ----
echo [3/8] Installing FFmpeg with STRICT dependencies...
call conda install -y -c conda-forge ffmpeg glib libiconv vc zlib poppler

ffmpeg -version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] FFmpeg failed to install correctly.
    pause
    exit /b
)

REM ---- TORCH ----
echo [4/8] Installing PyTorch CUDA 12.1...
call pip install --no-cache-dir torch==2.2.2 torchvision==0.17.2 torchaudio==2.2.2 --index-url https://download.pytorch.org/whl/cu121
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyTorch install failed.
    pause
    exit /b
)

REM ---- REQUIREMENTS ----
echo [5/8] Installing Python dependencies...
call pip install --no-cache-dir -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] requirements.txt failed.
    pause
    exit /b
)

REM ---- WEIGHTS ----
echo [6/8] Checking pretrained weights...
if not exist "pretrained_weights\insightface" (
    call pip install gdown
    gdown --folder https://drive.google.com/drive/folders/1UtKgzKjFAOmZkhNK-OYT0caJ_w2XAnib -O weights_temp
    mkdir pretrained_weights
    xcopy weights_temp pretrained_weights /E /I /Y
    rmdir /S /Q weights_temp
)

REM ---- REQUIRED RUNTIME DIRS ----
echo [7/8] Creating runtime directories...
if not exist "temp_uploads" mkdir temp_uploads
if not exist "outputs" mkdir outputs


echo.
echo ==============================================
echo  🎉 SETUP COMPLETE — Launching Streamlit
echo ==============================================
call streamlit run gui.py
pause
