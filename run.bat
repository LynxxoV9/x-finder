@echo off
REM ==============================================================================
REM X-Finder AI Agent - Lanceur Windows Batch
REM Commande : run.bat
REM ==============================================================================

title X-Finder AI Agent
echo ===============================================================
echo            X-FINDER AI AGENT - DEMARRAGE WINDOWS
echo ===============================================================

cd /d "%~dp0"

REM Verification de python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERREUR] Python n'est pas installe ou non present dans le PATH.
    echo Veuillez installer Python 3.10+ depuis https://www.python.org/
    pause
    exit /b 1
)

python run.py %*
pause
