@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

echo.
echo ========================================
echo MindForge setup and pipeline runner
echo ========================================
echo Project root: %CD%
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found on PATH.
    echo Install Python 3.12+ or enable "Add Python to PATH", then rerun this file.
    exit /b 1
)

if not exist "requirements.txt" (
    echo ERROR: requirements.txt was not found. Run this file from the MindForge project root.
    exit /b 1
)

if not exist ".env" (
    if exist ".env-example" (
        copy ".env-example" ".env" >nul
        echo ERROR: .env was missing, so I created one from .env-example.
        echo Fill in .env first, especially DEEPSEEK_TOKEN and KIMI_API_KEY, then rerun this file.
        exit /b 1
    )
    echo ERROR: .env was not found. Create .env with your DeepSeek and LLM credentials, then rerun this file.
    exit /b 1
)

if not exist "mindforge-env\Scripts\python.exe" (
    call :run "Setup: create virtual environment" python -m venv mindforge-env || exit /b !ERRORLEVEL!
) else (
    echo Setup: virtual environment already exists.
)

call "mindforge-env\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: Could not activate mindforge-env.
    exit /b 1
)

call :run "Setup: install Python dependencies" "python -m pip install -r requirements.txt" || exit /b !ERRORLEVEL!
call :run "Setup: install Playwright Chromium" "python -m playwright install chromium" || exit /b !ERRORLEVEL!

echo.
echo ========================================
echo Running MindForge stages
echo ========================================

call :run "Stage 01: DeepSeek export" "python 01_deepseek_export.py" || exit /b !ERRORLEVEL!
call :run "Stage 02: generate titles and summaries" "python 02_generate_title_summary.py" || exit /b !ERRORLEVEL!
call :run "Stage 03: add kind, purpose, and tags" "python 03_add_label.py" || exit /b !ERRORLEVEL!

echo.
echo ========================================
echo MindForge pipeline completed successfully.
echo Final markdowns: pipeline_outputs\03_final_markdowns
echo ========================================
exit /b 0

:run
set "STEP_NAME=%~1"
set "RUN_CMD=%~2"
echo.
echo === %STEP_NAME% ===
%RUN_CMD%
if errorlevel 1 (
    set "EXIT_CODE=%ERRORLEVEL%"
    echo.
    echo ========================================
    echo ERROR: %STEP_NAME% failed.
    echo Exit code: !EXIT_CODE!
    echo Command: %RUN_CMD%
    echo See the error output above for details.
    echo ========================================
    exit /b !EXIT_CODE!
)
exit /b 0
