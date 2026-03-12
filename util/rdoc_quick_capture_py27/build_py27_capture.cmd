@echo off
setlocal

rem Build rdoc_capture.pyd for embedded Python 2.7 (x64).

set SCRIPT_DIR=%~dp0
for %%I in ("%SCRIPT_DIR%..\\..") do set REPO_ROOT=%%~fI

set VS_DEV_CMD=E:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat
set PY_INC=F:\Code\S1\doc\tools\Formation_Toos\venv\Include
set PY_DLL=F:\Code\S1\Engine\Binaries\Win64\capture_texture\python27.dll
set RENDERDOC_INC=%REPO_ROOT%\renderdoc\api\app
set OUT_DIR=%SCRIPT_DIR%out

if not exist "%VS_DEV_CMD%" (
  echo VsDevCmd.bat not found: %VS_DEV_CMD%
  exit /b 1
)

if not exist "%PY_INC%\Python.h" (
  echo Python.h not found: %PY_INC%
  exit /b 1
)

if not exist "%PY_DLL%" (
  echo python27.dll not found: %PY_DLL%
  exit /b 1
)

if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

call "%VS_DEV_CMD%" -arch=x64 -host_arch=x64

rem Generate python27.lib from python27.dll if missing.
if not exist "%OUT_DIR%\python27.lib" (
  echo Generating python27.lib...
  dumpbin /exports "%PY_DLL%" > "%OUT_DIR%\python27.exports.txt"
  py -3 "%SCRIPT_DIR%make_def.py" "%OUT_DIR%\python27.exports.txt" "%OUT_DIR%\python27.def"
  lib /def:"%OUT_DIR%\python27.def" /machine:x64 /out:"%OUT_DIR%\python27.lib"
)

echo Building rdoc_capture.pyd...
cl /nologo /LD /EHsc ^
  /I "%PY_INC%" /I "%RENDERDOC_INC%" ^
  "%SCRIPT_DIR%rdoc_capture_py27.cpp" ^
  /link /OUT:"%OUT_DIR%\rdoc_capture.pyd" /LIBPATH:"%OUT_DIR%" python27.lib
if errorlevel 1 exit /b 1

echo Done: %OUT_DIR%\rdoc_capture.pyd
endlocal
