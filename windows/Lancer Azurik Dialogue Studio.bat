@echo off
setlocal
cd /d "%~dp0.."

if exist "%~dp01.0.0\Azurik Dialogue Studio.exe" (
    start "" "%~dp01.0.0\Azurik Dialogue Studio.exe" %*
    exit /b 0
)
if exist "%~dp0Azurik Dialogue Studio.exe" (
    start "" "%~dp0Azurik Dialogue Studio.exe" %*
    exit /b 0
)
if exist "%~dp0..\dist\Azurik Dialogue Studio.exe" (
    start "" "%~dp0..\dist\Azurik Dialogue Studio.exe" %*
    exit /b 0
)

rem Source checkout fallback. No automatic installation or network access.
if exist "%~dp0..\.venv-desktop\Scripts\pythonw.exe" (
    start "" "%~dp0..\.venv-desktop\Scripts\pythonw.exe" "%~dp0..\desktop.py" %*
    exit /b 0
)
if exist "%~dp0..\desktop.py" (
    where pyw.exe >nul 2>nul
    if not errorlevel 1 (
        start "" pyw.exe -3 "%~dp0..\desktop.py" %*
        exit /b 0
    )
)

echo Azurik Dialogue Studio.exe est introuvable.
echo Placez ce lanceur avec l'executable dans le dossier windows.
echo Depuis les sources, utilisez build-desktop.ps1 pour le compiler.
pause
exit /b 1
