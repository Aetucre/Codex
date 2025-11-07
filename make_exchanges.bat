@echo off
setlocal

set "SCRIPT_PATH=%~dp0make_exchanges.py"

where python >nul 2>&1
if %ERRORLEVEL%==0 (
    set "PYTHON_EXEC=python"
) else (
    where py >nul 2>&1
    if %ERRORLEVEL%==0 (
        set "PYTHON_EXEC=py"
    ) else (
        echo Python interpreter not found. Please install Python or add it to PATH.
        exit /b 1
    )
)

%PYTHON_EXEC% "%SCRIPT_PATH%" %*
