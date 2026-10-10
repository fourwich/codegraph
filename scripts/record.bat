@echo off
rem One-click CodeGraph demo recording (Windows).
rem Writes demo.cast at the repo root; no external recorder required.
setlocal
cd /d "%~dp0.."

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo Generating CodeGraph demo cast...
echo.
"%PY%" scripts\record_demo.py %*
if errorlevel 1 (
    echo.
    echo Recording failed. See the output above.
    exit /b 1
)

echo.
echo   Cast   : %CD%\demo.cast
echo   Page   : %CD%\demo.html  (published as /codegraph/demo.html)
echo   Upload : "%PY%" scripts\upload_demo.py demo.cast
echo.
endlocal