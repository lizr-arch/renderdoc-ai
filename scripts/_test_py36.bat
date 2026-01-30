@echo off
set PY36="D:\Program Files\Python36\python.exe"
echo Testing Python 3.6 at %PY36%
%PY36% --version
if errorlevel 1 (
    echo FAILED: Python 3.6 not working
    exit /b 1
)
echo.
echo Testing renderdoc.pyd import...
%PY36% d:\Code\git\renderdoc\scripts\_test_pyd_import.py
